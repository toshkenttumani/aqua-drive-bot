import asyncio
import logging
import sys
import re
import os
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from flask import Flask
from threading import Thread
import pymongo
import pandas as pd

# API TOKEN
TOKEN = "8649010974:AAHEuX5uDjRcBkY4oQs9PQdl0WVyZ2tNrUk"

# MongoDB ulanish (Tekin bulutli baza)
# DIQQAT: Bu yerga o'zingizning MongoDB linkiningizni qo'yishingiz mumkin
MONGO_URL = "mongodb+srv://admin:admin123@cluster0.mongodb.net/aqua_drive?retryWrites=true&w=majority"
# Eslatma: Agar yuqoridagi link ishlamasa, bot xotirada (RAM) saqlashga o'tadi
try:
    client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.aqua_drive
    collection = db.transactions
    client.server_info() # Tekshirish
    USE_MONGO = True
    logging.info("MongoDB-ga muvaffaqiyatli ulandi!")
except Exception as e:
    logging.error(f"MongoDB ulanish xatosi: {e}. Vaqtinchalik xotiraga o'tiladi.")
    USE_MONGO = False
    temp_db = []

# Render.com uchun Web Server
app = Flask('')
@app.route('/')
def home(): return "Bot is running with Cloud DB!"
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
    await m.answer("Salom! AQUA DRIVE Hisobot Boti (Cloud DB v3).\n\n/stats - Umumiy\n/kunlik - Bugungi\n/hisobot - Excel\n/reset - Tozalash")

def get_stats_text(rows, title):
    if not rows: return f"📊 {title}:\nMa'lumot yo'q."
    res = f"📊 {title}:\n\n"
    success = {}
    errors = {}
    for r in rows:
        b, s, a = r.get('branch', 'Noma\'lum'), r.get('status', 'UNKNOWN'), r.get('amount', 0)
        if s == 'SUCCESS': success[b] = success.get(b, 0) + a
        else: errors[b] = errors.get(b, 0) + a
    
    if success:
        res += "✅ Muvaffaqiyatli:\n"
        for b, a in success.items(): res += f"📍 {b}: {int(a):,} so'm\n"
        res += f"💰 Jami: {int(sum(success.values())):,} so'm\n\n"
    if errors:
        res += "🔴 Xatolar:\n"
        for b, a in errors.items(): res += f"📍 {b}: {int(a):,} so'm\n"
        res += f"💰 Jami: {int(sum(errors.values())):,} so'm\n"
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
        today = datetime.now().strftime("%Y-%m-%d")
        query = {"date": {"$regex": f"^{today}"}}
        rows = list(collection.find(query)) if USE_MONGO else [r for r in temp_db if r['date'].startswith(today)]
        await m.answer(get_stats_text(rows, f"Bugungi ({today})"), parse_mode="Markdown")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("reset"))
async def reset(m: Message):
    try:
        if USE_MONGO: collection.delete_many({})
        else: temp_db.clear()
        await m.answer("✅ Tozalandi!")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("hisobot"))
async def hisobot(m: Message):
    try:
        rows = list(collection.find()) if USE_MONGO else temp_db
        if not rows: return await m.answer("Ma'lumot yo'q.")
        df = pd.DataFrame(rows)
        if '_id' in df.columns: df.drop(columns=['_id'], inplace=True)
        path = "/tmp/report.xlsx"
        df.to_excel(path, index=False)
        await m.answer_document(FSInputFile(path), caption="Excel Hisobot")
    except Exception as e: await m.answer(f"Excel xatosi: {e}")

@dp.message(F.text.contains("AQUA DRIVE"))
async def handle_pay(m: Message):
    b, a, s = parse_payment(m.text)
    if a:
        data = {"branch": b, "amount": a, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": s}
        try:
            if USE_MONGO: collection.insert_one(data)
            else: temp_db.append(data)
            if m.chat.type == 'private': await m.answer(f"Saqlandi: {b} - {int(a):,} ({s})")
        except: pass

async def main():
    Thread(target=run_web).start()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
