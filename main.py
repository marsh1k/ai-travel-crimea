import os
import math
import logging
import pandas as pd
import asyncio
import aiohttp
from typing import List, Dict, Tuple
from urllib.parse import quote_plus
import re
import numpy as np
from datetime import datetime, date

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)

# ================== Logging ==================
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s | %(message)s", level=logging.INFO
)
logger = logging.getLogger("ai-travel-crimea")

# ================== States ===================
ASK_CITY, ASK_INTERESTS, ASK_CAR = range(3)

# ============== Data & Config =================
BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "places_semicolon_fixed.csv")

def parse_rating(v):
    """Устойчивый парсер рейтинга: 4,8 / 4.75 / '4,7 из 5' / '04.07.2024' → 4.7 и т.д."""
    import re
    import numpy as np
    from datetime import datetime, date

    if isinstance(v, (pd.Timestamp, datetime, date)):
        # Из Excel пришло как дата-тип — ничего надёжно не вытащим → нейтрально
        return 4.5

    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return np.nan

    # A) Формат даты dd.mm.yyyy → берём dd.mm → x.y
    m = re.match(r"^0?(\d{1,2})[.\-/]0?(\d{1,2})[.\-/]\d{2,4}$", s)
    if m:
        x, y = int(m.group(1)), int(m.group(2))
        val = x + (y / 10.0)
        return max(0.0, min(10.0, val))

    # B) Десятичное число с 1–2 знаками: 4,7 / 4.8 / 4,75 / 9.99
    m = re.search(r"(\d{1,2})[.,](\d{1,2})", s)
    if m:
        whole = int(m.group(1))
        frac = m.group(2)
        val = float(f"{whole}.{frac}")
        return max(0.0, min(10.0, val))

    # C) Просто целое 0–10 (в т.ч. строки типа '4 из 5')
    m = re.search(r"\b(\d{1,2})\b", s)
    if m:
        val = float(m.group(1))
        if 0 <= val <= 10:
            return val

    # D) Последняя попытка — заменяем запятую на точку и парсим float
    try:
        val = float(s.replace(",", "."))
        return val if 0 <= val <= 10 else np.nan
    except:
        return np.nan


    try:
        val = float(s.replace(",", "."))
        return val if 0 <= val <= 10 else np.nan
    except:
        return np.nan


df = pd.read_csv(
    CSV_PATH,
    sep=";",
    encoding="utf-8-sig",
    converters={"rating": parse_rating}
)


# ============== Interests =====================
INTERESTS = [
    ("море", "🌊 Море/пляжи"),
    ("история", "🏛 История/музеи"),
    ("природа", "🌿 Природа"),
    ("фото", "📸 Фото"),
    ("поход", "🥾 Трекинг"),
    ("семья", "👨‍👩‍👧 Семейный отдых"),
    ("архитектура", "🏰 Архитектура"),
    ("кафе", "☕ Кафе/прогулка"),
    ("туалеты", "🚻 Туалеты поблизости"),
    ("медицина", "🏥 Медпомощь поблизости"),
    ("полиция", "👮 Полиция / помощь"),
]

# Города
CITIES_PRESETS: Dict[str, Tuple[float, float]] = {
    "Севастополь": (44.6167, 33.5254),
    "Ялта": (44.4985, 34.1661),
    "Симферополь": (44.9482, 34.1003),
    "Судак": (44.8512, 34.9747),
    "Феодосия": (45.0319, 35.3825),
    "Евпатория": (45.1904, 33.3665),
    "Новый Свет": (44.8295, 34.9141),
    "Алушта": (44.6764, 34.4100),
}

COASTAL_CITIES = {"Ялта", "Севастополь", "Алушта", "Судак", "Феодосия", "Евпатория", "Новый Свет", "Форос"}

SEA_POINTS = {
    "Ялта": (44.495, 34.166),
    "Севастополь": (44.605, 33.495),
    "Алушта": (44.665, 34.415),
    "Судак": (44.843, 34.973),
    "Феодосия": (45.042, 35.389),
    "Евпатория": (45.203, 33.363),
    "Новый Свет": (44.826, 34.914),
}

# ================= Экстренные базы =================
TOILETS = {
    "Севастополь": [
        {"name": "Бесплатный общественный туалет", "address": "площадь Восставших, д. 4, корп. 1, литера А, эт. 1, 2", "hours": "Закроется через 56 минут"},
        {"name": "Платный общественный туалет", "address": "просп. Генерала Острякова, 235", "hours": "Закрыто до среды"},
        {"name": "Платный общественный туалет", "address": "Назукина набережная, 35", "hours": "Открыто до 21:40"},
        {"name": "Платный общественный туалет", "address": "Нахимова пл., 3А, этаж 1", "hours": "Закроется через 56 минут"},
        {"name": "Бесплатный общественный туалет", "address": "улица Адмирала Октябрьского, 20к1", "hours": "Закрыто до среды"},
        {"name": "Платный туалет", "address": "Балаклавское шоссе 5 километр, 5/17к1", "hours": "Закрыто до среды"},
        {"name": "Платный общественный туалет", "address": "шоссе Балаклавское, 9Г"},
    ],
    "Симферополь": [
        {"name": "Общественный туалет", "address": "Симферополь, Яблочкова улица, 19А/2", "hours": "Закрыто до среды"},
        {"name": "Бесплатный общественный туалет", "address": "Симферополь, Самокиша ул., д. 18, этаж 1-4", "hours": "Открыто до 21:00"},
        {"name": "Общественный туалет", "address": "Симферополь, ул. Козлова, 5, эт. 1", "hours": "Закрыто до среды"},
        {"name": "Общественный туалет", "address": "Симферополь, улица Кечкеметская, 180/5", "hours": "Открыто до 21:00"},
        {"name": "Платный общественный туалет", "address": "Симферополь, Субхи ул., 2, к. 2, эт. 1", "hours": "Закрыто до среды"},
        {"name": "Крымавтотранс, Мужской туалет", "address": "Симферополь, Киевская ул., 100Б, строение 4, эт. 1"},
    ],
    "Ялта": [
        {"name": "Платный туалет", "address": "наб. им. Ленина, 5А, этаж 1", "hours": "Открыто до 21:00"},
        {"name": "Платный общественный туалет", "address": "Московская, д. 33, этаж 1", "hours": "Закрыто до среды"},
        {"name": "Бесплатный общественный туалет", "address": "улица Киевская, дом 6, Дом торговли, этаж 3", "hours": "Открыто до 22:00"},
        {"name": "Платный туалет", "address": "ул. Екатерининская, 4Б", "hours": "Открыто до 22:00"},
        {"name": "Платный туалет", "address": "переулок Черноморский, 2/1", "hours": "Открыто до 22:00"},
        {"name": "Платный общественный туалет", "address": "Пушкинская, 12", "hours": "Открыто до 22:00"},
        {"name": "Платный туалет", "address": "Карла Маркса, 3Б"},
    ],
    "Алушта": [
        {"name": "Туалет", "address": "Симферопольская ул., 1, Алушта"},
        {"name": "Туалет", "address": "Республика Крым, городской округ Алушта, Стрельбище"},
        {"name": "Платный туалет", "address": "Парковая ул., 2, Алушта"},
        {"name": "Туалет", "address": "Республика Крым, Алушта, микрорайон Профессорский Уголок"},
    ],
    "Феодосия": [
        {"name": "Туалет", "address": "Республика Крым, Феодосия, бульвар Старшинова", "hours": "ежедневно, 09:00–17:00"},
        {"name": "Туалет", "address": "Республика Крым, Феодосия, микрорайон Первушина", "hours": "ежедневно, 08:00–16:00"},
        {"name": "Туалет", "address": "ул. Нахимова, 5, Феодосия", "hours": "ежедневно, 08:00–17:00"},
        {"name": "Туалет", "address": "ул. Нахимова, 2, Феодосия", "hours": "ежедневно, 09:00–17:00"},
        {"name": "Туалет", "address": "Республика Крым, Феодосия, проспект Айвазовского", "hours": "ежедневно, 09:00–18:00"},
        {"name": "Туалет", "address": "ул. Федько, 2А, Феодосия"},
        {"name": "Туалет", "address": "ул. Назукина, 10А, Феодосия"},
    ],
    "Евпатория": [
        {"name": "Туалет", "address": "наб. Горького, 1, Евпатория", "hours": "ежедневно, 09:00–23:00"},
        {"name": "Туалет", "address": "просп. Победы, 49, Евпатория", "hours": "ежедневно, 08:00–19:00"},
        {"name": "Туалет", "address": "ул. Горького, 5У, Евпатория", "hours": "ежедневно, 09:00–23:00"},
        {"name": "Туалет", "address": "Раздольненское ш., 1Д, Евпатория", "phone": "+7 (3652) 77-20-40", "hours": "ежедневно, круглосуточно"},
        {"name": "Туалет", "address": "ул. Горького, 5К, Евпатория", "hours": "ежедневно, 08:00–00:00"},
        {"name": "Туалет", "address": "Республика Крым, Евпатория, квартал Курортный"},
    ],
}

POLICE = {
    "Евпатория": [
        {"name": "Отдел полиции", "address": "проезд 9 Мая, 3, Евпатория", "hours": "вт 9:00–11:00; чт 17:00–20:00; сб 10:00–13:00"},
        {"name": "Полиция", "address": "Евпаторийская ул., 4, село Уютное", "phone": "+7 (999) 461-06-74"},
        {"name": "Полиция", "address": "Перекопская ул., 2, Евпатория"},
    ],
    "Алушта": [
        {"name": "Полиция", "address": "Республика Крым, Алушта, улица Ленина"},
        {"name": "Полиция", "address": "ул. Ленина, 22, Алушта"},
    ],
    "Феодосия": [
        {"name": "Полиция", "address": "ул. Гагарина, 15, п. г. т. Приморский"},
        {"name": "Опорный пункт полиции", "address": "ул. Гарнаева, 71А, Феодосия"},
        {"name": "Участковый пункт полиции №3", "address": "бул. Старшинова, 12, Феодосия"},
    ],
    "Судак": [
        {"name": "Отдел МВД России по г. Судаку", "address": "Партизанская ул., 10, Судак", "phone": "+7 (999) 461-09-58"},
        {"name": "Полиция", "address": "ул. Льва Голицына, 18, п. г. т. Новый Свет", "phone": "+7 (999) 461-09-61"},
    ],
    "Симферополь": [
        {"name": "Участковый пункт полиции", "address": "Привокзальная площадь, 3А, Симферополь", "hours": "ежедневно, круглосуточно"},
        {"name": "Участковый пункт полиции", "address": "Ковыльная ул., 46, Симферополь"},
        {"name": "Участковый пункт полиции", "address": "ул. Трубаченко, 18, Симферополь", "phone": "102, +7 (999) 461-03-49"},
        {"name": "Участковый пункт полиции", "address": "ул. Горького, 7, Симферополь"},
        {"name": "Участковый пункт полиции", "address": "ул. 1-й Конной Армии, 74А, Симферополь"},
    ],
    "Севастополь": [
        {"name": "Полиция", "address": "ул. Пожарова, 3, Севастополь", "phone": "102"},
        {"name": "Полиция", "address": "ул. Генерала Петрова, 15, Севастополь", "phone": "102"},
        {"name": "Полиция", "address": "Россия, Севастополь, улица Руднева"},
        {"name": "Полиция", "address": "Россия, Севастополь, Индустриальная улица"},
        {"name": "Полиция", "address": "Россия, Севастополь, Большая Морская улица, 30"},
    ],
    "Ялта": [
        {"name": "Полиция", "address": "ул. Карла Маркса, 11, Ялта"},
    ],
}


MEDHELP = {
    "Севастополь": [{"name": "Первая помощь", "address": "наб. Парк Победы, 7, Севастополь"}],
    "Симферополь": [{"name": "Первая помощь", "address": "ул. Лизы Чайкиной, 5а, Симферополь"}],
    "Феодосия": [{"name": "Первая помощь", "address": "ул. Дзержинского, 4, п. г. т. Кировское, Феодосия"}],
    "Судак": [{"name": "Первая помощь", "address": "Восточное ш., 31, Судак"}],
    "Евпатория": [{"name": "Первая помощь", "address": "ул. Дмитрия Ульянова, 58, Евпатория"}],
    "Ялта": [{"name": "Первая помощь", "address": "ул. Пальмиро Тольятти, 16а, Ялта"}],
    "Алушта": [{"name": "Первая помощь", "address": "Партизанская ул., 3, Алушта"}],
}


# ================== Helpers ===================
def safe_float(x, default=0.0):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def score_place(row, user_tags: List[str], origin: Tuple[float, float], has_car: bool):
    s = safe_float(row.get("rating", 0)) * 10
    tags = set(map(str.strip, str(row.get("tags", "")).split(",")))
    common = tags.intersection(user_tags)
    s += 6 * len(common)
    dist = haversine_km(origin[0], origin[1], safe_float(row["lat"]), safe_float(row["lon"]))
    max_ok = 60 if has_car else 12
    if dist > max_ok:
        s -= (dist - max_ok) * 1.5
    else:
        s += 5
    return s

# ================== Weather ===================
WEATHER_CODES = {0: "ясно", 1: "облачно", 2: "переменная облачность", 3: "пасмурно", 61: "дождь", 80: "ливень"}

async def get_weather(city):
    lat, lon = CITIES_PRESETS.get(city, (44.9, 34.1))
    async with aiohttp.ClientSession() as s:
        try:
            wurl = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            r = await s.get(wurl)
            d = await r.json()
            w = d.get("current_weather", {})
            t = w.get("temperature", "?")
            v = w.get("windspeed", "?")
            c = WEATHER_CODES.get(w.get("weathercode"), "ясно")
            line = f"🌤 *{city}*\n{c}, {t}°C\n💨 {v} м/с"
        except:
            line = f"🌤 *{city}*\nПогода недоступна"
        if city in SEA_POINTS:
            lat2, lon2 = SEA_POINTS[city]
            try:
                surl = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat2}&longitude={lon2}&current=sea_surface_temperature"
                r2 = await s.get(surl)
                d2 = await r2.json()
                t2 = d2.get("current", {}).get("sea_surface_temperature")
                if t2:
                    line += f"\n🌊 {t2:.1f}°C"
            except:
                pass
    return line

# ================== UI ===================
def restart_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Начать заново", callback_data="restart")]])

def interests_kb(selected, city):
    items = INTERESTS if city in COASTAL_CITIES else [i for i in INTERESTS if i[0] != "море"]
    rows, row = [], []
    for key, label in items:
        mark = "✅ " if key in selected else ""
        row.append(InlineKeyboardButton(mark + label, callback_data=f"tag:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("🔙 Назад", callback_data="back_city"),
        InlineKeyboardButton("Готово ✅", callback_data="done"),
    ])
    return InlineKeyboardMarkup(rows)

# ================== Bot Flow ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton(c)] for c in CITIES_PRESETS]
    await update.message.reply_text(
    "Привет! 🚀\nЯ — AI Travel Crimea, твой карманный помощник в поездке по Крыму 🏝\n\nВыбери город, чтобы показать лучшие места и полезные локации поблизости 🌆",
    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
)

    return ASK_CITY

async def ask_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    if city not in CITIES_PRESETS:
        await update.message.reply_text("Выбери город из списка.")
        return ASK_CITY
    context.user_data["city"] = city
    context.user_data["origin"] = CITIES_PRESETS[city]
    context.user_data["tags"] = set()
    await update.message.reply_text(f"Отлично, {city}! Выбери интересы:", reply_markup=interests_kb(set(), city))
    return ASK_INTERESTS

async def handle_restart(query, context):
    await query.message.reply_text(
        "🔁 Начнём заново! Выбери город:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(c)] for c in CITIES_PRESETS], resize_keyboard=True),
    )
    return ASK_CITY  # важное: остаёмся в разговоре и ждём город

async def interests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    city = context.user_data.get("city", "")
    tags = context.user_data.get("tags", set())

    if data == "restart":
        return await handle_restart(query, context)
    if data == "back_city":
        return await handle_restart(query, context)

    if data.startswith("tag:"):
        tag = data.split(":", 1)[1]

        # 🚻 / 🏥 / 👮
        if tag == "туалеты":
            toilets = TOILETS.get(city, [])
            if not toilets:
                await query.message.reply_text("🚻 Нет данных для этого города.")
            else:
                for t in toilets:
                    link = f"https://yandex.ru/maps/?text={quote_plus(t['address'])}"
                    await query.message.reply_text(
                        f"🚻 {t['name']}\n{t['address']}\n[Открыть в Яндекс.Картах]({link})",
                        parse_mode="Markdown", disable_web_page_preview=True
                    )
            await query.message.reply_text("Хочешь начать заново?", reply_markup=restart_kb())
            return ASK_INTERESTS

        if tag == "медицина":
            for t in MEDHELP.get(city, []):
                link = f"https://yandex.ru/maps/?text={quote_plus(t['address'])}"
                await query.message.reply_text(
                    f"🏥 {t['name']}\n{t['address']}\n[Открыть в Яндекс.Картах]({link})",
                    parse_mode="Markdown", disable_web_page_preview=True
                )
            await query.message.reply_text("Хочешь начать заново?", reply_markup=restart_kb())
            return ASK_INTERESTS

        if tag == "полиция":
            for t in POLICE.get(city, []):
                link = f"https://yandex.ru/maps/?text={quote_plus(t['address'])}"
                await query.message.reply_text(
                    f"👮 {t['name']}\n{t['address']}\n[Открыть в Яндекс.Картах]({link})",
                    parse_mode="Markdown", disable_web_page_preview=True
                )
            await query.message.reply_text("Хочешь начать заново?", reply_markup=restart_kb())
            return ASK_INTERESTS

        # обычные интересы
        if tag in tags:
            tags.remove(tag)
        else:
            tags.add(tag)
        context.user_data["tags"] = tags
        await query.edit_message_text(
            f"Выбрано: {', '.join(tags) if tags else 'ничего'}",
            reply_markup=interests_kb(tags, city)
        )
        return ASK_INTERESTS

    if data == "done":
        if not tags:
            await query.answer("Выбери хотя бы один интерес 🙂", show_alert=True)
            return ASK_INTERESTS
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚗 Да", callback_data="car_yes")],
            [InlineKeyboardButton("🚶 Нет", callback_data="car_no")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart")],
        ])
        await query.edit_message_text("Есть автомобиль?", reply_markup=kb)
        return ASK_CAR

async def car_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = context.user_data["city"]
    tags = list(context.user_data["tags"])
    origin = context.user_data["origin"]
    has_car = query.data == "car_yes"

    await query.edit_message_text("⏳ Загружаю погоду и места...")
    weather = await get_weather(city)
    await query.message.reply_text(weather, parse_mode="Markdown")

    df_city = df[df["city"].astype(str).str.lower() == city.lower()].copy()
    if df_city.empty:
        await query.message.reply_text("Нет данных по этому городу.")
        return await handle_restart(query, context)

    # === Рассчёт скоринга ===
    df_city["score"] = df_city.apply(lambda r: score_place(r, tags, origin, has_car), axis=1)
    top = df_city.sort_values("score", ascending=False).head(5)

    # === Вывод карточек мест ===
    for _, r in top.iterrows():
        query_text = f"{r['name']} {r['city']}"
        yandex = f"https://yandex.ru/maps/?text={quote_plus(query_text)}"

        rating_val = r.get("rating")
        rating_val = 4.5 if pd.isna(rating_val) else float(rating_val)

        caption = (
            f"*{r['name']}* — {r['city']}\n"
            f"⭐ {rating_val:.1f} | _{r['tags']}_\n"
            f"[Открыть в Яндекс.Картах]({yandex})"
        )

        photo = str(r.get("photo", "")).strip()
        if photo.startswith("http"):
            try:
                await query.message.reply_photo(photo=photo, caption=caption, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Ошибка при отправке фото: {e}")
                await query.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await query.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)

    # === Конец: возвращаемся к выбору города ===
    await query.message.reply_text("Хочешь начать заново?", reply_markup=restart_kb())
    return ASK_CITY


# ================== Main ==================
def main():
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_interests)],
            ASK_INTERESTS: [CallbackQueryHandler(interests_callback)],
            ASK_CAR: [CallbackQueryHandler(car_callback)],
        },
        fallbacks=[CommandHandler("cancel", start)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # ❌ Больше НЕ добавляем внешний обработчик на "restart" — он ломал ре-энтри
    # app.add_handler(CallbackQueryHandler(interests_callback, pattern="^restart$"))

    app.run_polling()

if __name__ == "__main__":
    main()
