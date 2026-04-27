import asyncio
import logging
import sys
import re
import sqlite3
import os
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from flask import Flask
from threading import Thread

# API TOKEN
TOKEN = "8649010974:AAHEuX5uDjRcBkY4oQs9PQdl0WVyZ2tNrUk"

# Render.com uchun oddiy Web Server
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"
def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Ma'lumotlar bazasini sozlash (Mutlaq yo'l bilan)
DB_PATH = os.path.join(os.getcwd(), 'payments.db')

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT,
                amount REAL,
                date TEXT,
                status TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logging.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logging.error(f"Database init error: {e}")

init_db()
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
    await m.answer("Salom! AQUA DRIVE Hisobot Boti.\n\n/stats - Umumiy\n/kunlik - Bugungi\n/hisobot - Excel\n/reset - Tozalash")

def get_stats_text(rows, title):
    if not rows: return f"📊 {title}:\nMa'lumot yo'q."
    res = f"📊 {title}:\n\n"
    success = {}
    errors = {}
    for b, s, a in rows:
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
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT branch, status, amount FROM transactions").fetchall()
        conn.close()
        await m.answer(get_stats_text(rows, "Umumiy Hisobot"), parse_mode="Markdown")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("kunlik"))
async def kunlik(m: Message):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT branch, status, amount FROM transactions WHERE date LIKE ?", (f"{today}%",)).fetchall()
        conn.close()
        await m.answer(get_stats_text(rows, f"Bugungi ({today})"), parse_mode="Markdown")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("reset"))
async def reset(m: Message):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM transactions")
        conn.commit()
        conn.close()
        await m.answer("✅ Tozalandi!")
    except Exception as e: await m.answer(f"Xato: {e}")

@dp.message(Command("hisobot"))
async def hisobot(m: Message):
    try:
        import pandas as pd
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        conn.close()
        if df.empty: return await m.answer("Ma'lumot yo'q.")
        path = "/tmp/report.xlsx"
        df.to_excel(path, index=False)
        await m.answer_document(FSInputFile(path), caption="Excel Hisobot")
    except Exception as e: await m.answer(f"Excel xatosi: {e}")

@dp.message(F.text.contains("AQUA DRIVE"))
async def handle_pay(m: Message):
    b, a, s = parse_payment(m.text)
    if a:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO transactions (branch, amount, date, status) VALUES (?, ?, ?, ?)",
                         (b, a, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), s))
            conn.commit()
            conn.close()
            if m.chat.type == 'private': await m.answer(f"Saqlandi: {b} - {int(a):,} ({s})")
        except: pass

async def main():
    Thread(target=run_web).start()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
