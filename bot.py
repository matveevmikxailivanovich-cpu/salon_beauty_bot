# -*- coding: utf-8 -*-
"""
TELEGRAM-БОТ САЛОНА КРАСОТЫ
Версия для Render
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List
import sqlite3

# Проверка библиотеки
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
    print("✅ Библиотека telegram найдена")
except ImportError:
    print("❌ Установите: pip install python-telegram-bot==20.3")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ ТОКЕН ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ Ошибка: переменная окружения BOT_TOKEN не найдена!")
    sys.exit(1)

print("🤖 ЗАПУСК БОТА САЛОНА КРАСОТЫ")
print("🔑 Токен загружен из переменной окружения")

# Состояния
class UserState:
    MAIN_MENU = "main_menu"
    SELECTING_SERVICE = "selecting_service"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PHONE = "awaiting_phone"

# Настройки салона
SERVICES = {
    "nails": {
        "name": "💅 Ногтевой сервис",
        "services": ["Маникюр - 1500₽", "Педикюр - 2000₽", "Гель-лак - 1200₽"],
        "duration": 90
    },
    "hair": {
        "name": "💇‍♀️ Парикмахерские услуги", 
        "services": ["Стрижка женская - 2500₽", "Окрашивание - 4500₽", "Укладка - 1500₽"],
        "duration": 120
    },
    "makeup": {
        "name": "💄 Перманентный макияж",
        "services": ["Брови - 8000₽", "Губы - 12000₽", "Веки - 10000₽"],
        "duration": 150
    }
}

MASTERS = {
    "nails": ["Анна Иванова", "Мария Петрова"],
    "hair": ["Елена Сидорова", "Ольга Козлова"],
    "makeup": ["Светлана Николаева"]
}

WORK_HOURS = list(range(9, 19))

SALON_INFO = {
    "name": "Салон красоты 'Элеганс'",
    "phone": "+7 (999) 123-45-67", 
    "address": "ул. Красоты, дом 10"
}

class Database:
    def __init__(self):
        self.init_db()
        print("💾 База данных готова")
    
    def init_db(self):
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                master TEXT,
                appointment_date TEXT,
                appointment_time TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def is_user_registered(self, user_id: int) -> bool:
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def register_user(self, user_id: int, name: str, phone: str):
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO users (user_id, name, phone) VALUES (?, ?, ?)',
            (user_id, name, phone)
        )
        conn.commit()
        conn.close()
        print(f"👤 Зарегистрирован: {name}")
    
    def create_appointment(self, user_id: int, service_type: str, master: str, date: str, time: str):
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO appointments (user_id, service_type, master, appointment_date, appointment_time) VALUES (?, ?, ?, ?, ?)',
            (user_id, service_type, master, date, time)
        )
        conn.commit()
        conn.close()
        print(f"📅 Запись создана: {date} {time}")
    
    def get_user_appointments(self, user_id: int) -> List[Dict]:
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT service_type, master, appointment_date, appointment_time FROM appointments WHERE user_id = ? AND status = "active"',
            (user_id,)
        )
        appointments = cursor.fetchall()
        conn.close()
        
        result = []
        for apt in appointments:
            result.append({
                'service_type': apt[0],
                'master': apt[1],
                'date': apt[2],
                'time': apt[3]
            })
        return result
    
    def is_time_available(self, master: str, date: str, time: str) -> bool:
        conn = sqlite3.connect('salon_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM appointments WHERE master = ? AND appointment_date = ? AND appointment_time = ? AND status = "active"',
            (master, date, time)
        )
        result = cursor.fetchone()
        conn.close()
        return result is None

# Глобальные переменные
db = Database()
user_states = {}
user_data = {}

class SalonBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        print("⚙️ Обработчики настроены")
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
    
    async def keep_alive_ping(self):
        """Keep-alive для бесплатного плана Render"""
        while True:
            await asyncio.sleep(600)  # Каждые 10 минут
            print(f"⏰ Keep-alive ping: {datetime.now()}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "Гость"
        user_states[user_id] = UserState.MAIN_MENU
        
        print(f"👋 Пользователь: {username}")
        
        welcome_text = (
            f"👋 Добро пожаловать в {SALON_INFO['name']}, {username}!\n\n"
            f"🌟 Я помогу вам:\n"
            f"📅 Записаться на процедуру\n"
            f"📋 Узнать цены\n"
            f"👩‍💻 Познакомиться с мастерами\n\n"
            f"📍 {SALON_INFO['address']}\n"
            f"📞 {SALON_INFO['phone']}\n\n"
            f"Что вас интересует?"
        )
        
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="book")],
            [InlineKeyboardButton("📋 Услуги и цены", callback_data="services")],
            [InlineKeyboardButton("👩‍💻 Наши мастера", callback_data="masters")],
            [InlineKeyboardButton("🎯 Акции", callback_data="promotions")],
            [InlineKeyboardButton("📱 Мои записи", callback_data="my_bookings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        print(f"🔘 Нажата кнопка: {data}")
        
        if data == "services":
            await self.show_services(query)
        elif data == "book":
            await self.start_booking(query)
        elif data == "masters":
            await self.show_masters(query)
        elif data == "promotions":
            await self.show_promotions(query)
        elif data == "my_bookings":
            await self.show_user_bookings(query)
        elif data.startswith("service_"):
            await self.select_service(query, data)
        elif data.startswith("date_"):
            await self.select_date(query, data)
        elif data.startswith("time_"):
            await self.select_time(query, data)
        elif data == "back_to_menu":
            await self.back_to_main_menu(query)
    
    async def show_services(self, query):
        text = f"📋 **Услуги {SALON_INFO['name']}**\n\n"
        
        for service_info in SERVICES.values():
            text += f"**{service_info['name']}**\n"
            for service in service_info['services']:
                text += f"• {service}\n"
            text += f"⏱ {service_info['duration']} мин\n\n"
        
        text += f"📞 {SALON_INFO['phone']}\n"
        text += f"📍 {SALON_INFO['address']}"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def start_booking(self, query):
        user_id = query.from_user.id
        user_states[user_id] = UserState.SELECTING_SERVICE
        
        text = "📅 **Выберите услугу:**"
        
        keyboard = [
            [InlineKeyboardButton("💅 Ногтевой сервис", callback_data="service_nails")],
            [InlineKeyboardButton("💇‍♀️ Парикмахерские услуги", callback_data="service_hair")],
            [InlineKeyboardButton("💄 Перманентный макияж", callback_data="service_makeup")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def select_service(self, query, callback_data):
        user_id = query.from_user.id
        service_type = callback_data.replace("service_", "")
        
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['service_type'] = service_type
        
        service_info = SERVICES[service_type]
        text = f"**{service_info['name']}**\n\n"
        for service in service_info['services']:
            text += f"• {service}\n"
        text += f"\n⏱ {service_info['duration']} мин\n\n"
        
        # Генерация дат
        available_dates = []
        for i in range(1, 8):
            date = datetime.now() + timedelta(days=i)
            if date.weekday() < 6:  # Пн-Сб
                available_dates.append(date)
        
        if available_dates:
            text += "📅 **Выберите дату:**"
            keyboard = []
            for date in available_dates:
                date_str = date.strftime("%Y-%m-%d")
                date_display = date.strftime("%d.%m (%a)")
                days = {'Mon': 'Пн', 'Tue': 'Вт', 'Wed': 'Ср', 'Thu': 'Чт', 'Fri': 'Пт', 'Sat': 'Сб'}
                for eng, rus in days.items():
                    date_display = date_display.replace(eng, rus)
                keyboard.append([InlineKeyboardButton(date_display, callback_data=f"date_{date_str}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="book")])
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            text += "❌ **Нет дат**"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def select_date(self, query, callback_data):
        user_id = query.from_user.id
        selected_date = callback_data.replace("date_", "")
        user_data[user_id]['date'] = selected_date
        
        service_type = user_data[user_id]['service_type']
        masters = MASTERS[service_type]
        
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        text = f"📅 **{formatted_date}**\n⏰ **Выберите время:**"
        
        keyboard = []
        for hour in WORK_HOURS:
            time_str = f"{hour:02d}:00"
            available = any(db.is_time_available(master, selected_date, time_str) for master in masters)
            if available:
                keyboard.append([InlineKeyboardButton(time_str, callback_data=f"time_{time_str}")])
        
        if keyboard:
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"service_{service_type}")])
        else:
            text += "\n❌ **Нет времени**"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f"service_{service_type}")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def select_time(self, query, callback_data):
        user_id = query.from_user.id
        selected_time = callback_data.replace("time_", "")
        user_data[user_id]['time'] = selected_time
        
        if not db.is_user_registered(user_id):
            user_states[user_id] = UserState.AWAITING_NAME
            
            text = (
                f"📝 **Для записи нужна регистрация**\n\n"
                f"👤 Введите ваше имя:"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await self.confirm_booking(query)
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        if user_id not in user_states:
            await self.start_command(update, context)
            return
        
        state = user_states[user_id]
        
        if state == UserState.AWAITING_NAME:
            user_data[user_id]['name'] = text.strip()
            user_states[user_id] = UserState.AWAITING_PHONE
            
            await update.message.reply_text(f"👍 Приятно познакомиться, {text}!\n📞 Введите номер телефона:")
        
        elif state == UserState.AWAITING_PHONE:
            user_data[user_id]['phone'] = text.strip()
            
            db.register_user(user_id, user_data[user_id]['name'], user_data[user_id]['phone'])
            await self.complete_booking(update)
    
    async def confirm_booking(self, query):
        user_id = query.from_user.id
        await self._finalize_booking(user_id, query)
    
    async def complete_booking(self, update):
        user_id = update.effective_user.id
        await self._finalize_booking(user_id, update)
        user_states[user_id] = UserState.MAIN_MENU
    
    async def _finalize_booking(self, user_id, update_or_query):
        service_type = user_data[user_id]['service_type']
        date = user_data[user_id]['date']
        time = user_data[user_id]['time']
        
        masters = MASTERS[service_type]
        available_master = None
        for master in masters:
            if db.is_time_available(master, date, time):
                available_master = master
                break
        
        if available_master:
            db.create_appointment(user_id, service_type, available_master, date, time)
            
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d.%m.%Y")
            
            text = (
                f"🎉 **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
                f"📅 Дата: {formatted_date}\n"
                f"⏰ Время: {time}\n"
                f"👩‍💻 Мастер: {available_master}\n"
                f"💅 Услуга: {SERVICES[service_type]['name']}\n\n"
                f"📍 {SALON_INFO['address']}\n"
                f"📞 {SALON_INFO['phone']}\n\n"
                f"✨ Ждем вас!"
            )
        else:
            text = "😔 Время занято. Выберите другое."
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update_or_query, 'edit_message_text'):
            await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_masters(self, query):
        text = f"👩‍💻 **Мастера {SALON_INFO['name']}:**\n\n"
        
        for service_type, masters in MASTERS.items():
            service_name = SERVICES[service_type]['name']
            text += f"**{service_name}:**\n"
            for master in masters:
                text += f"• {master}\n"
            text += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_promotions(self, query):
        text = (
            f"🎯 **Акции {SALON_INFO['name']}:**\n\n"
            f"🌟 Скидка 20% на первое посещение\n"
            f"💅 Маникюр + педикюр = скидка 15%\n"
            f"👯‍♀️ Приведи подругу - скидка 10%\n"
            f"🎂 В день рождения - скидка 25%\n\n"
            f"📞 Подробности: {SALON_INFO['phone']}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_user_bookings(self, query):
        user_id = query.from_user.id
        appointments = db.get_user_appointments(user_id)
        
        if appointments:
            text = "📱 **Ваши записи:**\n\n"
            for apt in appointments:
                service_name = SERVICES[apt['service_type']]['name']
                date_obj = datetime.strptime(apt['date'], "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d.%m.%Y")
                
                text += f"• {service_name}\n"
                text += f"📅 {formatted_date} в {apt['time']}\n"
                text += f"👩‍💻 {apt['master']}\n\n"
            
            text += f"📞 Для изменения: {SALON_INFO['phone']}"
        else:
            text = "📱 У вас нет записей\n\n📅 Хотите записаться?"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def back_to_main_menu(self, query):
        user_id = query.from_user.id
        user_states[user_id] = UserState.MAIN_MENU
        
        text = f"🏠 **Главное меню {SALON_INFO['name']}**\n\nВыберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="book")],
            [InlineKeyboardButton("📋 Услуги и цены", callback_data="services")],
            [InlineKeyboardButton("👩‍💻 Наши мастера", callback_data="masters")],
            [InlineKeyboardButton("🎯 Акции", callback_data="promotions")],
            [InlineKeyboardButton("📱 Мои записи", callback_data="my_bookings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    def run(self):
        print("🤖 БОТ ЗАПУЩЕН!")
        print("📱 Проверьте в Telegram")
        print("🔄 Для остановки: Ctrl+C")
        
        # Запуск keep-alive
        async def start_bot():
            await asyncio.gather(
                self.keep_alive_ping(),
                self.application.run_polling()
            )
        
        asyncio.run(start_bot())

def main():
    try:
        print("🎯 Инициализация...")
        bot = SalonBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n⏹️ Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.exception("Критическая ошибка:")

if __name__ == '__main__':
    print("🚀 ЗАПУСК БОТА...")
    main()
