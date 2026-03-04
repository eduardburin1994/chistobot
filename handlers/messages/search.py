from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
from constants import SEARCH_MESSAGES

async def admin_messages_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск по сообщениям"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    await query.edit_message_text(
        "🔍 <b>ПОИСК СООБЩЕНИЙ</b>\n\n"
        "Введите текст для поиска:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='admin_messages')
        ]])
    )
    return SEARCH_MESSAGES

async def admin_messages_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Результаты поиска"""
    admin_id = update.effective_user.id
    
    if admin_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    search_text = update.message.text
    results = db.search_messages(search_text)
    
    if not results:
        await update.message.reply_text(
            "❌ Ничего не найдено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin_messages')
            ]])
        )
        return ConversationHandler.END
    
    text = f"🔍 <b>Результаты поиска: '{search_text}'</b>\n\n"
    keyboard = []
    
    for msg in results[:5]:
        msg_id, user_id, user_name, msg_text, msg_time = msg
        
        # Обрезаем слишком длинные сообщения
        short_text = msg_text[:100] + "..." if len(msg_text) > 100 else msg_text
        
        # Форматируем время
        if msg_time:
            time_str = msg_time.strftime("%d.%m.%Y %H:%M")
        else:
            time_str = ""
        
        text += f"👤 <b>{user_name}</b> (ID:{user_id})\n"
        text += f"📝 {short_text}\n"
        text += f"🕒 {time_str}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"💬 Перейти к диалогу", 
            callback_data=f'dialog_open_{user_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_messages')])
    
    await update.message.reply_text(
        text, 
        parse_mode='HTML', 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END
