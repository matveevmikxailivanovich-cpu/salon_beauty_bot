# -*- coding: utf-8 -*-
"""
TELEGRAM-БОТ САЛОНА КРАСОТЫ ДЛЯ RENDER v2.0
Улучшенная версия с защитой от конфликтов и webhook поддержкой
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List
import sqlite3
import signal

# Проверка библиотеки
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
    print("✅ Библиотека telegram найдена")
except ImportError:
    print("❌ Установите: pip install python-telegram-bot==20.7")
    sys.exit(1)

# Настройка логирования для Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', "8215198856:AAFaeNBZnrKig1tU0VR74DoCTHdrXsRKV1U")
WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)  # Для webhook режима
PORT = int(os.getenv('PORT', 8443))  # Порт для webhook
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'

print("🤖 TELEGRAM-БОТ САЛОНА КРАСОТЫ v2.0")
print(f"🔑 Токен: {BOT_TOKEN[:20]}...")
print(f"🌐 Webhook: {'Включен' if USE_WEBHOOK else 'Отключен'}")

# Глобальная переменная для контроля завершения
shutdown_event = asyncio.Event()

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
        self.db_path = os.getenv('DATABASE_PATH', '/tmp/salon_bot.db')
        self.init_db()
        logger.info(f"💾 База данных готова: {self.db_path}")
    
    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
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
            
            # Создание индексов для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointments_master ON appointments(master)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointments_user ON appointments(user_id)')
            
            conn.commit()
            conn.close()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise
    
    def is_user_registered(self, user_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пользователя {user_id}: {e}")
            return False
    
    def register_user(self, user_id: int, name: str, phone: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO users (user_id, name, phone) VALUES (?, ?, ?)',
                (user_id, name, phone)
            )
            conn.commit()
            conn.close()
            logger.info(f"👤 Зарегистрирован пользователь: {name} (ID: {user_id})")
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации пользователя {user_id}: {e}")
    
    def create_appointment(self, user_id: int, service_type: str, master: str, date: str, time: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO appointments (user_id, service_type, master, appointment_date, appointment_time) VALUES (?, ?, ?, ?, ?)',
                (user_id, service_type, master, date, time)
            )
            appointment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"📅 Создана запись #{appointment_id}: {date} {time} для пользователя {user_id}")
            return appointment_id
        except Exception as e:
            logger.error(f"❌ Ошибка создания записи: {e}")
            return None
    
    def get_user_appointments(self, user_id: int) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT service_type, master, appointment_date, appointment_time 
                   FROM appointments 
                   WHERE user_id = ? AND status = "active"
                   ORDER BY appointment_date, appointment_time''',
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
        except Exception as e:
            logger.error(f"❌ Ошибка получения записей пользователя {user_id}: {e}")
            return []
    
    def is_time_available(self, master: str, date: str, time: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id FROM appointments 
                   WHERE master = ? AND appointment_date = ? AND appointment_time = ? AND status = "active"''',
                (master, date, time)
            )
            result = cursor.fetchone()
            conn.close()
            return result is None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступности времени: {e}")
            return False

# Глобальные переменные
db = Database()
user_states = {}
user_data = {}

class SalonBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        logger.info("⚙️ Обработчики настроены")
    
    def setup_handlers(self):
        # Основные обработчики
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик ошибок"""
        logger.error(f"❌ Исключение при обработке update: {context.error}")
        
        # Попытка уведомить пользователя об ошибке
        if update and update.effective_user:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="😔 Произошла техническая ошибка. Попробуйте команду /start",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи"""
        help_text = (
            f"🆘 **Помощь - {SALON_INFO['name']}**\n\n"
            f"**Доступные команды:**\n"
            f"/start - Главное меню\n"
            f"/help - Эта справка\n"
            f"/status - Статус бота\n\n"
            f"**Функции бота:**\n"
            f"📅 Запись на процедуры\n"
            f"📋 Просмотр услуг и цен\n"
            f"👩‍💻 Информация о мастерах\n"
            f"🎯 Актуальные акции\n"
            f"📱 Управление записями\n\n"
            f"📞 Техподдержка: {SALON_INFO['phone']}"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статуса бота"""
        try:
            # Проверка БД
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM appointments WHERE status = "active"')
            appointments_count = cursor.fetchone()[0]
            conn.close()
            
            status_text = (
                f"🤖 **Статус бота**\n\n"
                f"✅ Бот работает нормально\n"
                f"📊 Зарегистрировано пользователей: {users_count}\n"
                f"📅 Активных записей: {appointments_count}\n"
                f"🕐 Время сервера: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"💾 База данных: Подключена\n"
                f"🌐 Режим: {'Webhook' if USE_WEBHOOK else 'Polling'}"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса: {e}")
            status_text = f"❌ Ошибка получения статуса: {str(e)}"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "Гость"
        user_states[user_id] = UserState.MAIN_MENU
        
        logger.info(f"👋 Пользователь {username} (ID: {user_id}) запустил бота")
        
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
        
        logger.info(f"🔘 Callback: {data} от пользователя {user_id}")
        
        try:
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
            else:
                logger.warning(f"⚠️ Неизвестный callback: {data}")
                await query.edit_message_text("❓ Неизвестная команда. Попробуйте /start")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback {data}: {e}")
            try:
                await query.edit_message_text(
                    "😔 Произошла ошибка. Попробуйте /start",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
                    ]])
                )
            except:
                pass
    
    # Остальные методы остаются такими же, как в оригинальной версии
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
                available_dates.append(
