# -*- coding: utf-8 -*-
"""
ГЛАВНЫЙ ФАЙЛ ДЛЯ ЗАПУСКА БОТА НА RENDER
Интегрирует веб-сервер и Telegram-бота
"""

import os
from keep_alive import keep_alive
from bot import SalonBot

def main():
    print("="*50)
    print("🚀 ЗАПУСК БОТА САЛОНА КРАСОТЫ")
    print("="*50)
    
    # Проверка токена
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ ОШИБКА: Токен бота не найден!")
        print("📝 Добавьте BOT_TOKEN в Environment Variables")
        return
    
    print("✅ Токен загружен")
    
    # Запуск веб-сервера для поддержания активности
    keep_alive()
    
    # Запуск Telegram-бота
    try:
        print("\n🤖 Инициализация Telegram-бота...")
        bot = SalonBot()
        print("✅ Бот инициализирован")
        print("\n📱 Бот готов к работе!")
        print("🔗 Откройте бота в Telegram и отправьте /start")
        print("\n" + "="*50)
        bot.run()
    except KeyboardInterrupt:
        print("\n⏹️ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()