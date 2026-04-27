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
        # status ustunini qo'shish (SUCCESS yoki ERROR)
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
        # Agar jadval oldindan mavjud bo'lsa va status ustuni bo'lmasa, uni qo'shamiz
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'status' not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN status TEXT DEFAULT 'SUCCESS'")
            
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database init error: {e}")

init_db()

# Dispatcher yaratish
dp = Dispatcher()

def parse_payment(text):
    """
    Xabardan filial nomi, summa va holatni ajratib oladi
    """
    try:
        # Filial nomini topish
        branch_match = re.search(r"Параметры оплаты:\s*\n\s*🔸\s*(.+)", text)
        # Summani topish
        amount_match = re.search(r"🇺🇿\s*([\d,.]+)", text)
        
        status = "UNKNOWN"
        if "✅ Успешно подтвержден" in text:
            status = "SUCCESS"
        elif "‼️ Абонент не найден" in text:
            status = "ERROR"
            
        if branch_match and amount_match:
            branch = branch_match.group(1).strip()
            amount_str = amount_match.group(1).replace(',', '')
            amount = float(amount_str)
            return branch, amount, status
    except Exception as e:
        logging.error(f"Parsing error: {e}")
    return None, None, None

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Salom! Men tushumlarni hisoblovchi botman.\n\n"
                         f"Buyruqlar:\n"
                         f"/stats - Umumiy hisob-kitob\n"
                         f"/kunlik - Bugungi hisob-kitob\n"
                         f"/hisobot - Excel hisobot")

def format_stats(df, title):
    if df.empty:
        return f"{title}:\nMa'lumotlar yo'q.\n"
    
    text = f"📊 **{title}:**\n\n"
    
    # Muvaffaqiyatli to'lovlar
    success_df = df[df['status'] == 'SUCCESS']
    if not success_df.empty:
        text += "✅ **Muvaffaqiyatli:**\n"
        total_s = 0
        for _, row in success_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_s += row['total']
        text += f"💰 Jami: {int(total_s):,} so'm\n\n"
        
    # Xato to'lovlar
    error_df = df[df['status'] == 'ERROR']
    if not error_df.empty:
        text += "❌ **Xatolar (Abonent topilmadi):**\n"
        total_e = 0
        for _, row in error_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_e += row['total']
        text += f"💰 Jami: {int(total_e):,} so'm\n"
        
    return text

@dp.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, status, SUM(amount) as total FROM transactions GROUP BY branch, status", conn)
        conn.close()
        
        text = format_stats(df, "Umumiy tushumlar (Barcha vaqt)")
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await message.answer("Xatolik yuz berdi.")

@dp.message(Command("kunlik"))
async def daily_stats_handler(message: Message) -> None:
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect('payments.db')
        query = f"SELECT branch, status, SUM(amount) as total FROM transactions WHERE date LIKE '{today}%' GROUP BY branch, status"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        text = format_stats(df, f"Bugungi tushumlar ({today})")
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Daily stats error: {e}")
        await message.answer("Xatolik yuz berdi.")

@dp.message(Command("hisobot"))
async def report_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, amount, date, status FROM transactions", conn)
        conn.close()
        
        if df.empty:
            await message.answer("Hisobot uchun ma'lumotlar yetarli emas.")
            return
        
        file_path = f"hisobot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(file_path, index=False)
        
        excel_file = FSInputFile(file_path)
        await message.answer_document(excel_file, caption="Barcha tushumlar va xatolar haqida Excel hisobot")
    except Exception as e:
        logging.error(f"Report error: {e}")
        await message.answer("Excel fayl yaratishda xatolik yuz berdi.")

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
            logging.info(f"Saved: {branch} - {amount} ({status})")
    except Exception as e:
        logging.error(f"Payment save error: {e}")

async def main() -> None:
    while True:
        try:
            bot = Bot(token=TOKEN)
            logging.info("Bot ishga tushmoqda...")
            await dp.start_polling(bot)
        except TelegramNetworkError:
            logging.warning("Tarmoq xatosi, 5 soniyadan so'ng qayta uriniladi...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Kutilmagan xato: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    asyncio.run(main())
