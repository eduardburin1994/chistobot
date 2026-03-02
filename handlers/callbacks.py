# handlers/callbacks.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import datetime
from config import admin_data
from constants import CONFIRM_CANCEL, NAME
from keyboards.client_keyboards import get_main_keyboard

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки (общий)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # МАКСИМАЛЬНАЯ ОТЛАДКА
    print("\n" + "="*50)
    print(f"🔥🔥🔥 ПОЛУЧЕН CALLBACK! 🔥🔥🔥")
    print(f"📱 Данные кнопки: {query.data}")
    print(f"👤 Пользователь ID: {user_id}")
    print(f"💬 Текст сообщения: {query.message.text[:50]}..." if query.message.text else "Нет текста")
    print(f"🆔 ID сообщения: {query.message.message_id}")
    print(f"⏰ Время: {datetime.datetime.now()}")
    print("="*50 + "\n")
    
    # ВРЕМЕННО: показываем отладочное сообщение
    await query.edit_message_text(
        f"🔄 Отладка: получена команда '{query.data}'\n"
        f"Бот работает и видит нажатия!\n\n"
        f"Сейчас перенаправлю в нужное место..."
    )
    
    # Проверка блокировки
    if user_id in admin_data['blocked_users'] and query.data not in ['rules', 'prices']:
        await query.edit_message_text("⛔ Вы заблокированы.")
        return ConversationHandler.END
    
    # УПРОЩЕННАЯ ОБРАБОТКА КНОПОК ПРИВЕТСТВИЯ
    if query.data in ['welcome_yes', 'welcome_no']:
        print(f"✅ Обрабатываем кнопку приветствия: {query.data}")
        # Показываем главное меню
        keyboard = get_main_keyboard(user_id in admin_data['admins'])
        await query.edit_message_text(
            "👋 Главное меню:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    if query.data == 'new_order':
        await query.edit_message_text(
            "Давайте оформим заявку на вывоз мусора.\n\n"
            "Шаг 1 из 7: Введите ваше имя:"
        )
        return NAME
    
    elif query.data == 'prices':
        from handlers.common import show_prices
        await show_prices(update, context)
        return ConversationHandler.END
    
    elif query.data == 'rules':
        from handlers.common import show_rules
        await show_rules(update, context)
        return ConversationHandler.END
    
    elif query.data == 'contact':
        from handlers.common import show_contact
        await show_contact(update, context)
        return ConversationHandler.END
    
    elif query.data == 'back_to_menu':
        from handlers.common import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    
    elif query.data == 'my_orders':
        from handlers.client import my_orders
        await my_orders(update, context)
        return ConversationHandler.END
    
    elif query.data.startswith('order_detail_'):
        from handlers.client import order_detail
        await order_detail(update, context)
        return ConversationHandler.END
    
    elif query.data == 'cancel_order':
        return await cancel_order_handler(query, context)
    
    elif query.data.startswith('select_cancel_'):
        return await select_cancel_handler(query, context)
    
    elif query.data.startswith('confirm_cancel_'):
        return await confirm_cancel_handler(query, context)
    
    elif query.data == 'admin':
        from handlers.admin import admin_panel
        await admin_panel(update, context)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def cancel_order_handler(query, context):
    """Обработка отмены заказа (выбор заказа)"""
    user_id = query.from_user.id
    orders = db.get_user_orders(user_id)
    active_orders = [o for o in orders if len(o) > 9 and o[9] == 'new']
    
    if not active_orders:
        await query.edit_message_text(
            "❌ У вас нет активных заказов.",
            reply_markup=get_main_keyboard(query.from_user.id in admin_data['admins'])
        )
        return ConversationHandler.END
    
    keyboard = []
    for order in active_orders[:5]:
        order_id, _, name, _, _, date, time, bags, price, status, _ = order
        button_text = f"Заказ #{order_id} от {date} {time} ({bags} меш.)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'select_cancel_{order_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')])
    
    await query.edit_message_text(
        "Выберите заказ для отмены:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_CANCEL

async def select_cancel_handler(query, context):
    """Подтверждение отмены заказа"""
    order_id = int(query.data.replace('select_cancel_', ''))
    context.user_data['cancel_order_id'] = order_id
    
    # Проверяем время
    order = db.get_order_by_id(order_id)
    if order:
        order_date = order[5]
        order_time = order[6].split('-')[0]
        try:
            order_datetime = datetime.datetime.strptime(f"{order_date} {order_time}", "%d.%m.%Y %H:%M")
            now = datetime.datetime.now()
            hours_until = (order_datetime - now).total_seconds() / 3600
            
            if hours_until < 4:
                await query.edit_message_text(
                    "❌ Отменить можно не позднее, чем за 4 часа до выезда.",
                    reply_markup=get_main_keyboard(query.from_user.id in admin_data['admins'])
                )
                return ConversationHandler.END
        except:
            pass
    
    await query.edit_message_text(
        f"❓ Отменить заказ #{order_id}?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data=f'confirm_cancel_{order_id}')],
            [InlineKeyboardButton("❌ Нет", callback_data='back_to_menu')]
        ])
    )
    return CONFIRM_CANCEL

async def confirm_cancel_handler(query, context):
    """Подтверждение и выполнение отмены"""
    order_id = int(query.data.replace('confirm_cancel_', ''))
    db.cancel_order(order_id)
    
    # Уведомление админам
    for admin_id in admin_data['admins']:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"❌ Клиент отменил заказ #{order_id}"
            )
        except:
            pass
    
    await query.edit_message_text(
        f"✅ Заказ #{order_id} отменён.",
        reply_markup=get_main_keyboard(query.from_user.id in admin_data['admins'])
    )
    return ConversationHandler.END
