import sqlite3

conn = sqlite3.connect("places.db")
cur = conn.cursor()

# Проверим, какие таблицы есть в базе
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("📋 Таблицы в базе данных:")
for row in cur.fetchall():
    print(" -", row[0])

# Проверим, сколько строк в таблице places
cur.execute("SELECT COUNT(*) FROM places;")
count = cur.fetchone()[0]
print(f"\n📊 Количество записей в places: {count}")

# Посмотрим первые 5 строк
print("\n🔹 Пример данных:")
for row in cur.execute("SELECT name, city, rating FROM places LIMIT 5;"):
    print(row)

conn.close()
