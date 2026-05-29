#!/usr/bin/env python3
"""
Scraper de Tiendas Holísticas Argentina
Fuente primaria: Google Places API
Output: CSV listo para campañas comerciales mayoristas
"""

import requests
import csv
import time
import json
import re
import sys
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

GOOGLE_API_KEY = "AIzaSyAosnVIoKExn0bmu6A-rDccBYJkO2D5aeM"  # ← reemplazar

SEARCH_QUERIES = [
    "sahumerios Argentina",
    "tienda holistica Argentina",
    "santeria Argentina",
    "aromaterapia tienda Argentina",
    "velas de soja tienda Argentina",
    "esencias aromáticas tienda Argentina",
    "inciensos tienda Argentina",
    "productos esotericos tienda Argentina",
    "reiki shop Argentina",
    "tienda espiritual Argentina",
    "sahumerios Buenos Aires",
    "sahumerios Córdoba",
    "sahumerios Rosario",
    "sahumerios Mendoza",
    "tienda holistica Tucumán",
    "tienda holistica Salta",
    "tienda holistica Mar del Plata",
    "tienda holistica La Plata",
    "tienda esoterica Neuquén",
    "tienda esoterica Santa Fe",
]

OUTPUT_FILE = f"base_holistica_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
MAX_RESULTS_PER_QUERY = 60  # 3 páginas × 20 resultados

FIELDNAMES = [
    "empresa", "rubro", "direccion", "ciudad", "provincia",
    "telefono", "website", "google_maps_url", "rating",
    "reviews_count", "price_level", "horarios",
    "instagram", "email", "whatsapp",
    "score_ia", "observaciones", "fuente", "fecha_extraccion"
]

# ─────────────────────────────────────────────
# FUNCIONES GOOGLE PLACES
# ─────────────────────────────────────────────

def places_text_search(query, page_token=None):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": GOOGLE_API_KEY,
        "language": "es",
        "region": "ar",
    }
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

def extract_province(address_components):
    for comp in address_components:
        if "administrative_area_level_1" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""

def extract_city(address_components):
    for comp in address_components:
        if "locality" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""

def infer_instagram(name, website=""):
    """Intenta construir handle de Instagram desde el nombre"""
    if website and "instagram.com" in website:
        return website
    slug = re.sub(r'[^a-z0-9]', '', name.lower().replace(' ', ''))
    return f"@{slug[:20]}"  # estimado, requiere verificación

def score_lead(record):
    """Score simple 1-10 basado en completitud y señales de negocio"""
    score = 0
    if record.get("telefono"): score += 2
    if record.get("website"): score += 2
    if record.get("email"): score += 2
    if record.get("instagram"): score += 1
    rating = record.get("rating", 0)
    if rating and float(rating) >= 4.0: score += 2
    reviews = record.get("reviews_count", 0)
    if reviews and int(reviews) >= 20: score += 1
    return min(score, 10)

# ─────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────

def run_scraper():
    seen_ids = set()
    results = []

    print(f"\n{'='*50}")
    print("  SCRAPER HOLÍSTICA ARGENTINA")
    print(f"  Queries: {len(SEARCH_QUERIES)} | Target: 500-1000 registros")
    print(f"{'='*50}\n")

    for i, query in enumerate(SEARCH_QUERIES):
        print(f"[{i+1}/{len(SEARCH_QUERIES)}] Buscando: {query}")
        next_page_token = None
        page = 0

        while page < 3:  # máximo 3 páginas por query
            try:
                if page > 0 and next_page_token:
                    time.sleep(2)  # Google requiere delay para page tokens

                data = places_text_search(query, next_page_token)
                places = data.get("results", [])

                for place in places:
                    pid = place.get("place_id")
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    # Obtener detalles completos
                    time.sleep(0.1)
                    details = place_details(pid)

                    addr_comps = details.get("address_components", [])
                    phone = details.get("formatted_phone_number", "") or details.get("international_phone_number", "")
                    website = details.get("website", "")

                    record = {
                        "empresa": details.get("name", place.get("name", "")),
                        "rubro": "Tienda Holística / Sahumerios",
                        "direccion": details.get("formatted_address", ""),
                        "ciudad": extract_city(addr_comps),
                        "provincia": extract_province(addr_comps),
                        "telefono": phone,
                        "website": website,
                        "google_maps_url": details.get("url", ""),
                        "rating": details.get("rating", ""),
                        "reviews_count": details.get("user_ratings_total", ""),
                        "price_level": details.get("price_level", ""),
                        "horarios": "; ".join(details.get("opening_hours", {}).get("weekday_text", [])),
                        "instagram": infer_instagram(place.get("name", ""), website),
                        "email": "",  # requiere enriquecimiento manual o scraping web
                        "whatsapp": phone.replace(" ", "").replace("-", "").replace("+", "") if phone else "",
                        "score_ia": "",  # se calcula después
                        "observaciones": "",
                        "fuente": "Google Places API",
                        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d"),
                    }
                    record["score_ia"] = score_lead(record)
                    results.append(record)

                print(f"   Página {page+1}: +{len(places)} lugares | Total acumulado: {len(results)}")

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
                page += 1

            except requests.exceptions.RequestException as e:
                print(f"   ⚠ Error en query '{query}': {e}")
                break
            except Exception as e:
                print(f"   ⚠ Error inesperado: {e}")
                break

        if len(results) >= MAX_RESULTS_PER_QUERY * len(SEARCH_QUERIES):
            print("\n✓ Límite alcanzado.")
            break

        time.sleep(0.5)

    # ─── ESCRIBIR CSV ───
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*50}")
    print(f"  ✅ COMPLETADO")
    print(f"  Registros únicos: {len(results)}")
    print(f"  Archivo: {OUTPUT_FILE}")
    print(f"{'='*50}\n")

    # Stats rápidas
    with_phone = sum(1 for r in results if r.get("telefono"))
    with_web = sum(1 for r in results if r.get("website"))
    high_score = sum(1 for r in results if r.get("score_ia", 0) >= 7)

    print(f"  📊 Con teléfono:     {with_phone} ({100*with_phone//max(len(results),1)}%)")
    print(f"  📊 Con website:      {with_web} ({100*with_web//max(len(results),1)}%)")
    print(f"  📊 Score IA ≥ 7:     {high_score} ({100*high_score//max(len(results),1)}%)")
    print()

    return OUTPUT_FILE, results

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print("DRY RUN: sin API key. El script está listo para ejecutar con tu clave real.")
        print(f"Queries configuradas: {len(SEARCH_QUERIES)}")
        print(f"Output esperado: {OUTPUT_FILE}")
    else:
        if GOOGLE_API_KEY == "TU_API_KEY_AQUI":
            print("⚠ Agregá tu Google API Key en la variable GOOGLE_API_KEY")
            sys.exit(1)
        run_scraper()
