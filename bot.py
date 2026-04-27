import asyncio
import logging
import sys
import re
import sqlite3
import pandas as pd
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from flask import Flask
from threading import Thread

# API TOKEN
TOKEN = "8649010974:AAHEuX5uDjRcBkY4oQs9PQdl0WVyZ2tNrUk"

# Render.com uchun oddiy Web Server (Health Check uchun)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# Ma'lumotlar bazasini sozlash
def init_db():
    try:
        conn = sqlite3.connect('payments.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT,
                amount REAL,
                date TEXT,
                status TEXT,
                raw_text TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database init error: {e}")

init_db()

dp = Dispatcher()

def parse_payment(text):
    try:
        status = "UNKNOWN"
        if "🟢" in text:
            status = "SUCCESS"
        elif "🔴" in text:
            status = "ERROR"
        
        branch = "Noma'lum"
        branch_match = re.search(r"🔸\s*(.+)", text)
        if not branch_match:
            branch_match = re.search(r"Параметры оплаты:\s*\n\s*(.+)", text)
        if branch_match:
            branch = branch_match.group(1).strip()
            
        amount = 0.0
        amount_match = re.search(r"🇺🇿\s*([\d,.]+)", text)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            if '.' in amount_str:
                amount_str = amount_str.split('.')[0]
            amount = float(amount_str)
            
        if branch != "Noma'lum" and amount > 0:
            return branch, amount, status
    except Exception as e:
        logging.error(f"Parsing error: {e}")
    return None, None, None

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Salom! AQUA DRIVE hisobot boti (Render versiya).\n\n"
                         f"Buyruqlar:\n"
                         f"/stats - Umumiy statistika\n"
                         f"/kunlik - Bugungi statistika\n"
                         f"/hisobot - Excel hisobot\n"
                         f"/reset - Bazani tozalash")

def format_stats(df, title):
    if df.empty:
        return f"📊 **{title}:**\nHozircha ma'lumot yo'q."
    
    text = f"📊 **{title}:**\n\n"
    
    success_df = df[df['status'] == 'SUCCESS']
    if not success_df.empty:
        text += "✅ **Muvaffaqiyatli tushumlar:**\n"
        total_s = 0
        for _, row in success_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_s += row['total']
        text += f"💰 **Jami muvaffaqiyatli:** {int(total_s):,} so'm\n\n"
    
    error_df = df[df['status'] == 'ERROR']
    if not error_df.empty:
        text += "🔴 **Xatolar (Abonent topilmadi):**\n"
        total_e = 0
        for _, row in error_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_e += row['total']
        text += f"💰 **Jami xatolar:** {int(total_e):,} so'm\n"
        
    return text

@dp.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, status, SUM(amount) as total FROM transactions GROUP BY branch, status", conn)
        conn.close()
        await message.answer(format_stats(df, "Umumiy statistika"), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"Statistika olishda xato.")

@dp.message(Command("kunlik"))
async def daily_stats_handler(message: Message) -> None:
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect('payments.db')
        query = f"SELECT branch, status, SUM(amount) as total FROM transactions WHERE date LIKE '{today}%' GROUP BY branch, status"
        df = pd.read_sql_query(query, conn)
        conn.close()
        await message.answer(format_stats(df, f"Bugungi hisobot ({today})"), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"Kunlik hisobotda xato.")

@dp.message(Command("hisobot"))
async def report_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, amount, date, status FROM transactions ORDER BY date DESC", conn)
        conn.close()
        if df.empty:
            await message.answer("Hozircha ma'lumot yo'q.")
            return
        file_path = f"hisobot.xlsx"
        df.to_excel(file_path, index=False)
        await message.answer_document(FSInputFile(file_path), caption="Excel hisobot")
    except Exception as e:
        await message.answer(f"Excel yaratishda xato.")

@dp.message(Command("reset"))
async def reset_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions")
        conn.commit()
        conn.close()
        await message.answer("✅ Ma'lumotlar bazasi muvaffaqiyatli tozalandi!")
    except Exception as e:
        await message.answer(f"Tozalashda xato.")

@dp.message(F.text.contains("AQUA DRIVE"))
async def payment_handler(message: Message) -> None:
    try:
        branch, amount, status = parse_payment(message.text)
        if branch and amount:
            conn = sqlite3.connect('payments.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (branch, amount, date, status, raw_text) VALUES (?, ?, ?, ?, ?)",
                           (branch, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, message.text))
            conn.commit()
            conn.close()
            logging.info(f"Saqlandi: {branch} - {amount} - {status}")
    except Exception as e:
        logging.error(f"Save error: {traceback.format_exc()}")

async def main() -> None:
    logging.info("Bot ishga tushmoqda...")
    # Web serverni alohida oqimda ishga tushirish
    Thread(target=run_web).start()
    
    bot = Bot(token=TOKEN)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Critical error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())
