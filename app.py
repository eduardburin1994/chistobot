# app.py - точка входа для Render.com
import os
import sys
import threading
import logging
from flask import Flask

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask приложение для health check
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 ЧистоBOT работает!"

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    """Запускает Telegram бота в отдельном потоке"""
    try:
        logger.info("🚀 Запуск Telegram бота...")
        from bot import main
        main()
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    # Запускаем бота в фоне
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Бот запущен в фоновом потоке")
    
    # Запускаем Flask сервер
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Flask сервер запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)