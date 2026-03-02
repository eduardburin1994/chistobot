# app.py - финальная версия для Render.com
import os
import asyncio
import logging
from flask import Flask

# Настройка логирования
logging.basicConfig(
    format='%(asime).19s - %(name)s - %(levelname)s - %(message)s',
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
        logger.info("🚀 Запуск Telegram бота из потока...")
        
        # Создаем и устанавливаем event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Импортируем функцию main из bot.py
        from bot import main
        
        # Запускаем main в event loop
        loop.run_until_complete(main())
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Бот запущен в фоновом потоке")
    
    # Запускаем Flask сервер
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Flask сервер запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)
