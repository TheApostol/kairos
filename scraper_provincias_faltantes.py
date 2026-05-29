#!/usr/bin/env python3
"""
Scraper focalizado en provincias con poca o nula cobertura.
Formosa, Catamarca, La Rioja, Santa Cruz, Tierra del Fuego (0 registros)
+ Corrientes, Santiago del Estero, Jujuy, Salta, Entre Ríos (pocos)
"""

import requests, csv, time, re, sys
from datetime import datetime

GOOGLE_API_KEY = "AIzaSyAosnVIoKExn0bmu6A-rDccBYJkO2D5aeM"

PROVINCIAS_TARGET = [
    # Sin datos
    "Formosa", "Catamarca", "La Rioja", "Santa Cruz", "Tierra del Fuego",
    # Pocos datos
    "Corrientes", "Santiago del Estero", "Jujuy", "Salta", "Entre Ríos",
    "Chaco", "Tucumán", "La Pampa",
]

RUBROS = [
    "sahumerios", "tienda holistica", "santeria", "aromaterapia",
    "velas artesanales", "cristales minerales", "herboristeria",
    "productos naturales", "cosmética natural", "yoga tienda",
    "tienda esoterica", "inciensos", "esencias aromáticas",
]

# Genera queries cruzando provincia × rubro
SEARCH_QUERIES = []
for prov in PROVINCIAS_TARGET:
    for rubro in RUBROS:
        SEARCH_QUERIES.append(f"{rubro} {prov}")
    # búsqueda genérica también
    SEARCH_QUERIES.append(f"tienda holistica {prov}")
    SEARCH_QUERIES.append(f"mayorista sahumerios {prov}")

OUTPUT_FILE = f"base_provincias_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

FIELDNAMES = [
    "empresa", "rubro", "direccion", "ciudad", "provincia",
    "telefono", "website", "google_maps_url", "rating",
    "reviews_count", "price_level", "horarios",
    "instagram", "email", "whatsapp",
    "score_ia", "observaciones", "fuente", "fecha_extraccion"
]

def places_text_search(query, page_token=None):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": GOOGLE_API_KEY, "language": "es", "region": "ar"}
    if page_token:
        params["pagetoken"] = page_token
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def place_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_API_KEY,
        "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,price_level,opening_hours,address_components,url",
        "language": "es",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("result", {})

def extract_province(ac):
    for c in ac:
        if "administrative_area_level_1" in c.get("types", []):
            return c.get("long_name", "")
    return ""

def extract_city(ac):
    for c in ac:
        if "locality" in c.get("types", []):
            return c.get("long_name", "")
    return ""

def score_lead(r):
    s = 0
    if r.get("telefono"): s += 2
    if r.get("website"):  s += 2
    if r.get("email"):    s += 2
    if r.get("instagram"): s += 1
    try:
        if float(r.get("rating", 0)) >= 4.0: s += 2
    except: pass
    try:
        if int(r.get("reviews_count", 0)) >= 20: s += 1
    except: pass
    return min(s, 10)

ARGENTINA_PROVINCES = {
    "formosa", "catamarca", "la rioja", "santa cruz", "tierra del fuego",
    "corrientes", "santiago del estero", "jujuy", "salta", "entre ríos",
    "chaco", "tucumán", "la pampa", "misiones", "chubut", "río negro",
    "neuquén", "san luis", "san juan", "mendoza", "córdoba", "santa fe",
    "provincia de buenos aires", "ciudad autónoma de buenos aires",
}

def is_argentina(province):
    return province.lower() in ARGENTINA_PROVINCES

def run():
    # Cargar IDs ya conocidos
    seen_ids = set()
    import glob
    for f in glob.glob("base_*.csv"):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    url = row.get("google_maps_url", "")
                    if "cid=" in url:
                        seen_ids.add(url.split("cid=")[-1])
        except: pass

    print(f"\n{'='*55}")
    print(f"  SCRAPER PROVINCIAS FALTANTES")
    print(f"  {len(SEARCH_QUERIES)} queries | IDs conocidos: {len(seen_ids)}")
    print(f"{'='*55}\n")

    results = []
    for i, query in enumerate(SEARCH_QUERIES):
        next_page_token = None
        page = 0
        query_new = 0

        while page < 3:
            try:
                if page > 0 and next_page_token:
                    time.sleep(2)
                data = places_text_search(query, next_page_token)
                places = data.get("results", [])

                for place in places:
                    pid = place.get("place_id")
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    time.sleep(0.1)
                    details = place_details(pid)
                    ac = details.get("address_components", [])
                    prov = extract_province(ac)

                    # Filtrar solo Argentina
                    if not is_argentina(prov):
                        continue

                    phone   = details.get("formatted_phone_number","") or details.get("international_phone_number","")
                    website = details.get("website","")
                    slug    = re.sub(r'[^a-z0-9]', '', place.get("name","").lower())

                    record = {
                        "empresa":          details.get("name", place.get("name","")),
                        "rubro":            "Tienda Holística / Sahumerios",
                        "direccion":        details.get("formatted_address",""),
                        "ciudad":           extract_city(ac),
                        "provincia":        prov,
                        "telefono":         phone,
                        "website":          website,
                        "google_maps_url":  details.get("url",""),
                        "rating":           details.get("rating",""),
                        "reviews_count":    details.get("user_ratings_total",""),
                        "price_level":      details.get("price_level",""),
                        "horarios":         "; ".join(details.get("opening_hours",{}).get("weekday_text",[])),
                        "instagram":        f"@{slug[:20]}" if slug else "",
                        "email":            "",
                        "whatsapp":         phone.replace(" ","").replace("-","").replace("+","") if phone else "",
                        "score_ia":         "",
                        "observaciones":    "",
                        "fuente":           "Google Places API",
                        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d"),
                    }
                    record["score_ia"] = score_lead(record)
                    results.append(record)
                    query_new += 1

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
                page += 1

            except Exception as e:
                print(f"   ⚠ {e}")
                break

        if query_new > 0:
            print(f"[{i+1}/{len(SEARCH_QUERIES)}] {query} → +{query_new} | Total: {len(results)}")
        time.sleep(0.3)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*55}")
    print(f"  ✅ {len(results)} nuevos registros — {OUTPUT_FILE}")
    print(f"{'='*55}")

    # Breakdown por provincia
    from collections import Counter
    cnt = Counter(r["provincia"] for r in results)
    for prov, n in cnt.most_common():
        print(f"  {n:4d}  {prov}")

if __name__ == "__main__":
    run()
