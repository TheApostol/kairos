#!/usr/bin/env python3
"""Tenant-scope audit guardrail for Kairos/Polkorp SaaS backend.

Run from repository root:

    python app/backend/tools/audit_tenant_scope.py

Purpose:
- Prevent accidental raw `db` usage in tenant routers.
- Allow explicitly public/platform files.
- Encourage all tenant runtime access through `current_org.db` or `ScopedSupabaseClient`.

This is intentionally static and conservative. If it flags a false positive,
prefer refactoring the code for clarity instead of disabling the check.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTERS = ROOT / "app" / "backend" / "routers"

# Public/platform routers are allowed to use raw service client when they
# explicitly apply org filters or operate outside a tenant request context.
ALLOWED_RAW_DB_FILES = {
    "public.py",          # unauthenticated public catalog; manually filters by organization slug/id
    "organizations.py",   # platform membership/invitation bootstrap; uses auth helpers + explicit filters
    "platform.py",        # platform admin router; protected by platform_admins, not tenant membership
}

RAW_DB_CALL_RE = re.compile(r"(?<![A-Za-z0-9_.])db\.(select|select_all|raw_select|insert|update|delete|count)\(")
SCOPED_CLIENT_RE = re.compile(r"ScopedSupabaseClient\(\s*db\s*,")


def audit_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    errors: list[str] = []

    if path.name in ALLOWED_RAW_DB_FILES:
        return errors

    for match in RAW_DB_CALL_RE.finditer(text):
        line_no = text[: match.start()].count("\n") + 1
        line = text.splitlines()[line_no - 1].strip()
        errors.append(f"{rel}:{line_no}: raw tenant DB call: {line}")

    # Importing raw `db` is acceptable only when it is used to build a scoped
    # client for background jobs/SSE closures. Direct `db.*` calls are caught
    # above.
    if "from services.supabase_client import db" in text and not SCOPED_CLIENT_RE.search(text):
        errors.append(
            f"{rel}: imports raw `db` but does not construct ScopedSupabaseClient; "
            "tenant routers should use current_org.db"
        )

    return errors


def main() -> int:
    if not ROUTERS.exists():
        print(f"Routers directory not found: {ROUTERS}", file=sys.stderr)
        return 2

    errors: list[str] = []
    for path in sorted(ROUTERS.glob("*.py")):
        errors.extend(audit_file(path))

    if errors:
        print("Tenant scope audit FAILED:\n")
        for err in errors:
            print(f"- {err}")
        print("\nFix: use `current_org.db` inside request handlers or `ScopedSupabaseClient(db, org_id)` inside background jobs/SSE closures.")
        return 1

    print("Tenant scope audit passed: no unsafe raw `db` usage found in tenant routers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
