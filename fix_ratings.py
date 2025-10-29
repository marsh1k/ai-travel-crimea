import pandas as pd
import re

df = pd.read_csv("places_semicolon.csv", sep=";", encoding="utf-8-sig")

def fix_rating(v):
    s = str(v).strip()

    # Формат даты dd.mm.yyyy → 4.7
    m = re.match(r"^0?(\d{1,2})[.\-/]0?(\d{1,2})[.\-/]\d{2,4}$", s)
    if m:
        x, y = int(m.group(1)), int(m.group(2))
        val = round(x + y / 10.0, 1)
        return val if 0 <= val <= 10 else 4.5

    # Попробуем просто float (если вдруг нормальное число)
    s = s.replace(",", ".")
    try:
        f = float(s)
        return f if 0 <= f <= 10 else 4.5
    except:
        return 4.5

df["rating"] = df["rating"].apply(fix_rating)
df.to_csv("places_semicolon_fixed.csv", sep=";", encoding="utf-8-sig", index=False)
print("✅ Новый файл сохранён: places_semicolon_fixed.csv")
