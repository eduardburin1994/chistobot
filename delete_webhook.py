import asyncio
from telegram import Bot

async def delete_webhook():
    bot = Bot(token="8730099509:AAF83M1EjAqwB7FErvaRXJUPKaP-1kREv8I")
    await bot.delete_webhook()
    print("✅ Webhook удалён")

asyncio.run(delete_webhook())