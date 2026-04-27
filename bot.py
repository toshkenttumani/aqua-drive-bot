import asyncio
import logging
import sys
import re
import sqlite3
import pandas as pd
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramNetworkError

# Bot tokeningiz
TOKEN = "7968119666:AAE8DKrs4WHx8bPgciL17ry8SVogZIqRz3w"

# Ma'lumotlar bazasini sozlash
def init_db():
    try:
        conn = sqlite3.connect('payments.db')
        cursor = conn.cursor()
        # Bazani tozalab, yangi struktura bilan yaratamiz
        cursor.execute('DROP TABLE IF EXISTS transactions')
        cursor.execute('''
            CREATE TABLE transactions (
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

# Diqqat: Bu funksiya faqat bir marta - bot yangilanganda ishlaydi
# init_db()  # Serverda qo'lda ishga tushiramiz

dp = Dispatcher()

def parse_payment(text):
    try:
        # 1. Holatni aniqlash (🟢 yoki 🔴)
        status = "UNKNOWN"
        if "🟢" in text:
            status = "SUCCESS"
        elif "🔴" in text:
            status = "ERROR"
        
        # 2. Filial nomini topish (🔸 dan keyin)
        branch = "Noma'lum"
        branch_match = re.search(r"🔸\s*(.+)", text)
        if branch_match:
            branch = branch_match.group(1).strip()
            
        # 3. Summani topish (🇺🇿 dan keyin)
        amount = 0.0
        amount_match = re.search(r"🇺🇿\s*([\d,.]+)", text)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            if '.' in amount_str:
                amount_str = amount_str.split('.')[0]
            amount = float(amount_str)
            
        if branch != "Noma'lum" and amount > 0 and status != "UNKNOWN":
            return branch, amount, status
    except Exception as e:
        logging.error(f"Parsing error: {e}")
    return None, None, None

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Salom! AQUA DRIVE hisobot boti yangilandi.\n\n"
                         f"Endi bot 🟢 (Muvaffaqiyatli) va 🔴 (Xato) to'lovlarni alohida hisoblaydi.\n\n"
                         f"Buyruqlar:\n"
                         f"/stats - Umumiy\n"
                         f"/kunlik - Bugungi\n"
                         f"/hisobot - Excel")

def format_stats(df, title):
    if df.empty:
        return f"📊 **{title}:**\nHozircha ma'lumot yo'q."
    
    text = f"📊 **{title}:**\n\n"
    
    # SUCCESS
    success_df = df[df['status'] == 'SUCCESS']
    if not success_df.empty:
        text += "✅ **Muvaffaqiyatli tushumlar:**\n"
        total_s = 0
        for _, row in success_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_s += row['total']
        text += f"💰 **Jami muvaffaqiyatli:** {int(total_s):,} so'm\n\n"
    
    # ERROR
    error_df = df[df['status'] == 'ERROR']
    if not error_df.empty:
        text += "🔴 **Xatolar (Abonent topilmadi):**\n"
        total_e = 0
        for _, row in error_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_e += row['total']
        text += f"💰 **Jami xatolar:** {int(total_e):,} so'm\n"
        
    if success_df.empty and error_df.empty:
        return f"📊 **{title}:**\nMa'lumotlar topilmadi."
        
    return text

@dp.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, status, SUM(amount) as total FROM transactions GROUP BY branch, status", conn)
        conn.close()
        await message.answer(format_stats(df, "Umumiy statistika"), parse_mode="Markdown")
    except Exception as e:
        await message.answer("Xatolik.")

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
        await message.answer("Xatolik.")

@dp.message(Command("hisobot"))
async def report_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, amount, date, status FROM transactions ORDER BY date DESC", conn)
        conn.close()
        file_path = f"hisobot.xlsx"
        df.to_excel(file_path, index=False)
        await message.answer_document(FSInputFile(file_path), caption="Excel hisobot")
    except Exception as e:
        await message.answer("Excel xato.")

@dp.message(F.text.contains("AQUA DRIVE"))
async def payment_handler(message: Message) -> None:
    try:
        branch, amount, status = parse_payment(message.text)
        if branch and amount and status != "UNKNOWN":
            conn = sqlite3.connect('payments.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (branch, amount, date, status, raw_text) VALUES (?, ?, ?, ?, ?)",
                           (branch, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, message.text))
            conn.commit()
            conn.close()
            logging.info(f"Saqlandi: {branch} - {amount} - {status}")
    except Exception as e:
        logging.error(f"Save error: {e}")

async def main() -> None:
    while True:
        try:
            bot = Bot(token=TOKEN)
            await dp.start_polling(bot)
        except Exception as e:
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
