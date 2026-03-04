from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
from constants import DIALOG_REPLY

async def admin_dialog_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ответа в диалоге"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('dialog_reply_', ''))
    context.user_data['reply_to_user'] = user_id
    
    await query.edit_message_text(
        f"✏️ <b>Ответ пользователю</b>\n\n"
        f"Введите текст сообщения:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data=f'dialog_open_{user_id}')
        ]])
    )
    return DIALOG_REPLY

async def admin_dialog_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка ответа в диалоге"""
    admin_id = update.effective_user.id
    
    if admin_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    target_user_id = context.user_data.get('reply_to_user')
    if not target_user_id:
        await update.message.reply_text("❌ Ошибка: диалог не найден")
        return ConversationHandler.END
    
    message_text = update.message.text
    
    # Отправляем сообщение клиенту
    try:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Ответить администратору", callback_data='support_write')
        ]])
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📢 <b>Ответ администратора</b>\n\n{message_text}",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        # Сохраняем в БД
        db.save_admin_message(target_user_id, message_text)
        
        # Возвращаемся в диалог
        await update.message.reply_text(
            "✅ Сообщение отправлено!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Вернуться в диалог", callback_data=f'dialog_open_{target_user_id}')
            ]])
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")
    
    return ConversationHandler.END

async def admin_dialog_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление диалога (помещение в корзину)"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('dialog_delete_', ''))
    
    # Подтверждение удаления
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f'dialog_delete_confirm_{user_id}'),
            InlineKeyboardButton("❌ Нет", callback_data=f'dialog_open_{user_id}')
        ]
    ]
    
    await query.edit_message_text(
        f"❓ Удалить все сообщения с пользователем ID {user_id}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_dialog_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления диалога"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID пользователя из callback_data
    data = query.data
    user_id = int(data.replace('dialog_delete_confirm_', ''))
    
    # Здесь можно реализовать удаление всех сообщений пользователя
    # Например: db.delete_all_user_messages(user_id)
    
    await query.edit_message_text(
        "✅ Диалог удален",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К диалогам", callback_data='admin_dialogs_all')
        ]])
    )

async def admin_show_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает телефон пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('show_phone_', ''))
    user_info = db.get_user_by_id(user_id)
    
    if user_info and user_info[4]:
        phone = user_info[4]
    else:
        phone = "не указан"
    
    await query.answer(f"📞 Телефон: {phone}", show_alert=True)
