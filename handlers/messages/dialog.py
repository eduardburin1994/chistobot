from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
from constants import DIALOG_VIEW

async def admin_dialog_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает диалог с конкретным пользователем"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    user_id = int(query.data.replace('dialog_open_', ''))
    context.user_data['current_dialog_user'] = user_id
    
    # Получаем информацию о пользователе
    user_info = db.get_user_by_id(user_id)
    if not user_info:
        await query.edit_message_text("❌ Пользователь не найден")
        return
    
    # Получаем сообщения
    messages = db.get_dialog_messages(user_id, limit=15)
    
    # Отмечаем все как прочитанные
    db.mark_dialog_as_read(user_id)
    
    # Формируем шапку диалога
    first_name = user_info[2] or ""
    username = user_info[1] or ""
    phone = user_info[4] or "не указан"
    
    name_parts = []
    if first_name:
        name_parts.append(first_name)
    if username:
        name_parts.append(f"@{username}")
    if not name_parts:
        name_parts.append(f"ID {user_id}")
    
    display_name = " ".join(name_parts)
    
    text = (
        f"💬 <b>{display_name}</b> (ID: {user_id})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 {phone}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Добавляем сообщения (последние 10)
    for msg in messages[:10]:
        # msg: (message_id, user_id, from_admin, user_message, created_at, is_read)
        msg_id = msg[0]
        from_admin = msg[2]  # индекс 2, а не 1!
        msg_text = msg[3]
        msg_time = msg[4]
        is_read = msg[5]
        
        # Форматируем время
        time_str = msg_time.strftime("%H:%M") if msg_time else ""
        
        if from_admin:
            sender = "👤 Админ"
            read_icon = "✓" if is_read else ""
        else:
            sender = "👤 Клиент"
            read_icon = ""
        
        text += f"[{time_str}] {sender}:\n{msg_text} {read_icon}\n\n"
    
    # Кнопки действий
    keyboard = [
        [
            InlineKeyboardButton("✏️ Ответить", callback_data=f'dialog_reply_{user_id}'),
            InlineKeyboardButton("✅ Отм. все", callback_data=f'dialog_mark_read_{user_id}')
        ],
        [
            InlineKeyboardButton("⭐ В важное", callback_data=f'dialog_important_{user_id}'),
            InlineKeyboardButton("🗑 Удалить", callback_data=f'dialog_delete_{user_id}')
        ],
        [
            InlineKeyboardButton("🚫 Блок", callback_data=f'block_user_{user_id}'),
            InlineKeyboardButton("📞 Телефон", callback_data=f'show_phone_{user_id}')
        ],
        [InlineKeyboardButton("◀️ Назад к диалогам", callback_data='admin_dialogs_all')]
    ]
    
    await query.edit_message_text(
        text, 
        parse_mode='HTML', 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DIALOG_VIEW

async def admin_dialog_mark_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмечает диалог как прочитанный"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('dialog_mark_read_', ''))
    db.mark_dialog_as_read(user_id)
    
    # Возвращаемся в диалог
    await admin_dialog_open(update, context)
