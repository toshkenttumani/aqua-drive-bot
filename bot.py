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
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'status' not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN status TEXT DEFAULT 'SUCCESS'")
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database init error: {e}")

init_db()

dp = Dispatcher()

def parse_payment(text):
    """
    Xabardan filial nomi, summa va holatni ajratib oladi.
    Aniqroq regex va qidiruv logikasi.
    """
    try:
        # Filial nomini qidirish (AQUA DRIVE so'zidan keyingi qism yoki maxsus belgi orqali)
        # 1-variant: 🔸 belgisidan keyingi qator
        branch_match = re.search(r"🔸\s*(AQUA DRIVE\s*\d*)", text, re.IGNORECASE)
        if not branch_match:
            # 2-variant: "Параметры оплаты:" dan keyingi qator
            branch_match = re.search(r"Параметры оплаты:\s*\n\s*🔸?\s*(.+)", text, re.IGNORECASE)
            
        # Summani qidirish (🇺🇿 belgisidan keyin yoki raqamlar formati orqali)
        amount_match = re.search(r"🇺🇿\s*([\d,.]+)", text)
        if not amount_match:
            amount_match = re.search(r"([\d,.]+)\s*сум", text, re.IGNORECASE)
        
        status = "UNKNOWN"
        # Holatni aniqlash - matnning istalgan joyida bo'lishi mumkin
        if "Успешно подтвержден" in text or "✅" in text:
            status = "SUCCESS"
        if "Абонент не найден" in text or "‼️" in text:
            status = "ERROR"
            
        if branch_match and amount_match:
            branch = branch_match.group(1).strip()
            # Summadagi barcha belgilarni (vergul, nuqta) tozalash
            amount_str = amount_match.group(1).replace(',', '')
            # Agar nuqtadan keyin 00 bo'lsa (masalan 10,000.00), ularni olib tashlash
            if '.' in amount_str:
                amount_str = amount_str.split('.')[0]
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
        return f"📊 **{title}:**\nHozircha ma'lumotlar yo'q."
    
    text = f"📊 **{title}:**\n\n"
    
    # SUCCESS statusdagilar
    success_df = df[df['status'] == 'SUCCESS']
    if not success_df.empty:
        text += "✅ **Muvaffaqiyatli tushumlar:**\n"
        total_s = 0
        # Filiallar bo'yicha guruhlash (agar SQLda qilinmagan bo'lsa)
        for _, row in success_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_s += row['total']
        text += f"💰 **Jami muvaffaqiyatli:** {int(total_s):,} so'm\n\n"
    else:
        text += "✅ Muvaffaqiyatli tushumlar: 0 so'm\n\n"
        
    # ERROR statusdagilar
    error_df = df[df['status'] == 'ERROR']
    if not error_df.empty:
        text += "‼️ **Xatolar (Abonent topilmadi):**\n"
        total_e = 0
        for _, row in error_df.iterrows():
            text += f"📍 {row['branch']}: {int(row['total']):,} so'm\n"
            total_e += row['total']
        text += f"💰 **Jami xatolar:** {int(total_e):,} so'm\n"
    else:
        text += "‼️ Xato to'lovlar: 0 so'm\n"
        
    return text

@dp.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        # Barcha vaqt uchun
        df = pd.read_sql_query("SELECT branch, status, SUM(amount) as total FROM transactions GROUP BY branch, status", conn)
        conn.close()
        await message.answer(format_stats(df, "Umumiy statistika"), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await message.answer("Statistikani hisoblashda xatolik.")

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
        logging.error(f"Daily stats error: {e}")
        await message.answer("Kunlik hisobotda xatolik.")

@dp.message(Command("hisobot"))
async def report_handler(message: Message) -> None:
    try:
        conn = sqlite3.connect('payments.db')
        df = pd.read_sql_query("SELECT branch, amount, date, status FROM transactions ORDER BY date DESC", conn)
        conn.close()
        
        if df.empty:
            await message.answer("Ma'lumotlar bazasi bo'sh.")
            return
            
        file_path = f"hisobot_{datetime.now().strftime('%Y%m%d')}.xlsx"
        df.to_excel(file_path, index=False)
        await message.answer_document(FSInputFile(file_path), caption="Barcha tranzaksiyalar (Excel)")
    except Exception as e:
        logging.error(f"Report error: {e}")
        await message.answer("Excel hisobot tayyorlashda xatolik.")

@dp.message(F.text.contains("AQUA DRIVE") | F.text.contains("confirm") | F.text.contains("подтвержден"))
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
            logging.info(f"Yozildi: {branch} - {amount} - {status}")
    except Exception as e:
        logging.error(f"Save error: {e}")

async def main() -> None:
    while True:
        try:
            bot = Bot(token=TOKEN)
            logging.info("Bot ishga tushdi...")
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
