# bot.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import TOKEN, admin_data
from constants import *
from keyboards.client_keyboards import get_main_keyboard, create_date_keyboard, get_back_button
from handlers.client import (
    get_name, get_phone, get_intercom, date_callback, time_callback, get_bags, 
    support_start, support_message, start_order, check_address_handler, 
    new_address, new_entrance, new_floor, new_apartment, new_intercom,
    my_orders_detail, order_detail_select, favorite_addresses_menu, favorite_add,
    favorite_save, favorite_delete_menu, favorite_delete, choose_address, 
    select_favorite_address, new_address_start, manage_favorites, edit_favorite_menu,
    edit_favorite_name, save_favorite_name, delete_favorite_confirm, confirm_delete_favorite,
    favorite_add_after_order, payment_method_handler, back_to_bags
)
from handlers.admin import (
    handle_admin_actions, admin_panel, admin_orders, admin_clients, 
    admin_messages, admin_messages_all, admin_prices_menu, admin_blacklist, admin_stats,
    edit_price_start, set_new_price, show_user_id, admin_blacklist_menu,
    blacklist_add_user, blacklist_add_process, admin_broadcast, broadcast_new, broadcast_send,
    broadcast_history, notify_admin, toggle_test_mode
)
from handlers.common import (
    start, welcome_callback, back_to_menu, show_prices, show_rules, show_contact, 
    handle_new_chat_members
)

# Константа для редактирования цен
EDITING_PRICE = 100

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def button_handler(update: Update, context):
    """Обработчик всех кнопок"""
    query = update.callback_query
    await query.answer()
    logger.info(f"Нажата кнопка: {query.data}")
    
    user_id = query.from_user.id
    
    # Обработка кнопок приветствия
    if query.data in ['welcome_yes', 'welcome_no']:
        keyboard = get_main_keyboard(user_id in admin_data['admins'])
        if query.data == 'welcome_yes':
            text = "Отлично! 🎉 Давайте начнём. Выберите действие:"
        else:
            text = "Ладно, но если передумаете — я всегда здесь! 😉\n\nВыберите действие:"
        await query.edit_message_text(text, reply_markup=keyboard)
        return ConversationHandler.END
    
    # Кнопка возврата в главное меню
    if query.data == 'back_to_menu':
        keyboard = get_main_keyboard(user_id in admin_data['admins'])
        await query.edit_message_text("👋 Главное меню:", reply_markup=keyboard)
        return ConversationHandler.END
    
    # Запуск процесса заказа
    if query.data == 'new_order':
        await start_order(update, context)
        return
    
    # Кнопки меню
    if query.data == 'prices':
        price_text = (
            "💰 <b>Наши расценки:</b>\n\n"
            f"• 🟢 <b>1 мешок</b> — {admin_data['prices']['1']} ₽\n"
            f"  <i>(за один мешок)</i>\n\n"
            f"• 🟡 <b>2 мешка</b> — {admin_data['prices']['2']} ₽\n"
            f"  <i>(за два мешка, включая вывоз)</i>\n\n"
            f"• 🔴 <b>3 и более мешков</b> — {admin_data['prices']['3+']} ₽\n"
            f"  <i>(фиксированная цена за весь объём)</i>\n\n"
            "⚠️ <b>Важно:</b> Общий вес всех мешков не должен превышать 15 кг!\n\n"
            "💳 Оплата наличными или переводом курьеру."
        )
        await query.edit_message_text(price_text, parse_mode='HTML', reply_markup=get_back_button())
    
    if query.data == 'rules':
        rules_text = (
            "📋 <b>Правила и условия:</b>\n\n"
            "1️⃣ <b>Вес:</b> Общий вес всех мешков не более 15 кг.\n"
            "2️⃣ <b>Отмена:</b> Клиент может отменить заказ за 4 часа до выезда.\n"
            "3️⃣ <b>Время работы:</b> Заявки принимаются с 8:00 до 20:00.\n"
            "4️⃣ <b>Отказ:</b> При превышении веса курьер вправе отказаться от заказа.\n"
            "5️⃣ <b>Запрещено:</b> Строительный мусор и опасные отходы."
        )
        await query.edit_message_text(rules_text, parse_mode='HTML', reply_markup=get_back_button())
    
    if query.data == 'contact':
        await show_contact(update, context)
        return
    
    if query.data == 'support_write':
        return await support_start(update, context)
    
    # Кнопки заказов
    if query.data == 'my_orders_detail':
        await my_orders_detail(update, context)
        return
    
    if query.data == 'order_detail_select':
        await order_detail_select(update, context)
        return
    
    if query.data.startswith('order_detail_'):
        from handlers.client import order_detail
        await order_detail(update, context)
        return
    
    # Кнопки избранных адресов
    if query.data == 'favorite_menu':
        await favorite_addresses_menu(update, context)
        return
    
    if query.data == 'favorite_add':
        await favorite_add(update, context)
        return
    
    if query.data == 'favorite_delete':
        await favorite_delete_menu(update, context)
        return
    
    if query.data.startswith('favorite_del_'):
        await favorite_delete(update, context)
        return
    
    if query.data == 'favorite_add_after_order':
        await favorite_add_after_order(update, context)
        return
    
    if query.data == 'manage_favorites':
        await manage_favorites(update, context)
        return
    
    if query.data.startswith('edit_fav_'):
        await edit_favorite_menu(update, context)
        return
    
    if query.data.startswith('edit_name_'):
        await edit_favorite_name(update, context)
        return
    
    if query.data.startswith('delete_fav_'):
        await delete_favorite_confirm(update, context)
        return
    
    if query.data.startswith('confirm_delete_'):
        await confirm_delete_favorite(update, context)
        return
    
    # Кнопки выбора адреса
    if query.data == 'choose_address':
        await choose_address(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('select_fav_'):
        await select_favorite_address(update, context)
        return ConversationHandler.END
    
    if query.data == 'new_address_start':
        await new_address_start(update, context)
        return ConversationHandler.END
    
    # Кнопки оплаты
    if query.data in ['pay_cash', 'pay_card', 'pay_yookassa']:
        return await payment_method_handler(update, context)
    
    if query.data == 'back_to_bags':
        await back_to_bags(update, context)
        return
    
    # Кнопки админки
    if query.data == 'admin':
        await admin_panel(update, context)
        return
    
    if query.data == 'admin_orders':
        await admin_orders(update, context)
        return
    
    if query.data == 'admin_clients':
        await admin_clients(update, context)
        return
    
    if query.data == 'admin_messages':
        await admin_messages(update, context)
        return
    
    if query.data == 'admin_messages_all':
        await admin_messages_all(update, context)
        return
    
    if query.data == 'admin_prices_menu':
        await admin_prices_menu(update, context)
        return
    
    if query.data == 'admin_blacklist':
        await admin_blacklist_menu(update, context)
        return
    
    if query.data == 'blacklist_add_user':
        await blacklist_add_user(update, context)
        return
    
    if query.data == 'admin_broadcast':
        await admin_broadcast(update, context)
        return
    
    if query.data == 'broadcast_new':
        await broadcast_new(update, context)
        return
    
    if query.data == 'broadcast_history':
        await broadcast_history(update, context)
        return
    
    if query.data == 'admin_stats':
        await admin_stats(update, context)
        return
    
    if query.data == 'toggle_test_mode':
        await toggle_test_mode(update, context)
        return
    
    # Обработка действий с заказами
    if query.data.startswith('complete_') or query.data.startswith('cancel_'):
        await handle_admin_actions(update, context)
        return
    
    if query.data.startswith('show_user_id_'):
        await show_user_id(update, context)
        return
    
    return ConversationHandler.END

async def main():
    """Асинхронная функция запуска бота"""
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Единый ConversationHandler для всего процесса заказа
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order, pattern='^new_order$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CHECK_ADDRESS: [CallbackQueryHandler(check_address_handler, pattern='^(change_address_yes|change_address_no)$')],
            SELECT_ADDRESS: [
                CallbackQueryHandler(select_favorite_address, pattern='^select_fav_'),
                CallbackQueryHandler(new_address_start, pattern='^new_address_start$')
            ],
            NEW_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_address)],
            NEW_ENTRANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_entrance)],
            NEW_FLOOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_floor)],
            NEW_APARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_apartment)],
            NEW_INTERCOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_intercom)],
            DATE: [CallbackQueryHandler(date_callback, pattern='^date_')],
            TIME: [CallbackQueryHandler(time_callback, pattern='^time_')],
            PAYMENT_METHOD: [CallbackQueryHandler(payment_method_handler, pattern='^pay_')],
            BAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bags)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для избранных адресов (добавление)
    favorite_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(favorite_add, pattern='^favorite_add$')],
        states={
            FAVORITE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, favorite_save)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для редактирования избранных адресов
    favorite_edit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_favorite_name, pattern='^edit_name_')
        ],
        states={
            EDIT_FAVORITE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_favorite_name)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для черного списка
    blacklist_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(blacklist_add_user, pattern='^blacklist_add_user$')],
        states={
            BLACKLIST_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_add_process)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для рассылки
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_new, pattern='^broadcast_new$')],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для сообщений в поддержку
    support_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_start, pattern='^support_write$')],
        states={
            SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_message)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для приветствия
    welcome_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WELCOME: [CallbackQueryHandler(button_handler, pattern='^(welcome_yes|welcome_no)$')]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # ConversationHandler для редактирования цен
    price_edit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_price_start, pattern='^edit_price_')
        ],
        states={
            EDITING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_price)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # Добавляем все обработчики
    app.add_handler(welcome_handler)
    app.add_handler(conv_handler)
    app.add_handler(favorite_handler)
    app.add_handler(favorite_edit_handler)
    app.add_handler(blacklist_handler)
    app.add_handler(broadcast_handler)
    app.add_handler(support_handler)
    app.add_handler(price_edit_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(toggle_test_mode, pattern='^toggle_test_mode$'))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    
    print("🚀 Бот ЧистоBOT запущен на Render...")
    
    # Запускаем бота (асинхронно)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Держим бота запущенным
    while True:
        await asyncio.sleep(1)

# Убираем блок if __name__ == '__main__' - он больше не нужен
# так как запуск будет через app.py
