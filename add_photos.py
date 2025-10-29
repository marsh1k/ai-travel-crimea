import time
import requests
import pandas as pd

INPUT_FILE = "places_semicolon.csv"
OUTPUT_FILE = "places_semicolon.csv"

HEADERS = {"User-Agent": "AI Travel Crimea Bot/1.0 (https://t.me/yourbot)"}

def find_image_wikipedia(query: str):
    """Ищет основное изображение статьи Википедии"""
    try:
        url = "https://ru.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "pageimages",
            "format": "json",
            "piprop": "original",
            "titles": query
        }
        res = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = res.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "original" in page:
                return page["original"]["source"]
    except Exception as e:
        print(f"⚠️ Ошибка при поиске {query}: {e}")
    return None

def main():
    df = pd.read_csv(INPUT_FILE, sep=";")
    if "photo" not in df.columns:
        df["photo"] = ""

    for i, row in df.iterrows():
        if isinstance(row.get("photo"), str) and row["photo"].startswith("http"):
            continue  # уже есть фото
        query = f"{row['name']} {row['city']} Крым"
        print(f"🔎 Ищу фото для: {query}")
        img = find_image_wikipedia(query)
        if not img:
            # если нет точного совпадения — попробуем без города
            img = find_image_wikipedia(row["name"])
        if img:
            df.at[i, "photo"] = img
            print(f"✅ Найдено фото: {img}")
        else:
            print(f"❌ Не найдено фото для {query}")
        time.sleep(0.5)

    df.to_csv(OUTPUT_FILE, sep=";", index=False)
    print(f"\n💾 Файл сохранён: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
