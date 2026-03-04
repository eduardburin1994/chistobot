# app.py - Улучшенная версия с веб-хуками для Render
import os
import asyncio
import logging
import sys
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Route
import uvicorn
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout  # Важно для Render
)
logger = logging.getLogger(__name__)

# Глобальная переменная для приложения бота
bot_app = None

async def startup():
    """Инициализация бота при старте"""
    global bot_app
    try:
        logger.info("🚀 Запуск инициализации бота...")
        
        # Проверяем наличие токена
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        logger.info("✅ Токен найден")
        
        from bot import main
        bot_app = await main(set_webhook=False)
        
        # Проверяем, что бот инициализирован
        if bot_app and bot_app.bot:
            bot_info = await bot_app.bot.get_me()
            logger.info(f"✅ Бот @{bot_info.username} инициализирован")
        else:
            logger.error("❌ Бот инициализирован некорректно")
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}", exc_info=True)
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
        
        # Проверяем, что тело не пустое
        if not body:
            logger.error("❌ Получено пустое тело запроса")
            return Response(status_code=400)
        
        # Логируем первые 200 символов для отладки
        logger.info(f"🔍 Получены данные (первые 200): {body[:200]}")
        
        # Пробуем декодировать
        try:
            body_str = body.decode('utf-8')
            logger.info(f"🔍 Декодированная строка: {body_str[:200]}")
            update_data = json.loads(body_str)
        except UnicodeDecodeError as e:
            logger.error(f"❌ Ошибка декодирования UTF-8: {e}")
            return Response(status_code=400)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            return Response(status_code=400)
        
        # Логируем тип обновления
        if 'message' in update_data:
            message = update_data['message']
            user_from = message.get('from', {})
            user_id = user_from.get('id')
            username = user_from.get('username', 'нет username')
            first_name = user_from.get('first_name', '')
            text = message.get('text', '')
            logger.info(f"📩 Сообщение от {first_name} (@{username}, ID:{user_id}): {text[:50]}")
        elif 'callback_query' in update_data:
            callback = update_data['callback_query']
            user_from = callback.get('from', {})
            user_id = user_from.get('id')
            data = callback.get('data', 'нет данных')
            logger.info(f"🔘 Callback от пользователя {user_id}: {data}")
        elif 'my_chat_member' in update_data:
            logger.info(f"👥 Обновление статуса чата: {update_data['my_chat_member']}")
        else:
            logger.info(f"📦 Другой тип обновления: {list(update_data.keys())}")
        
        # Передаём обновление боту
        from telegram import Update
        update = Update.de_json(update_data, bot_app.bot)
        
        # Обрабатываем обновление асинхронно
        await bot_app.process_update(update)
        logger.info("✅ Обновление успешно обработано")
        
        return Response(status_code=200)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки обновления: {e}", exc_info=True)
        return Response(status_code=500)

async def healthcheck(request):
    """Endpoint для проверки здоровья (Render требует)"""
    global bot_app
    
    # Проверяем состояние бота
    if not bot_app:
        return PlainTextResponse("Bot not initialized", status_code=503)
    
    try:
        # Проверяем подключение к Telegram API
        me = await bot_app.bot.get_me()
        return PlainTextResponse(f"OK - Bot @{me.username} is running")
    except Exception as e:
        logger.error(f"❌ Healthcheck failed: {e}")
        return PlainTextResponse(f"ERROR: {e}", status_code=500)

async def setup_webhook():
    """Установка веб-хука после запуска"""
    global bot_app
    if not bot_app:
        logger.error("❌ Невозможно установить webhook: бот не инициализирован")
        return
    
    try:
        # Получаем URL из переменной окружения Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not render_url:
            logger.error("❌ RENDER_EXTERNAL_URL не установлен!")
            logger.info("🔍 Доступные переменные окружения:")
            for key in os.environ.keys():
                if 'RENDER' in key or 'URL' in key:
                    logger.info(f"   {key}={os.environ.get(key)}")
            return
        
        # Формируем URL для webhook
        webhook_url = f"{render_url.rstrip('/')}/telegram"
        logger.info(f"🔗 Устанавливаем webhook на {webhook_url}")
        
        # Получаем текущую информацию о webhook
        current_webhook = await bot_app.bot.get_webhook_info()
        logger.info(f"ℹ️ Текущий webhook: {current_webhook.url}")
        
        # Если уже установлен на нужный URL, пропускаем
        if current_webhook.url == webhook_url:
            logger.info("✅ Webhook уже установлен на правильный URL")
            return
        
        # Удаляем старый webhook
        logger.info("🗑 Удаляем старый webhook...")
        await bot_app.bot.delete_webhook()
        
        # Устанавливаем новый
        logger.info(f"🔧 Устанавливаем новый webhook на {webhook_url}")
        await bot_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query', 'chat_member', 'my_chat_member'],
            max_connections=40,  # Оптимально для Render
            drop_pending_updates=True  # Очищаем старые обновления
        )
        
        # Проверяем результат
        webhook_info = await bot_app.bot.get_webhook_info()
        logger.info(f"✅ Webhook успешно установлен:")
        logger.info(f"   • URL: {webhook_info.url}")
        logger.info(f"   • Pending updates: {webhook_info.pending_update_count}")
        logger.info(f"   • Max connections: {webhook_info.max_connections}")
        
        # Проверяем доступность webhook
        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(webhook_url, json={"test": True}) as resp:
                    logger.info(f"📡 Тестовый запрос к webhook: статус {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Тестовый запрос не удался: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}", exc_info=True)

async def shutdown():
    """Действия при остановке приложения"""
    global bot_app
    logger.info("🛑 Завершение работы приложения...")
    if bot_app:
        try:
            await bot_app.stop()
            logger.info("✅ Бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")

# Создаём Starlette приложение
app = Starlette(
    routes=[
        Route("/telegram", telegram, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
        Route("/", healthcheck, methods=["GET"]),  # Корневой маршрут для проверки
    ],
    on_startup=[startup, setup_webhook],
    on_shutdown=[shutdown]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info("="*50)
    logger.info(f"🌐 Запуск сервера на {host}:{port}")
    logger.info(f"📡 Режим: webhook")
    logger.info(f"🔍 Render URL: {os.environ.get('RENDER_EXTERNAL_URL', 'не установлен')}")
    logger.info("="*50)
    
    # Запускаем сервер
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info",
        access_log=True  # Включаем логи доступа для отладки
    )
