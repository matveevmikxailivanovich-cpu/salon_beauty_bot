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
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
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
                drop_pending_updates=True,
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
        sys.exit(1)
