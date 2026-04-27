# Aqua Drive Telegram Bot

Ushbu bot guruhdagi tushumlar haqidagi xabarlarni tahlil qiladi, filiallar bo'yicha hisoblaydi va Excel hisobot yaratadi.

## Xususiyatlari
- `/stats` - Umumiy tushumlar statistikasi.
- `/kunlik` - Bugungi kunlik tushumlar.
- `/hisobot` - Barcha ma'lumotlarni Excel formatida yuklab olish.
- Avtomatik xabarlarni tahlil qilish (AQUA DRIVE formatidagi xabarlar uchun).

## O'rnatish (Ubuntu Server)

1. Loyihani klonlash:
```bash
git clone https://github.com/[YOUR_USERNAME]/aqua-drive-bot.git
cd aqua-drive-bot
```

2. Kerakli kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

3. Botni doimiy ishga tushirish (Systemd):
```bash
sudo cp bot.service /etc/systemd/system/bot.service
sudo systemctl daemon-reload
sudo systemctl enable bot
sudo systemctl start bot
```

4. Holatni tekshirish:
```bash
sudo systemctl status bot
```
