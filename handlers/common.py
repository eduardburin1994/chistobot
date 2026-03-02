# handlers/common.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data, user_data
from keyboards.client_keyboards import get_main_keyboard
from constants import WELCOME

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полноценный обработчик команды /start"""
    user = update.effective_user
    
    # Проверяем, есть ли пользователь в базе
    user_info = db.get_user_by_id(user.id)
    
    # Если пользователя нет в базе - добавляем
    if not user_info:
        db.add_user(user.id, user.username, user.first_name, user.last_name)
        print(f"✅ Новый пользователь {user.id} добавлен в базу")
        
        # Для нового пользователя показываем специальное приветствие
        welcome_text = (
            f"👋 <b>Добро пожаловать в ЧистоBOT, {user.first_name}!</b>\n\n"
            f"🚛 Я помогу вам быстро и удобно заказать вывоз мусора в Твери.\n\n"
            f"📝 <b>Нажмите кнопку ниже, чтобы начать работу:</b>"
        )
    else:
        # Для существующего пользователя показываем обычное приветствие
        print(f"✅ Существующий пользователь {user.id} вернулся в бота")
        welcome_text = (
            f"👋 <b>С возвращением, {user.first_name}!</b>\n\n"
            f"🚛 <b>ЧистоBOT</b> — твой помощник по вывозу мусора в Твери!\n\n"
            f"✨ <b>Что я умею:</b>\n"
            f"• 📦 Быстро оформить вывоз мусора\n"
            f"• 📅 Выбрать удобную дату и время\n"
            f"• 💰 Рассчитать стоимость сразу\n"
            f"• 📋 Посмотреть историю заказов\n"
            f"• 💬 Связаться с поддержкой\n\n"
            f"<b>Ну что, избавимся от мусора без хлопот?</b>"
        )
    
    # Проверка на блокировку
    if user.id in admin_data.get('blocked_users', []):
        await update.message.reply_text("⛔ Вы заблокированы в этом боте.")
        return ConversationHandler.END
    
    # Кнопки для ответа
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, давай!", callback_data='welcome_yes'),
            InlineKeyboardButton("🚶 Сам вынесу", callback_data='welcome_no')
        ]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return WELCOME

# ... остальные функции (welcome_callback, back_to_menu, show_prices, и т.д.) ...
# они у тебя уже есть и правильные
