import asyncio
import logging
import sys
import re
import os
import traceback
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from flask import Flask
from threading import Thread
import pymongo
import pandas as pd

# API TOKEN
TOKEN = "8649010974:AAHEuX5uDjRcBkY4oQs9PQdl0WVyZ2tNrUk"

# Foydalanuvchining shaxsiy MongoDB ulanish linki
MONGO_URL = "mongodb+srv://toshkenttumanuyushma_db_user:dilshodjon1@cluster0.efanu1g.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.aqua_drive
    collection = db.transactions
    # Ulanishni tekshirish
    client.server_info()
    USE_MONGO = True
    logging.info("Shaxsiy MongoDB-ga muvaffaqiyatli ulandi!")
except Exception as e:
    logging.error(f"MongoDB Error: {e}")
    USE_MONGO = False
    temp_db = []

def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

app = Flask('')
@app.route('/')
def home(): return f"Bot is active with Private Cloud DB. Time: {get_uzb_time().strftime('%Y-%m-%d %H:%M:%S')}"
def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

dp = Dispatcher()

def parse_payment(text):
    try:
        status = "SUCCESS" if "🟢" in text or "Успешно" in text else "ERROR" if "🔴" in text or "Абонент не найден" in text else "UNKNOWN"
        branch = "Noma'lum"
        branch_match = re.search(r"🔸\s*(.+)", text) or re.search(r"AQUA DRIVE \d+", text)
        if branch_match:
            branch = branch_match.group(1).strip() if "🔸" in text else branch_match.group(0).strip()
        amount = 0.0
        amount_match = re.search(r"🇺🇿\s*([\d,.]+)", text)
        if amount_match:
            amount = float(amount_match.group(1).replace(',', '').split('.')[0])
        return branch, amount, status
    except: return None, None, None

@dp.message(CommandStart())
async def start(m: Message):
    uzb_now = get_uzb_time().strftime("%Y-%m-%d %H:%M:%S")
    await m.answer(f"AQUA DRIVE Hisobot Boti (Private Cloud DB)\n"
                   f"Hozirgi vaqt: {uzb_now}\n\n"
                   f"/stats - Umumiy (Barcha vaqt)\n"
                   f"/kunlik - Bugungi hisobot\n"
                   f"/hisobot - Excel (Barcha ma'lumotlar)\n"
                   f"/reset - Bazani tozalash")

def get_stats_text(rows, title):
    if not rows: return f"📊 {title}:\nMa'lumot topilmadi."
    res = f"📊 {title}:\n\n"
    success = {}
    errors = {}
    for r in rows:
        b, s, a = r.get('branch', 'Noma\'lum'), r.get('status', 'UNKNOWN'), r.get('amount', 0)
        if s == 'SUCCESS': success[b] = success.get(b, 0) + a
        else: errors[b] = errors.get(b, 0) + a
    
    if success:
        res += "✅ **Muvaffaqiyatli:**\n"
        for b, a in success.items(): res += f"📍 {b}: {int(a):,} so'm\n"
        res += f"💰 **Jami:** {int(sum(success.values())):,} so'm\n\n"
    if errors:
        res += "🔴 **Xatolar:**\n"
        for b, a in errors.items(): res += f"📍 {b}: {int(a):,} so'm\n"
        res += f"💰 **Jami:** {int(sum(errors.values())):,} so'm\n"
    return res

@dp.message(Command("stats"))
async def stats(m: Message):
    try:
        rows = list(collection.find()) if USE_MONGO else temp_db
        await m.answer(get_stats_text(rows, "Umumiy Hisobot"), parse_mode="Markdown")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("kunlik"))
async def kunlik(m: Message):
    try:
        today = get_uzb_time().strftime("%Y-%m-%d")
        query = {"date": {"$regex": f"^{today}"}}
        rows = list(collection.find(query)) if USE_MONGO else [r for r in temp_db if r['date'].startswith(today)]
        await m.answer(get_stats_text(rows, f"Bugungi ({today})"), parse_mode="Markdown")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("reset"))
async def reset(m: Message):
    try:
        if USE_MONGO: collection.delete_many({})
        else: temp_db.clear()
        await m.answer("✅ Barcha ma'lumotlar shaxsiy bulutli bazadan tozalandi!")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("hisobot"))
async def hisobot(m: Message):
    try:
        rows = list(collection.find({}, {'_id': 0})) if USE_MONGO else temp_db
        if not rows: return await m.answer("Ma'lumot yo'q.")
        df = pd.DataFrame(rows)
        path = "/tmp/report.xlsx"
        df.to_excel(path, index=False)
        await m.answer_document(FSInputFile(path), caption="Excel Hisobot (Shaxsiy bulutli bazadan)")
    except Exception as e: await m.answer(f"Excel xatosi: {e}")

@dp.message(F.text.contains("AQUA DRIVE"))
async def handle_pay(m: Message):
    b, a, s = parse_payment(m.text)
    if a:
        data = {"branch": b, "amount": a, "date": get_uzb_time().strftime("%Y-%m-%d %H:%M:%S"), "status": s}
        try:
            if USE_MONGO: collection.insert_one(data)
            else: temp_db.append(data)
            if m.chat.type == 'private':
                await m.answer(f"✅ Saqlandi: {b} - {int(a):,} ({s})")
        except Exception as e:
            logging.error(f"Save error: {e}")

async def main():
    Thread(target=run_web).start()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
