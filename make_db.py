import pandas as pd
import sqlite3
import os

base_dir = os.path.dirname(__file__)
csv_path = os.path.join(base_dir, "places_semicolon.csv")
db_path = os.path.join(base_dir, "places.db")

print("📂 CSV path:", csv_path)
print("📦 DB path:", db_path)

df = pd.read_csv(csv_path, encoding="utf-8-sig", sep=";")
print(f"✅ CSV загружен: {len(df)} строк")

conn = sqlite3.connect(db_path)
df.to_sql("places", conn, if_exists="replace", index=False)
conn.close()

print("✅ Данные успешно перенесены в places.db")

import sqlite3

conn = sqlite3.connect("places.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    city TEXT,
    interests TEXT,
    has_car INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("✅ Таблица users успешно создана в базе places.db")
