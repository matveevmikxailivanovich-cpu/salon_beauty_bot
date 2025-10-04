# -*- coding: utf-8 -*-
"""
TELEGRAM-БОТ САЛОНА КРАСОТЫ ДЛЯ RENDER v2.1 FIXED
Исправленная версия без синтаксических ошибок
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)
PORT = int(os.getenv('PORT', 8443))
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'

print("🤖 TELEGRAM-БОТ САЛОНА КРАСОТЫ v2.1")
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
            text = "📱 У вас нет активных записей\n\n📅 Хотите записаться?"
        
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
    
    async def run_webhook(self):
        """Запуск в режиме webhook"""
        try:
            if not WEBHOOK_URL:
                raise ValueError("WEBHOOK_URL не установлен для webhook режима")
            
            logger.info(f"🌐 Запуск в режиме webhook: {WEBHOOK_URL}")
            
            # Настройка webhook
            await self.application.initialize()
            await self.application.start()
            await self.application.bot.set_webhook(url=WEBHOOK_URL)
            
            # Запуск webhook сервера
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path="",
                webhook_url=WEBHOOK_URL
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска webhook: {e}")
            raise
    
    async def run_polling(self):
        """Запуск в режиме polling"""
        try:
            logger.info("🔄 Запуск в режиме polling")
            
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                drop_pending_updates=True,  # Пропускаем старые обновления
                allowed_updates=['message', 'callback_query']
            )
            
            # Мониторинг работы
            while not shutdown_event.is_set():
                await asyncio.sleep(60)
                logger.info("🔄 Бот работает...")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска polling: {e}")
            raise
        finally:
            await self.application.stop()
            await self.application.shutdown()
    
    async def run(self):
        """Основной метод запуска"""
        try:
            logger.info("🤖 БОТ ЗАПУЩЕН НА RENDER!")
            logger.info("📱 Проверьте в Telegram")
            logger.info(f"🌐 Режим: {'Webhook' if USE_WEBHOOK else 'Polling'}")
            
            if USE_WEBHOOK:
                await self.run_webhook()
            else:
                await self.run_polling()
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"📶 Получен сигнал {signum}, завершение работы...")
    shutdown_event.set()

async def main():
    """Главная функция"""
    try:
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("🎯 Инициализация Telegram-бота для Render...")
        logger.info(f"🐍 Python версия: {sys.version}")
        logger.info(f"📂 Рабочая директория: {os.getcwd()}")
        logger.info(f"💾 Путь к БД: {os.getenv('DATABASE_PATH', '/tmp/salon_bot.db')}")
        
        # Проверка критических переменных
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
            raise ValueError("❌ BOT_TOKEN не установлен или имеет значение по умолчанию")
        
        # Создание и запуск бота
        bot = SalonBot()
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка main(): {e}")
        sys.exit(1)
    finally:
        logger.info("🏁 Завершение работы бота")

if __name__ == '__main__':
    logger.info("🚀 СТАРТ TELEGRAM-БОТА НА RENDER...")
    
    # Проверка зависимостей при запуске
    try:
        import telegram
        logger.info(f"✅ python-telegram-bot версия: {telegram.__version__}")
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта telegram: {e}")
        sys.exit(1)
    
    # Запуск основной функции
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Принудительная остановка")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)", callback_data="back_to_menu")]]
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
        
        # Генерация дат (ИСПРАВЛЕНО!)
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
            text += "❌ **Нет доступных дат**"
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
            text += "\n❌ **Нет свободного времени**"
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
        
        try:
            if state == UserState.AWAITING_NAME:
                user_data[user_id]['name'] = text.strip()
                user_states[user_id] = UserState.AWAITING_PHONE
                
                await update.message.reply_text(
                    f"👍 Приятно познакомиться, {text}!\n📞 Введите номер телефона:"
                )
            
            elif state == UserState.AWAITING_PHONE:
                user_data[user_id]['phone'] = text.strip()
                
                db.register_user(user_id, user_data[user_id]['name'], user_data[user_id]['phone'])
                await self.complete_booking(update)
            
            else:
                # Неожиданное текстовое сообщение
                await update.message.reply_text(
                    "❓ Используйте кнопки меню или команду /start",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
                    ]])
                )
        except Exception as e:
            logger.error(f"❌ Ошибка обработки текста от {user_id}: {e}")
            await update.message.reply_text("😔 Произошла ошибка. Попробуйте /start")
    
    async def confirm_booking(self, query):
        user_id = query.from_user.id
        await self._finalize_booking(user_id, query)
    
    async def complete_booking(self, update):
        user_id = update.effective_user.id
        await self._finalize_booking(user_id, update)
        user_states[user_id] = UserState.MAIN_MENU
    
    async def _finalize_booking(self, user_id, update_or_query):
        try:
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
                appointment_id = db.create_appointment(user_id, service_type, available_master, date, time)
                
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
                
                if appointment_id:
                    logger.info(f"✅ Успешная запись #{appointment_id} для пользователя {user_id}")
            else:
                text = "😔 К сожалению, время уже занято. Выберите другое время."
                logger.warning(f"⚠️ Время {date} {time} недоступно для пользователя {user_id}")
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"❌ Ошибка финализации записи для {user_id}: {e}")
            error_text = "😔 Произошла ошибка при создании записи. Попробуйте еще раз."
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text(error_text, reply_markup=reply_markup)
            else:
                await update_or_query.message.reply_text(error_text, reply_markup=reply_markup)
    
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
        
        keyboard = [[InlineKeyboardButton("🔙 Назад
