import time
import requests
import pandas as pd

INPUT_FILE = "places_semicolon.csv"
OUTPUT_FILE = "places_semicolon.csv"

HEADERS = {"User-Agent": "AI Travel Crimea Bot/1.0 (https://t.me/yourbot)"}

# ---- Тематические fallback фото ----
FALLBACKS = {
    "море": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800",
    "природа": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=800",
    "архитектура": "https://images.unsplash.com/photo-1505842465776-3d90f616310d?w=800",
    "кафе": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800",
    "история": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=800",
    "поход": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=800",
    "семья": "https://images.unsplash.com/photo-1511895426328-dc8714191300?w=800",
    "фото": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=800",
    "default": "https://images.unsplash.com/photo-1503264116251-35a269479413?w=800",
}

def osm_find_photo(name, city):
    """Поиск фото через OpenStreetMap -> Wikidata -> Wikimedia"""
    try:
        q = f"{name}, {city}, Крым"
        url = "https://nominatim.openstreetmap.org/search"
        res = requests.get(url, params={"q": q, "format": "jsonv2", "limit": 1}, headers=HEADERS, timeout=10)
        data = res.json()
        if not data:
            return None

        place = data[0]
        wikidata_id = place.get("extratags", {}).get("wikidata")
        wikimedia_link = place.get("extratags", {}).get("wikimedia_commons")

        # если прямо есть ссылка на Wikimedia
        if wikimedia_link:
            file = wikimedia_link.split("/")[-1]
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{file}"

        # если есть Wikidata ID — пробуем вытянуть фото
        if wikidata_id:
            wd_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            wd_res = requests.get(wd_url, headers=HEADERS, timeout=10).json()
            entity = wd_res["entities"].get(wikidata_id, {})
            claims = entity.get("claims", {})
            if "P18" in claims:
                file_name = claims["P18"][0]["mainsnak"]["datavalue"]["value"]
                return f"https://commons.wikimedia.org/wiki/Special:FilePath/{file_name}"
    except Exception as e:
        print(f"⚠️ OSM ошибка для {name}: {e}")
    return None

def find_fallback(tags):
    """Выбор fallback-фото по тегам"""
    for tag in FALLBACKS:
        if tag in tags.lower():
            return FALLBACKS[tag]
    return FALLBACKS["default"]

def main():
    df = pd.read_csv(INPUT_FILE, sep=";")
    if "photo" not in df.columns:
        df["photo"] = ""

    for i, row in df.iterrows():
        current_photo = row.get("photo", "")
        if isinstance(current_photo, str) and current_photo.startswith("http"):
            continue  # уже есть фото

        name, city, tags = row["name"], row["city"], str(row.get("tags", ""))
        print(f"🔎 Ищу фото для: {name} ({city})")

        photo_url = osm_find_photo(name, city)
        if not photo_url:
            photo_url = find_fallback(tags)

        if photo_url:
            df.at[i, "photo"] = photo_url
            print(f"✅ Фото найдено или подставлено: {photo_url}")
        else:
            print(f"❌ Не удалось найти фото для {name}")
        time.sleep(1)

    df.to_csv(OUTPUT_FILE, sep=";", index=False)
    print(f"\n💾 Файл сохранён: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
