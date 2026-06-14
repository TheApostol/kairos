"""Manual verification harness for lead-discovery sources.

Usage:
    python -m scripts.test_sources <source_id> [--limit N] [--areas A,B] [--full]

Prints yielded records as JSON (one per line), does not write to the
database. `--areas` is passed through as a comma-separated list to sources
that accept an `areas` kwarg (overpass, paginas_amarillas). `--full` passes
`use_full_dataset=True` to datos_gob.
"""

import argparse
import json
import sys

from sources import SOURCE_REGISTRY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id", choices=sorted(SOURCE_REGISTRY.keys()))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--areas", type=str, default=None, help="comma-separated area/geo names")
    parser.add_argument("--full", action="store_true", help="use_full_dataset=True (datos_gob only)")
    parser.add_argument("--api-key", type=str, default=None, help="Google API key (google_places only)")
    args = parser.parse_args()

    iter_fn = SOURCE_REGISTRY[args.source_id]

    kwargs: dict = {"max_records": args.limit}
    if args.areas:
        kwargs["areas"] = args.areas.split(",")
    if args.full:
        kwargs["use_full_dataset"] = True
    if args.api_key:
        kwargs["api_key"] = args.api_key

    count = 0
    try:
        for record in iter_fn(**kwargs):
            print(json.dumps(record, ensure_ascii=False, indent=2))
            count += 1
            if count >= args.limit:
                break
    except NotImplementedError as exc:
        print(f"Source '{args.source_id}' not implemented: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n--- {count} record(s) yielded ---", file=sys.stderr)


if __name__ == "__main__":
    main()
