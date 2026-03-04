# handlers/admin_access.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import admin_data

# Пароль для доступа к админке
ADMIN_PASSWORD = "54admin54"

# Состояние для ввода пароля
ENTER_ADMIN_PASSWORD = 50

async def admin_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin - начало входа"""
    user_id = update.effective_user.id
    
    # Если уже админ - показываем админ-панель через reply-версию
    if user_id in admin_data['admins']:
        from handlers.admin import admin_panel_reply
        await admin_panel_reply(update, context)
        return ConversationHandler.END
    
    # Если не админ - спрашиваем пароль
    await update.message.reply_text(
        "🔐 <b>Вход в админ-панель</b>\n\n"
        "Введите пароль для доступа:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')
        ]])
    )
    return ENTER_ADMIN_PASSWORD

# ← НИКАКИХ ЛИШНИХ СТРОК ЗДЕСЬ!
