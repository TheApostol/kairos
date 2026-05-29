#!/usr/bin/env python3
"""
Importa todos los leads de los CSVs a Supabase.
Deduplica por empresa+direccion para no repetir al re-correr.
"""

import csv, requests, json, re, sys
from datetime import datetime

SUPABASE_URL = "https://gachxhquivfvwejytsbb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdhY2h4aHF1aXZmdndlanl0c2JiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3MTczMTksImV4cCI6MjA5MTI5MzMxOX0.AjHenUD4i_xErSORT8WzIpDt3Vvrn5pU2tMTevxzZ3Y"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

FAKE_EMAILS = ["nuvempago","ejemplo.com","example","domain","sentry","wix",
               "shopify",".png",".jpg",".gif","@2x"]

CSV_FILES = [
    "base_holistica_20260529_0832_enriquecido.csv",
    "base_expansion_20260529_0859.csv",
]

def clean(row):
    def s(v): return v.strip() if v and v.strip() else None
    def f(v):
        try: return float(v) if v and v.strip() else None
        except: return None
    def i(v):
        try: return int(float(v)) if v and v.strip() else None
        except: return None
    def valid_email(e):
        if not e: return None
        if any(x in e for x in FAKE_EMAILS): return None
        if "@" not in e or "." not in e.split("@")[-1]: return None
        return e.strip()
    def clean_date(v):
        if not v or not v.strip(): return None
        try:
            datetime.strptime(v.strip(), "%Y-%m-%d")
            return v.strip()
        except: return None

    return {
        "empresa":          s(row.get("empresa","")) or "Sin nombre",
        "rubro":            s(row.get("rubro","")),
        "direccion":        s(row.get("direccion","")),
        "ciudad":           s(row.get("ciudad","")),
        "provincia":        s(row.get("provincia","")),
        "telefono":         s(row.get("telefono","")),
        "website":          s(row.get("website","")),
        "google_maps_url":  s(row.get("google_maps_url","")),
        "rating":           f(row.get("rating","")),
        "reviews_count":    i(row.get("reviews_count","")),
        "price_level":      i(row.get("price_level","")),
        "horarios":         s(row.get("horarios","")),
        "instagram":        s(row.get("instagram","")),
        "email":            valid_email(row.get("email","")),
        "whatsapp":         s(row.get("whatsapp","")),
        "score_ia":         i(row.get("score_ia","")),
        "observaciones":    s(row.get("observaciones","")),
        "fuente":           s(row.get("fuente","")) or "Google Places API",
        "fecha_extraccion": clean_date(row.get("fecha_extraccion","")),
        "estado":           "nuevo",
    }

def insert_batch(rows):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/leads",
        headers=HEADERS,
        data=json.dumps(rows),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
        return False
    return True

def run():
    all_rows = []
    seen = set()

    for fname in CSV_FILES:
        try:
            with open(fname, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    cleaned = clean(row)
                    # dedup key
                    key = (cleaned["empresa"].lower(), (cleaned["direccion"] or "").lower()[:50])
                    if key in seen:
                        continue
                    seen.add(key)
                    all_rows.append(cleaned)
        except FileNotFoundError:
            print(f"⚠ No encontrado: {fname}")

    total = len(all_rows)
    print(f"\n📦 Importando {total} leads a Supabase...")

    BATCH = 100
    ok = 0
    for i in range(0, total, BATCH):
        batch = all_rows[i:i+BATCH]
        if insert_batch(batch):
            ok += len(batch)
            pct = int(100 * ok / total)
            print(f"  [{pct:3d}%] {ok}/{total} insertados", end="\r")

    print(f"\n✅ Importación completa: {ok}/{total} leads en Supabase")

if __name__ == "__main__":
    run()
