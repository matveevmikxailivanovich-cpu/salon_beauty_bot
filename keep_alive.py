# -*- coding: utf-8 -*-
"""
ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖАНИЯ АКТИВНОСТИ БОТА
Используется для пинга от UptimeRobot
"""

from flask import Flask, jsonify
from threading import Thread
import time

app = Flask(__name__)

@app.route('/')
def home():
    """Главная страница для проверки статуса"""
    return jsonify({
        'status': 'online',
        'message': '🤖 Бот салона красоты работает',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/health')
def health():
    """Endpoint для проверки здоровья сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'salon-telegram-bot'
    })

@app.route('/ping')
def ping():
    """Простой endpoint для пинга"""
    return 'pong', 200

def run():
    """Запуск Flask-сервера"""
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Запуск сервера в отдельном потоке"""
    server_thread = Thread(target=run)
    server_thread.daemon = True
    server_thread.start()
    print("🌐 Веб-сервер запущен на порту 8080")
    print("📡 Бот готов к пингу от UptimeRobot")