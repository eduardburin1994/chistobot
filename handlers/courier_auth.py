from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import COURIER_PASSWORD

ENTER_COURIER_PASSWORD = 60

async def courier_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в режим курьера"""
    user_id = update.effective_user.id
    
    # Проверяем, не админ ли это (админы могут входить без пароля)
    from config import admin_data
    if user_id in admin_data['admins']:
        context.user_data['is_courier'] = True
        from handlers.courier import courier_main_menu
        await courier_main_menu(update, context)
        return ConversationHandler.END
    
    # Проверяем, может уже курьер
    if context.user_data.get('is_courier'):
        from handlers.courier import courier_main_menu
        await courier_main_menu(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🚚 <b>Вход для курьера</b>\n\n"
        "Введите пароль для доступа:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')
        ]])
    )
    return ENTER_COURIER_PASSWORD

async def courier_login_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка пароля курьера"""
    password = update.message.text
    
    if password == COURIER_PASSWORD:
        context.user_data['is_courier'] = True
        from handlers.courier import courier_main_menu
        await courier_main_menu(update, context)
    else:
        await update.message.reply_text(
            "❌ <b>Неверный пароль</b>\n\n"
            "Попробуйте ещё раз или нажмите /start",
            parse_mode='HTML'
        )
    return ConversationHandler.END

async def courier_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из режима курьера"""
    context.user_data['is_courier'] = False
    
    # Проверяем, может это админ
    from config import admin_data
    is_admin = update.effective_user.id in admin_data['admins']
    
    from keyboards.client_keyboards import get_main_keyboard
    await update.message.reply_text(
        "👋 Вы вышли из режима курьера",
        reply_markup=get_main_keyboard(is_admin)
    )
    return ConversationHandler.END