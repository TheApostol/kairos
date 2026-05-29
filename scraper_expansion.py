#!/usr/bin/env python3
"""
Expansión de base — rubros relacionados con Kairos
Corre sobre el mismo motor que scraper_holistica.py
"""

import requests, csv, time, re, sys
from datetime import datetime

GOOGLE_API_KEY = "AIzaSyAosnVIoKExn0bmu6A-rDccBYJkO2D5aeM"

SEARCH_QUERIES = [
    # Cristales y minerales
    "tienda de cristales Argentina",
    "minerales y piedras preciosas tienda Argentina",
    "cristales curativos Buenos Aires",
    "gemas y minerales tienda Córdoba",
    "piedras energéticas tienda Argentina",
    # Herboristería / naturismo
    "herboristería Argentina",
    "dietética naturista Argentina",
    "productos naturales tienda Argentina",
    "herbolaria tienda Argentina",
    "farmacia naturista Argentina",
    "tienda naturista Buenos Aires",
    "productos herbales Argentina",
    # Yoga / meditación
    "tienda yoga Argentina",
    "accesorios yoga Buenos Aires",
    "tienda meditación Argentina",
    "ropa yoga tienda Argentina",
    "mandala shop Argentina",
    # Budismo / oriente
    "tienda budista Argentina",
    "artículos orientales tienda Argentina",
    "tienda tibetana Argentina",
    "budismo tienda Buenos Aires",
    "zen shop Argentina",
    # Bienestar / spa / terapias
    "spa productos tienda Argentina",
    "aromaterapia profesional Argentina",
    "centro bienestar tienda Argentina",
    "terapias alternativas tienda Argentina",
    "aceites esenciales tienda Argentina",
    # Cosmética natural
    "cosmética natural tienda Argentina",
    "cosmética vegana Argentina",
    "jabones artesanales tienda Argentina",
    "tienda orgánica Argentina",
    # Velas / insumos
    "insumos velas Argentina",
    "velas artesanales tienda Argentina",
    "insumos sahumerios Argentina",
    "cera de soja Argentina",
    # Regalería / deco holística
    "regalería holística Argentina",
    "deco zen tienda Argentina",
    "regalos espirituales Argentina",
    "tienda regalos alternativos Argentina",
    # Ferias / mercados alternativos
    "feria artesanal holística Buenos Aires",
    "mercado esotérico Argentina",
    "feria new age Argentina",
    # Interior del país
    "tienda holistica Mendoza",
    "tienda holistica Rosario",
    "sahumerios Córdoba",
    "tienda esoterica Tucumán",
    "tienda holistica Santa Fe",
    "tienda holistica Neuquén",
    "tienda holistica Bariloche",
    "tienda holistica Salta",
    "tienda holistica Jujuy",
    "tienda holistica Mar del Plata",
    "tienda holistica La Plata",
    "tienda holistica Bahía Blanca",
    "tienda holistica Posadas",
    "tienda holistica Resistencia",
    "tienda holistica San Luis",
    "tienda holistica San Juan",
    "tienda holistica Paraná",
    "tienda holistica Río Cuarto",
    "tienda holistica Villa María",
    "tienda holistica Rafaela",
    # Mayoristas / distribuidores
    "mayorista sahumerios Argentina",
    "distribuidora productos holísticos Argentina",
    "mayorista velas Argentina",
    "mayorista aromas Argentina",
    "distribuidora esoterica Argentina",
    "mayorista cosmética natural Argentina",
    # Flores de Bach / homeopatía
    "flores de bach tienda Argentina",
    "homeopatía tienda Argentina",
    # Tarot / esoterismo
    "librería esotérica Argentina",
    "tarot tienda Argentina",
    "astrología tienda Argentina",
    "magia blanca tienda Argentina",
    "wicca tienda Argentina",
    # Feng shui / decoración energética
    "feng shui tienda Argentina",
    "decoración energética tienda Argentina",
    # Difusores / aromatizadores
    "difusor aromas tienda Argentina",
    "aromatizador ambiental tienda Argentina",
    "humidificador ultrasónico tienda Argentina",
]

OUTPUT_FILE = f"base_expansion_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

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

def infer_rubro(query):
    q = query.lower()
    if "cristal" in q or "mineral" in q or "piedra" in q or "gema" in q: return "Cristales / Minerales"
    if "herbo" in q or "dietét" in q or "naturist" in q or "herbal" in q: return "Herboristería / Naturismo"
    if "yoga" in q or "medit" in q or "mandala" in q: return "Yoga / Meditación"
    if "budis" in q or "orient" in q or "tibet" in q or "zen" in q: return "Budismo / Oriente"
    if "spa" in q or "bienes" in q or "terapia" in q: return "Bienestar / Terapias"
    if "cosmét" in q or "vegana" in q or "jabón" in q or "orgán" in q: return "Cosmética Natural"
    if "vela" in q or "insumo" in q or "cera" in q: return "Velas / Insumos"
    if "regalo" in q or "deco" in q: return "Regalería / Deco Holística"
    if "feria" in q or "mercado" in q: return "Feria / Mercado"
    if "mayor" in q or "distribu" in q: return "Mayorista / Distribuidora"
    if "flor" in q or "homeop" in q: return "Flores de Bach / Homeopatía"
    if "tarot" in q or "astro" in q or "magia" in q or "wicca" in q or "librer" in q: return "Esoterismo / Tarot"
    if "feng" in q or "energét" in q: return "Feng Shui"
    if "difusor" in q or "aromatiz" in q or "humidif" in q: return "Difusores / Aromatizadores"
    if "aromaterapia" in q or "aceite" in q: return "Aromaterapia"
    return "Tienda Holística"

def score_lead(r):
    score = 0
    if r.get("telefono"): score += 2
    if r.get("website"): score += 2
    if r.get("email"): score += 2
    if r.get("instagram"): score += 1
    try:
        if float(r.get("rating", 0)) >= 4.0: score += 2
    except: pass
    try:
        if int(r.get("reviews_count", 0)) >= 20: score += 1
    except: pass
    return min(score, 10)

def run():
    # Cargar place_ids ya existentes para no duplicar
    seen_ids = set()
    import glob, os
    for f in glob.glob("base_holistica_*.csv") + glob.glob("base_expansion_*.csv"):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    url = row.get("google_maps_url","")
                    if "cid=" in url:
                        seen_ids.add(url.split("cid=")[-1])
        except: pass

    results = []
    print(f"\n{'='*55}")
    print(f"  EXPANSIÓN DE BASE — {len(SEARCH_QUERIES)} queries")
    print(f"  IDs ya conocidos: {len(seen_ids)}")
    print(f"{'='*55}\n")

    for i, query in enumerate(SEARCH_QUERIES):
        rubro = infer_rubro(query)
        print(f"[{i+1}/{len(SEARCH_QUERIES)}] {query}")
        next_page_token = None
        page = 0

        while page < 3:
            try:
                if page > 0 and next_page_token:
                    time.sleep(2)
                data = places_text_search(query, next_page_token)
                places = data.get("results", [])

                new = 0
                for place in places:
                    pid = place.get("place_id")
                    cid = ""
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    time.sleep(0.1)
                    details = place_details(pid)
                    ac = details.get("address_components", [])
                    phone = details.get("formatted_phone_number","") or details.get("international_phone_number","")
                    website = details.get("website","")
                    maps_url = details.get("url","")

                    slug = re.sub(r'[^a-z0-9]', '', place.get("name","").lower())
                    instagram = f"@{slug[:20]}" if slug else ""

                    record = {
                        "empresa": details.get("name", place.get("name","")),
                        "rubro": rubro,
                        "direccion": details.get("formatted_address",""),
                        "ciudad": extract_city(ac),
                        "provincia": extract_province(ac),
                        "telefono": phone,
                        "website": website,
                        "google_maps_url": maps_url,
                        "rating": details.get("rating",""),
                        "reviews_count": details.get("user_ratings_total",""),
                        "price_level": details.get("price_level",""),
                        "horarios": "; ".join(details.get("opening_hours",{}).get("weekday_text",[])),
                        "instagram": instagram,
                        "email": "",
                        "whatsapp": phone.replace(" ","").replace("-","").replace("+","") if phone else "",
                        "score_ia": "",
                        "observaciones": "",
                        "fuente": "Google Places API",
                        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d"),
                    }
                    record["score_ia"] = score_lead(record)
                    results.append(record)
                    new += 1

                print(f"   Pág {page+1}: +{new} nuevos | Total acumulado: {len(results)}")
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
                page += 1

            except Exception as e:
                print(f"   ⚠ {e}")
                break

        time.sleep(0.5)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*55}")
    print(f"  ✅ COMPLETADO — {len(results)} registros nuevos")
    print(f"  Archivo: {OUTPUT_FILE}")
    print(f"{'='*55}")
    with_phone = sum(1 for r in results if r.get("telefono"))
    with_web   = sum(1 for r in results if r.get("website"))
    high_score = sum(1 for r in results if int(r.get("score_ia",0)) >= 7)
    print(f"  Con teléfono:  {with_phone} ({100*with_phone//max(len(results),1)}%)")
    print(f"  Con website:   {with_web} ({100*with_web//max(len(results),1)}%)")
    print(f"  Score IA ≥ 7:  {high_score} ({100*high_score//max(len(results),1)}%)")

if __name__ == "__main__":
    run()
