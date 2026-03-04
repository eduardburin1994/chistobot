from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data

async def admin_dialogs_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех диалогов"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    # Получаем тип списка из callback_data
    data = query.data
    if data == 'admin_dialogs_all':
        filter_type = 'all'
        title = "📋 ВСЕ ДИАЛОГИ"
    elif data == 'admin_dialogs_new':
        filter_type = 'new'
        title = "🆕 НОВЫЕ ДИАЛОГИ"
    elif data == 'admin_dialogs_important':
        filter_type = 'important'
        title = "⭐ ВАЖНЫЕ"
    elif data == 'admin_dialogs_outbox':
        filter_type = 'outbox'
        title = "📤 ИСХОДЯЩИЕ"
    else:
        filter_type = 'all'
        title = "📋 ВСЕ ДИАЛОГИ"
    
    # Загружаем диалоги из БД
    dialogs = db.get_dialogs(filter_type)
    
    if not dialogs:
        await query.edit_message_text(
            f"{title}\n\n📭 Нет диалогов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin_messages')
            ]])
        )
        return
    
    text = f"💬 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []
    
    for dialog in dialogs[:10]:
        user_id, first_name, username, last_msg, last_time, unread, is_blocked = dialog
        
        # Определяем имя для отображения
        if first_name:
            display_name = first_name
        elif username:
            display_name = f"@{username}"
        else:
            display_name = f"ID {user_id}"
        
        # Статус (заблокирован или нет)
        status_emoji = "🔴" if is_blocked else "🟢"
        
        # Добавляем информацию о диалоге
        text += f"{status_emoji} <b>{display_name}</b>\n"
        text += f"   📝 {last_msg[:50]}...\n"
        
        # Преобразуем datetime в строку
        if last_time:
            time_str = last_time.strftime("%H:%M")
        else:
            time_str = ""
            
        text += f"   🕒 {time_str} "
        if unread > 0:
            text += f"• <b>{unread} новых</b>"
        text += "\n\n"
        
        # Кнопка для входа в диалог
        keyboard.append([InlineKeyboardButton(
            f"💬 {display_name[:20]}", 
            callback_data=f'dialog_open_{user_id}'
        )])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data='admin_messages'),
        InlineKeyboardButton("📥 Все", callback_data='admin_dialogs_all')
    ])
    
    await query.edit_message_text(
        text, 
        parse_mode='HTML', 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
