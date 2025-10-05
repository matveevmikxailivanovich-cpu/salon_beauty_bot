# -*- coding: utf-8 -*-
"""
TELEGRAM-БОТ САЛОНА КРАСОТЫ ДЛЯ RENDER v2.2
Полностью рабочая версия
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List
import sqlite3
import signal

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
    print("✅ telegram OK")
except ImportError:
    print("❌ Install: pip install python-telegram-bot==20.7")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', "8215198856:AAFaeNBZnrKig1tU0VR74DoCTHdrXsRKV1U")
WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)
PORT = int(os.getenv('PORT', 8443))
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'

print(f"🤖 BOT v2.2 | Mode: {'Webhook' if USE_WEBHOOK else 'Polling'}")

shutdown_event = asyncio.Event()

class UserState:
    MAIN_MENU = "main_menu"
    SELECTING_SERVICE = "selecting_service"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PHONE = "awaiting_phone"

SERVICES = {
    "nails": {"name": "💅 Ногтевой сервис", "services": ["Маникюр - 1500₽", "Педикюр - 2000₽"], "duration": 90},
    "hair": {"name": "💇‍♀️ Парикмахерские", "services": ["Стрижка - 2500₽", "Окрашивание - 4500₽"], "duration": 120},
    "makeup": {"name": "💄 Макияж", "services": ["Брови - 8000₽", "Губы - 12000₽"], "duration": 150}
}

MASTERS = {
    "nails": ["Анна Иванова", "Мария Петрова"],
    "hair": ["Елена Сидорова", "Ольга Козлова"],
    "makeup": ["Светлана Николаева"]
}

WORK_HOURS = list(range(9, 19))
SALON_INFO = {"name": "Салон 'Элеганс'", "phone": "+7 (999) 123-45-67", "address": "ул. Красоты, 10"}

class Database:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', '/tmp/salon_bot.db')
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_type TEXT, master TEXT, appointment_date TEXT, appointment_time TEXT, status TEXT DEFAULT "active", created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON appointments(appointment_date)')
        conn.commit()
        conn.close()
        logger.info("✅ DB OK")
    
    def is_user_registered(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def register_user(self, user_id: int, name: str, phone: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, name, phone) VALUES (?, ?, ?)', (user_id, name, phone))
        conn.commit()
        conn.close()
        logger.info(f"👤 User {user_id} registered")
    
    def create_appointment(self, user_id: int, service_type: str, master: str, date: str, time: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO appointments (user_id, service_type, master, appointment_date, appointment_time) VALUES (?, ?, ?, ?, ?)', (user_id, service_type, master, date, time))
        aid = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"📅 Appointment #{aid}")
        return aid
    
    def get_user_appointments(self, user_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT service_type, master, appointment_date, appointment_time FROM appointments WHERE user_id = ? AND status = "active" ORDER BY appointment_date', (user_id,))
        appointments = cursor.fetchall()
        conn.close()
        return [{'service_type': a[0], 'master': a[1], 'date': a[2], 'time': a[3]} for a in appointments]
    
    def is_time_available(self, master: str, date: str, time: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM appointments WHERE master = ? AND appointment_date = ? AND appointment_time = ? AND status = "active"', (master, date, time))
        result = cursor.fetchone()
        conn.close()
        return result is None

db = Database()
user_states = {}
user_data = {}

class SalonBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"❌ {context.error}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        u = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM appointments WHERE status = "active"')
        a = cursor.fetchone()[0]
        conn.close()
        await update.message.reply_text(f"✅ OK | Users: {u} | Appointments: {a}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_states[user_id] = UserState.MAIN_MENU
        
        kb = [
            [InlineKeyboardButton("📅 Записаться", callback_data="book")],
            [InlineKeyboardButton("📋 Услуги", callback_data="services")],
            [InlineKeyboardButton("👩‍💻 Мастера", callback_data="masters")],
            [InlineKeyboardButton("📱 Мои записи", callback_data="my_bookings")]
        ]
        await update.message.reply_text(f"👋 {SALON_INFO['name']}\n📞 {SALON_INFO['phone']}", reply_markup=InlineKeyboardMarkup(kb))
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        
        try:
            if q.data == "services":
                await self.show_services(q)
            elif q.data == "book":
                await self.start_booking(q)
            elif q.data == "masters":
                await self.show_masters(q)
            elif q.data == "my_bookings":
                await self.show_bookings(q)
            elif q.data.startswith("service_"):
                await self.select_service(q, q.data)
            elif q.data.startswith("date_"):
                await self.select_date(q, q.data)
            elif q.data.startswith("time_"):
                await self.select_time(q, q.data)
            elif q.data == "back":
                await self.back_menu(q)
        except Exception as e:
            logger.error(f"❌ {e}")
    
    async def show_services(self, q):
        t = "📋 **Услуги**\n\n"
        for s in SERVICES.values():
            t += f"**{s['name']}**\n" + "\n".join(f"• {x}" for x in s['services']) + f"\n⏱ {s['duration']} мин\n\n"
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]), parse_mode='Markdown')
    
    async def show_masters(self, q):
        t = "👩‍💻 **Мастера**\n\n"
        for st, ms in MASTERS.items():
            t += f"**{SERVICES[st]['name']}:**\n" + "\n".join(f"• {m}" for m in ms) + "\n\n"
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]), parse_mode='Markdown')
    
    async def show_bookings(self, q):
        apps = db.get_user_appointments(q.from_user.id)
        if apps:
            t = "📱 **Ваши записи:**\n\n"
            for a in apps:
                d = datetime.strptime(a['date'], "%Y-%m-%d").strftime("%d.%m")
                t += f"• {SERVICES[a['service_type']]['name']}\n📅 {d} в {a['time']} • {a['master']}\n\n"
        else:
            t = "📱 Нет записей"
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]), parse_mode='Markdown')
    
    async def back_menu(self, q):
        user_states[q.from_user.id] = UserState.MAIN_MENU
        kb = [
            [InlineKeyboardButton("📅 Записаться", callback_data="book")],
            [InlineKeyboardButton("📋 Услуги", callback_data="services")],
            [InlineKeyboardButton("👩‍💻 Мастера", callback_data="masters")],
            [InlineKeyboardButton("📱 Мои записи", callback_data="my_bookings")]
        ]
        await q.edit_message_text("🏠 **Меню**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    async def start_booking(self, q):
        user_states[q.from_user.id] = UserState.SELECTING_SERVICE
        kb = [
            [InlineKeyboardButton("💅 Ногти", callback_data="service_nails")],
            [InlineKeyboardButton("💇‍♀️ Волосы", callback_data="service_hair")],
            [InlineKeyboardButton("💄 Макияж", callback_data="service_makeup")],
            [InlineKeyboardButton("🔙", callback_data="back")]
        ]
        await q.edit_message_text("📅 **Услуга:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    async def select_service(self, q, data):
        st = data.replace("service_", "")
        if q.from_user.id not in user_data:
            user_data[q.from_user.id] = {}
        user_data[q.from_user.id]['service_type'] = st
        
        s = SERVICES[st]
        t = f"**{s['name']}**\n\n" + "\n".join(f"• {x}" for x in s['services']) + f"\n\n⏱ {s['duration']} мин\n\n📅 **Дата:**"
        
        kb = []
        for i in range(1, 8):
            d = datetime.now() + timedelta(days=i)
            if d.weekday() < 6:
                ds = d.strftime("%Y-%m-%d")
                dd = d.strftime("%d.%m (%a)").replace('Mon','Пн').replace('Tue','Вт').replace('Wed','Ср').replace('Thu','Чт').replace('Fri','Пт').replace('Sat','Сб')
                kb.append([InlineKeyboardButton(dd, callback_data=f"date_{ds}")])
        kb.append([InlineKeyboardButton("🔙", callback_data="book")])
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    async def select_date(self, q, data):
        date = data.replace("date_", "")
        user_data[q.from_user.id]['date'] = date
        
        st = user_data[q.from_user.id]['service_type']
        ms = MASTERS[st]
        
        d = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m")
        t = f"📅 **{d}**\n⏰ **Время:**"
        
        kb = []
        for h in WORK_HOURS:
            tm = f"{h:02d}:00"
            if any(db.is_time_available(m, date, tm) for m in ms):
                kb.append([InlineKeyboardButton(tm, callback_data=f"time_{tm}")])
        
        kb.append([InlineKeyboardButton("🔙", callback_data=f"service_{st}")])
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    async def select_time(self, q, data):
        tm = data.replace("time_", "")
        user_data[q.from_user.id]['time'] = tm
        
        if not db.is_user_registered(q.from_user.id):
            user_states[q.from_user.id] = UserState.AWAITING_NAME
            await q.edit_message_text("📝 **Регистрация**\n\n👤 Введите имя:", parse_mode='Markdown')
        else:
            await self.confirm(q)
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        txt = update.message.text
        
        if uid not in user_states:
            await self.start_command(update, context)
            return
        
        st = user_states[uid]
        
        if st == UserState.AWAITING_NAME:
            user_data[uid]['name'] = txt.strip()
            user_states[uid] = UserState.AWAITING_PHONE
            await update.message.reply_text(f"👍 {txt}!\n📞 Введите телефон:")
        
        elif st == UserState.AWAITING_PHONE:
            user_data[uid]['phone'] = txt.strip()
            db.register_user(uid, user_data[uid]['name'], user_data[uid]['phone'])
            await self.complete(update)
    
    async def confirm(self, q):
        await self._finalize(q.from_user.id, q)
    
    async def complete(self, update):
        await self._finalize(update.effective_user.id, update)
        user_states[update.effective_user.id] = UserState.MAIN_MENU
    
    async def _finalize(self, uid, uq):
        st = user_data[uid]['service_type']
        dt = user_data[uid]['date']
        tm = user_data[uid]['time']
        
        ms = MASTERS[st]
        m = None
        for x in ms:
            if db.is_time_available(x, dt, tm):
                m = x
                break
        
        if m:
            db.create_appointment(uid, st, m, dt, tm)
            d = datetime.strptime(dt, "%Y-%m-%d").strftime("%d.%m")
            t = f"🎉 **ГОТОВО!**\n\n📅 {d} в {tm}\n👩‍💻 {m}\n💅 {SERVICES[st]['name']}\n\n📍 {SALON_INFO['address']}\n📞 {SALON_INFO['phone']}"
        else:
            t = "😔 Время занято"
        
        kb = [[InlineKeyboardButton("🏠", callback_data="back")]]
        
        if hasattr(uq, 'edit_message_text'):
            await uq.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await uq.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    async def run(self):
    logger.info("🤖 STARTING...")
    
    if USE_WEBHOOK:
        if not WEBHOOK_URL:
            raise ValueError("No WEBHOOK_URL")
        logger.info(f"🌐 Webhook: {WEBHOOK_URL}")
        await self.app.initialize()
        await self.app.start()
        await self.app.bot.set_webhook(url=WEBHOOK_URL)
        await self.app.run_webhook(listen="0.0.0.0", port=PORT, url_path="", webhook_url=WEBHOOK_URL)
    else:
        logger.info("🔄 Polling mode")
        # Используем run_polling вместо ручного управления
        await self.app.run_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )

def sig_handler(signum, frame):
    logger.info(f"📶 Signal {signum}")
    shutdown_event.set()

async def main():
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    
    logger.info("🎯 Init...")
    
    if not BOT_TOKEN:
        raise ValueError("No BOT_TOKEN")
    
    bot = SalonBot()
    await bot.run()

if __name__ == '__main__':
    logger.info("🚀 START")
    
    try:
        import telegram
        logger.info(f"✅ telegram {telegram.__version__}")
    except ImportError:
        logger.error("❌ No telegram lib")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"❌ {e}")
        sys.exit(1)

