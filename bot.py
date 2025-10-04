# ============================================
# requirements.txt - ИСПРАВЛЕННАЯ ВЕРСИЯ
# ============================================
python-telegram-bot==20.7
flask==3.0.0

# ============================================
# render.yaml - КОНФИГУРАЦИЯ ДЛЯ RENDER
# ============================================
services:
  - type: worker  # ОБЯЗАТЕЛЬНО: Background Worker
    name: salon-beauty-bot
    env: python
    region: oregon  # Выберите ближайший регион
    plan: free
    buildCommand: |
      echo "🔧 Установка зависимостей..."
      pip install --no-cache-dir -r requirements.txt
      echo "✅ Зависимости установлены"
    startCommand: |
      echo "🚀 Запуск Telegram-бота..."
      python bot_render_v2.py
    envVars:
      - key: BOT_TOKEN
        value: 8215198856:AAFaeNBZnrKig1tU0VR74DoCTHdrXsRKV1U
      - key: DATABASE_PATH
        value: /tmp/salon_bot.db
      - key: USE_WEBHOOK
        value: false
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: PYTHONUNBUFFERED
        value: "1"
    
    # Настройки для автоматического перезапуска
    autoDeploy: true
    
    # Игнорирование проверки портов для Background Worker
    healthCheckPath: ""

# ============================================
# Procfile - АЛЬТЕРНАТИВНАЯ КОНФИГУРАЦИЯ
# ============================================
worker: python bot_render_v2.py

# ============================================
# runtime.txt - ВЕРСИЯ PYTHON
# ============================================
python-3.11.0

# ============================================
# .gitignore - ЧТО НЕ ЗАГРУЖАТЬ НА GITHUB
# ============================================
# Локальные файлы
*.db
*.log
.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# ============================================
# start.sh - СКРИПТ ЗАПУСКА (опционально)
# ============================================
#!/bin/bash
set -e

echo "🚀 Запуск Telegram-бота салона красоты"
echo "📅 Время: $(date)"
echo "🌍 Окружение: $RENDER_SERVICE_NAME"

# Проверка переменных окружения
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Ошибка: BOT_TOKEN не установлен!"
    exit 1
fi

echo "✅ BOT_TOKEN: ${BOT_TOKEN:0:15}..."
echo "📂 DATABASE_PATH: ${DATABASE_PATH:-/tmp/salon_bot.db}"
echo "🐍 Python: $(python --version)"

# Проверка зависимостей
echo "🔍 Проверка python-telegram-bot..."
python -c "import telegram; print(f'✅ telegram-bot версия: {telegram.__version__}')" || {
    echo "❌ Ошибка: python-telegram-bot не установлен!"
    exit 1
}

# Создание директории для логов
mkdir -p /tmp/logs

echo "🤖 Запуск бота..."
exec python bot_render_v2.py

# ============================================
# health_check.py - ПРОВЕРКА СОСТОЯНИЯ БОТА
# ============================================
#!/usr/bin/env python3
"""
Скрипт для проверки состояния бота
Можно использовать для мониторинга
"""

import sqlite3
import os
import sys
from datetime import datetime

def check_bot_health():
    """Проверка состояния компонентов бота"""
    health_status = {
        'database': False,
        'bot_token': False,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Проверка токена
        bot_token = os.getenv('BOT_TOKEN')
        if bot_token and len(bot_token) > 20:
            health_status['bot_token'] = True
            print("✅ BOT_TOKEN: OK")
        else:
            print("❌ BOT_TOKEN: Не установлен или некорректный")
        
        # Проверка БД
        db_path = os.getenv('DATABASE_PATH', '/tmp/salon_bot.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Проверка таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            expected_tables = ['users', 'appointments']
            
            existing_tables = [table[0] for table in tables]
            if all(table in existing_tables for table in expected_tables):
                health_status['database'] = True
                print("✅ DATABASE: OK")
                
                # Статистика
                cursor.execute("SELECT COUNT(*) FROM users")
                users_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM appointments WHERE status='active'")
                appointments_count = cursor.fetchone()[0]
                
                print(f"📊 Пользователей: {users_count}")
                print(f"📅 Активных записей: {appointments_count}")
            else:
                print("❌ DATABASE: Отсутствуют необходимые таблицы")
            
            conn.close()
        else:
            print("❌ DATABASE: Файл БД не найден")
    
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
    
    # Общий статус
    all_ok = all(health_status[key] for key in ['database', 'bot_token'])
    print(f"\n{'✅ Общий статус: OK' if all_ok else '❌ Общий статус: ОШИБКА'}")
    
    return all_ok

if __name__ == '__main__':
    print("🔍 ПРОВЕРКА СОСТОЯНИЯ БОТА")
    print("=" * 40)
    
    success = check_bot_health()
    sys.exit(0 if success else 1)

# ============================================
# deploy_checklist.md - ЧЕКЛИСТ ДЕПЛОЯ
# ============================================

# 🚀 Чеклист деплоя на Render

## Перед деплоем

### 1. Остановка локальных экземпляров
- [ ] Остановлены ВСЕ локальные запуски бота (Ctrl+C)
- [ ] Закрыты все терминалы с запущенным ботом
- [ ] Проверено, что бот не запущен в фоне

### 2. Подготовка файлов
- [ ] Создан `bot_render_v2.py` (улучшенная версия)
- [ ] Обновлен `requirements.txt` (версия 20.7)
- [ ] Создан `render.yaml` с правильной конфигурацией
- [ ] Добавлен `.gitignore` (исключает .env, *.db)
- [ ] Проверены все файлы на корректность

### 3. GitHub репозиторий
- [ ] Все изменения загружены: `git add . && git commit -m "Fix for Render" && git push`
- [ ] Репозиторий доступен публично или подключен к Render
- [ ] Основная ветка: `main`

## Настройка Render

### 4. Создание сервиса
- [ ] Зайти на [render.com](https://render.com)
- [ ] Нажать "New +" → **"Background Worker"** (НЕ Web Service!)
- [ ] Подключить GitHub репозиторий
- [ ] Выбрать правильную ветку (main)

### 5. Конфигурация сервиса
```
Name: salon-beauty-bot
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python bot_render_v2.py
Plan: Free
Auto-Deploy: Yes
```

### 6. Переменные окружения
- [ ] `BOT_TOKEN` = `8215198856:AAFaeNBZnrKig1tU0VR74DoCTHdrXsRKV1U`
- [ ] `DATABASE_PATH` = `/tmp/salon_bot.db`
- [ ] `USE_WEBHOOK` = `false`
- [ ] `PYTHON_VERSION` = `3.11.0`
- [ ] `PYTHONUNBUFFERED` = `1`

## После деплоя

### 7. Проверка логов
Должны быть сообщения:
- [ ] `🚀 СТАРТ TELEGRAM-БОТА НА RENDER...`
- [ ] `✅ python-telegram-bot версия: 20.7`
- [ ] `🎯 Инициализация Telegram-бота для Render...`
- [ ] `💾 База данных готова: /tmp/salon_bot.db`
- [ ] `🤖 БОТ ЗАПУЩЕН НА RENDER!`
- [ ] `🔄 Бот работает...`

### 8. Тестирование бота
- [ ] Бот отвечает на `/start`
- [ ] Работает запись на процедуру
- [ ] Показывает услуги и цены
- [ ] Отображает информацию о мастерах
- [ ] Функционируют акции
- [ ] Работает "Мои записи"

### 9. Проверка стабильности
- [ ] Сервис показывает статус "Live"
- [ ] Нет ошибок в логах за 10 минут
- [ ] CPU Usage < 50%
- [ ] Memory Usage < 100MB
- [ ] Нет конфликтов с другими экземплярами

## Решение проблем

### Если "Conflict: terminated by other getUpdates request"
1. Остановить ВСЕ другие экземпляры бота
2. В Render: Manual Deploy → Deploy Latest Commit
3. Дождаться полного перезапуска

### Если "No open ports detected"
1. Убедиться, что создан **Background Worker**, не Web Service
2. Background Worker не требует портов - это нормально

### Если ошибки импорта
1. Проверить `requirements.txt`: `python-telegram-bot==20.7`
2. НЕ использовать версию 21.0
3. Пересобрать сервис

### Если бот не отвечает
1. Проверить логи на наличие ошибок
2. Убедиться, что BOT_TOKEN корректный
3. Проверить, что бот не заблокирован в Telegram

## Мониторинг

### Ежедневно
- [ ] Проверка статуса сервиса в Render Dashboard
- [ ] Просмотр логов на наличие ошибок
- [ ] Тестирование основных функций бота

### Еженедельно
- [ ] Проверка использования ресурсов
- [ ] Анализ количества пользователей
- [ ] Резервная копия важных данных

---

**🎉 Успешный деплой означает:**
- Статус сервиса: "Live"
- Логи без критических ошибок
- Бот отвечает на все команды
- Записи сохраняются в БД
- Нет конфликтов с другими экземплярами
