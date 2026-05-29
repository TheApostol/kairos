#!/usr/bin/env python3
"""
Enriquecedor de Base - Fase 2
Lee el CSV generado por scraper_holistica.py
Intenta completar: email, Instagram real, WhatsApp
Fuentes: scraping de website propio de cada negocio
"""

import csv
import re
import time
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
INSTAGRAM_REGEX = re.compile(r'instagram\.com/([A-Za-z0-9._]{1,30})')
WA_REGEX = re.compile(r'(?:wa\.me|whatsapp\.com/send\?phone=)[/\?]?(\d{6,15})')

def scrape_website(url, timeout=8):
    """Extrae email, instagram y whatsapp del sitio web del negocio"""
    result = {"email": "", "instagram": "", "whatsapp": ""}
    if not url or not url.startswith("http"):
        return result

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return result

        text = resp.text

        # Email
        emails = EMAIL_REGEX.findall(text)
        valid_emails = [e for e in emails if not any(x in e for x in ["example", "domain", "sentry", "wix", "shopify"])]
        if valid_emails:
            result["email"] = valid_emails[0]

        # Instagram
        ig_matches = INSTAGRAM_REGEX.findall(text)
        if ig_matches:
            result["instagram"] = f"@{ig_matches[0]}"

        # WhatsApp
        wa_matches = WA_REGEX.findall(text)
        if wa_matches:
            result["whatsapp"] = wa_matches[0]

        # También buscar en links <a>
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "instagram.com" in href and not result["instagram"]:
                ig = INSTAGRAM_REGEX.search(href)
                if ig:
                    result["instagram"] = f"@{ig.group(1)}"
            if "wa.me" in href and not result["whatsapp"]:
                wa = WA_REGEX.search(href)
                if wa:
                    result["whatsapp"] = wa.group(1)
            if "mailto:" in href and not result["email"]:
                result["email"] = href.replace("mailto:", "").split("?")[0]

    except Exception:
        pass

    return result

def enrich_csv(input_file, output_file=None):
    if not output_file:
        output_file = input_file.replace(".csv", "_enriquecido.csv")

    rows = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"\n🔍 Enriqueciendo {len(rows)} registros...")
    print("   Solo procesa los que tienen website y email vacío.\n")

    to_enrich = [r for r in rows if r.get("website") and not r.get("email")]
    print(f"   Con website sin email: {len(to_enrich)}")

    for i, row in enumerate(rows):
        if not row.get("website") or row.get("email"):
            continue

        enrich = scrape_website(row["website"])
        changed = []

        for field in ["email", "instagram", "whatsapp"]:
            if enrich.get(field) and not row.get(field):
                row[field] = enrich[field]
                changed.append(field)

        if changed:
            print(f"  [{i+1}] {row['empresa'][:30]} → {', '.join(changed)}")

        time.sleep(0.3)

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with_email = sum(1 for r in rows if r.get("email"))
    with_ig = sum(1 for r in rows if r.get("instagram") and not r["instagram"].startswith("@") or (r.get("instagram") and "@" in r.get("instagram", "")))

    print(f"\n✅ Enriquecimiento completado")
    print(f"   Con email:     {with_email}")
    print(f"   Output:        {output_file}")
    return output_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 enriquecedor.py base_holistica_YYYYMMDD_HHMM.csv")
        sys.exit(1)
    enrich_csv(sys.argv[1])
