# handlers/admin_access.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import admin_data

# Пароль для доступа к админке (можешь поменять)
ADMIN_PASSWORD = "54admin54"

# Состояние для ввода пароля (добавим в constants позже)
ENTER_ADMIN_PASSWORD = 50

async def admin_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin - начало входа"""
    user_id = update.effective_user.id
    
    # Если уже админ - сразу показываем панель
    if user_id in admin_data['admins']:
        from handlers.admin import admin_panel_reply
        await admin_panel_reply(update, context)
        return ConversationHandler.END
    
    # Спрашиваем пароль
    await update.message.reply_text(
        "🔐 <b>Вход в админ-панель</b>\n\n"
        "Введите пароль для доступа:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')
        ]])
    )
    return ENTER_ADMIN_PASSWORD

async def admin_login_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка пароля"""
    user_id = update.effective_user.id
    password = update.message.text
    
    if password == ADMIN_PASSWORD:
        # Добавляем пользователя в админы
        if user_id not in admin_data['admins']:
            admin_data['admins'].append(user_id)
            print(f"✅ Новый администратор добавлен: {user_id}")
        
        await update.message.reply_text(
            "✅ <b>Доступ разрешён!</b>\n\n"
            "Добро пожаловать в админ-панель.\n"
            "Теперь у вас есть доступ ко всем разделам.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Открыть админку", callback_data='admin')
            ]])
        )
    else:
        await update.message.reply_text(
            "❌ <b>Неверный пароль</b>\n\n"
            "Попробуйте ещё раз или нажмите /start",
            parse_mode='HTML'
        )
    
    return ConversationHandler.END

async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из админки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Не даём удалить главного админа (твой ID)
    if user_id == 954653245:
        await query.edit_message_text(
            "❌ Главный администратор не может выйти",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin')
            ]])
        )
        return
    
    if user_id in admin_data['admins']:
        admin_data['admins'].remove(user_id)
        print(f"👋 Администратор {user_id} вышел")
        await query.edit_message_text(
            "✅ Вы вышли из режима администратора",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')
            ]])
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin')
            ]])
        )
