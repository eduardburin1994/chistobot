# app.py - Версия с веб-хуками для Render
import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Route
import uvicorn
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная переменная для приложения бота
bot_app = None

async def startup():
    """Инициализация бота при старте"""
    global bot_app
    try:
        logger.info("🚀 Запуск инициализации бота...")
        from bot import main
        bot_app = await main(set_webhook=False)
        logger.info("✅ Бот инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        raise

async def telegram(request):
    """Обработчик входящих обновлений от Telegram"""
    global bot_app
    if not bot_app:
        logger.error("❌ Бот не инициализирован")
        return Response("Bot not initialized", status_code=503)
    
    try:
        # Получаем данные от Telegram
        body = await request.body()
        update_data = json.loads(body)
        
        # Безопасно логируем полученное обновление
        if 'message' in update_data:
            # Проверяем, есть ли username
            user_from = update_data['message'].get('from', {})
            username = user_from.get('username', 'нет username')
            first_name = user_from.get('first_name', '')
            logger.info(f"📩 Получено сообщение от {first_name} (@{username})")
        
        # Передаём обновление боту
        from telegram import Update
        update = Update.de_json(update_data, bot_app.bot)
        await bot_app.process_update(update)
        
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки обновления: {e}")
        return Response(status_code=500)

async def healthcheck(request):
    """Endpoint для проверки здоровья (Render требует)"""
    return PlainTextResponse("OK")

async def setup_webhook():
    """Установка веб-хука после запуска"""
    global bot_app
    if not bot_app:
        logger.error("❌ Невозможно установить webhook: бот не инициализирован")
        return
    
    try:
        # Получаем URL из переменной окружения Render
        webhook_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not webhook_url:
            logger.error("❌ RENDER_EXTERNAL_URL не установлен!")
            return
        
        webhook_url = f"{webhook_url}/telegram"
        logger.info(f"🔗 Устанавливаем webhook на {webhook_url}")
        
        # Удаляем старый webhook
        await bot_app.bot.delete_webhook()
        
        # Устанавливаем новый
        await bot_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query', 'chat_member']
        )
        logger.info(f"✅ Webhook успешно установлен на {webhook_url}")
        
        # Проверяем информацию о webhook
        webhook_info = await bot_app.bot.get_webhook_info()
        logger.info(f"ℹ️ Информация о webhook: {webhook_info}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")

# Создаём Starlette приложение
app = Starlette(
    routes=[
        Route("/telegram", telegram, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
        Route("/", healthcheck, methods=["GET"]),  # Корневой маршрут для проверки
    ],
    on_startup=[startup, setup_webhook]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Запуск сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
