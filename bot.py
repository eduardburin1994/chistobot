# bot.py
import logging
import asyncio
import warnings
from handlers.client import bags_callback
from keyboards.client_keyboards import get_bags_keyboard
from handlers.admin import admin_order_detail, reopen_order
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", message="Fetching updates got a asyncio.CancelledError")
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import TOKEN, admin_data
from constants import *
from keyboards.client_keyboards import get_main_keyboard, create_date_keyboard, get_back_button
from handlers.client import (
    get_name, get_phone, get_intercom, date_callback, time_callback, get_bags, 
    support_start, support_message, start_order, check_address_handler, 
    new_address, new_entrance, new_floor, new_apartment, new_intercom,
    my_orders_detail, order_detail_select, favorite_addresses_menu,
    favorite_add, favorite_save, favorite_delete_menu, favorite_delete, choose_address, 
    select_favorite_address, new_address_start, manage_favorites, edit_favorite_menu,
    edit_favorite_name, save_favorite_name, delete_favorite_confirm, confirm_delete_favorite,
    favorite_add_after_order, payment_method_handler, back_to_bags, order_detail,
    bags_callback, confirm_order_before_final, repeat_order, final_confirm_order
)
from handlers.admin import (
    handle_admin_actions, admin_panel, admin_orders, admin_clients, 
    admin_messages, admin_messages_all, admin_prices_menu, admin_blacklist, admin_stats,
    admin_stats_detailed, admin_stats_charts, edit_price_start, set_new_price, show_user_id, 
    admin_blacklist_menu, blacklist_add_user, blacklist_add_process, admin_broadcast, 
    broadcast_new, broadcast_send, broadcast_history, notify_admin, toggle_test_mode,
    admin_working_hours, edit_start_hour, edit_end_hour, set_working_hours,
    admin_export, admin_settings,
    admin_write_to_user, enter_user_id_for_message, send_message_to_user,
    admin_orders_cleanup, process_orders_cleanup,
    blacklist_remove_user, blacklist_remove_process
)
from handlers.common import (
    start, welcome_callback, back_to_menu, show_prices, show_rules, show_contact, 
    handle_new_chat_members, rules_command
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
    
    # Проверка черного списка для всех действий
    import database as db
    if db.is_user_blacklisted(user_id) and query.data not in ['rules', 'prices']:
        await query.edit_message_text("⛔ Вы заблокированы в этом боте.")
        return ConversationHandler.END

    # Детали заказа
    if query.data.startswith('order_detail_'):
        await admin_order_detail(update, context)
        return ConversationHandler.END

    # Возврат заказа в работу
    if query.data.startswith('reopen_'):
        await reopen_order(update, context)
        return ConversationHandler.END

    # Повтор заказа
    if query.data.startswith('repeat_order_'):
        from handlers.client import repeat_order
        await repeat_order(update, context)
        return ConversationHandler.END

    #    # ===== ИЗМЕНЕНИЕ АДРЕСА =====
    if query.data == 'change_address':
        user_id = query.from_user.id
        print(f"🔄 Пользователь {user_id} изменяет адрес")
        
        # Очищаем данные адреса, но оставляем имя и телефон
        if user_id in user_data:
            user_data[user_id].pop('street_address', None)
            user_data[user_id].pop('entrance', None)
            user_data[user_id].pop('floor', None)
            user_data[user_id].pop('apartment', None)
            user_data[user_id].pop('intercom', None)
            user_data[user_id].pop('address_name', None)
        
        from handlers.client import choose_address
        await choose_address(update, context)
        return SELECT_ADDRESS
    # =============================
    # ===============================

    # Подтверждение заказа
    if query.data == 'final_confirm':
        print(f"🔍 НАЖАТА КНОПКА final_confirm для пользователя {user_id}")
        from handlers.client import final_confirm_order
        await final_confirm_order(update, context)
        return ConversationHandler.END
    
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
        return ConversationHandler.END
    
    # Кнопки меню
    if query.data == 'prices':
        price_text = (
            "💰 <b>Наши расценки:</b>\n\n"
            f"• 🟢 <b>1 пакет</b> — {admin_data['prices']['1']} ₽\n"
            f"  <i>(курьер заберёт и утилизирует один пакет)</i>\n\n"
            f"• 🟡 <b>2 пакета</b> — {admin_data['prices']['2']} ₽\n"
            f"  <i>(за два пакета, включая вынос)</i>\n\n"
            f"• 🔴 <b>3 и более пакетов</b> — {admin_data['prices']['3+']} ₽\n"
            f"  <i>(фиксированная цена за весь объём)</i>\n\n"
            "⚠️ <b>Важно:</b> Общий вес всех пакетов не должен превышать 15 кг!\n\n"
            "💳 Оплата наличными или переводом курьеру после выполнения."
        )
        await query.edit_message_text(price_text, parse_mode='HTML', reply_markup=get_back_button())
        return ConversationHandler.END
    
    if query.data == 'rules':
        rules_text = (
            "📋 <b>Правила и условия:</b>\n\n"
            "1️⃣ <b>Вес:</b> Общий вес всех пакетов не более 15 кг.\n"
            "2️⃣ <b>Отмена:</b> Вы можете отменить заказ за 4 часа до прихода курьера.\n"
            "3️⃣ <b>Время работы:</b> Заявки принимаются с 10:00 до 22:00.\n"
            "4️⃣ <b>Отказ:</b> При превышении веса курьер вправе отказаться от выноса.\n"
            "5️⃣ <b>Что можно выносить:</b> Обычные бытовые отходы. Строительный мусор и опасные отходы не принимаются.\n"
            "6️⃣ <b>Как это работает:</b> Курьер забирает пакеты прямо от вашей двери и самостоятельно утилизирует их в ближайшем баке."
        )
        await query.edit_message_text(rules_text, parse_mode='HTML', reply_markup=get_back_button())
        return ConversationHandler.END
    
    if query.data == 'contact':
        await show_contact(update, context)
        return ConversationHandler.END
    
    if query.data == 'support_write':
        return await support_start(update, context)
    
    # Кнопки заказов
    if query.data == 'my_orders_detail':
        await my_orders_detail(update, context)
        return ConversationHandler.END
    
    if query.data == 'order_detail_select':
        await order_detail_select(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('order_detail_'):
        await order_detail(update, context)
        return ConversationHandler.END
    
    # Кнопки избранных адресов
    if query.data == 'favorite_menu':
        await favorite_addresses_menu(update, context)
        return ConversationHandler.END
    
    if query.data == 'favorite_add':
        await favorite_add(update, context)
        return ConversationHandler.END
    
    if query.data == 'favorite_delete':
        await favorite_delete_menu(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('favorite_del_'):
        await favorite_delete(update, context)
        return ConversationHandler.END
    
    if query.data == 'favorite_add_after_order':
        await favorite_add_after_order(update, context)
        return ConversationHandler.END
    
    if query.data == 'manage_favorites':
        await manage_favorites(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('edit_fav_'):
        await edit_favorite_menu(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('edit_name_'):
        await edit_favorite_name(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('delete_fav_'):
        await delete_favorite_confirm(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('confirm_delete_'):
        await confirm_delete_favorite(update, context)
        return ConversationHandler.END
    
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
        return ConversationHandler.END
    
    # Кнопки админки
    if query.data == 'admin':
        await admin_panel(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_orders':
        await admin_orders(update, context)
        return ConversationHandler.END
    
    # НОВЫЕ КНОПКИ ДЛЯ ЗАКАЗОВ (пагинация, фильтры, очистка)
    if query.data.startswith('orders_page_') or query.data.startswith('orders_filter_'):
        await admin_orders(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_orders_cleanup':
        await admin_orders_cleanup(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('cleanup_'):
        await process_orders_cleanup(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_clients':
        await admin_clients(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_messages':
        await admin_messages(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_messages_all':
        await admin_messages_all(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_prices_menu':
        await admin_prices_menu(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_blacklist':
        await admin_blacklist_menu(update, context)
        return ConversationHandler.END
    
    if query.data == 'blacklist_add_user':
        await blacklist_add_user(update, context)
        return ConversationHandler.END
    
    # НОВАЯ КНОПКА: Удаление из черного списка
    if query.data == 'blacklist_remove_user':
        await blacklist_remove_user(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_broadcast':
        await admin_broadcast(update, context)
        return ConversationHandler.END
    
    if query.data == 'broadcast_new':
        await broadcast_new(update, context)
        return ConversationHandler.END
    
    if query.data == 'broadcast_history':
        await broadcast_history(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_stats':
        await admin_stats(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_stats_detailed':
        await admin_stats_detailed(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_stats_charts':
        await admin_stats_charts(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_working_hours':
        await admin_working_hours(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_export':
        await admin_export(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_settings':
        await admin_settings(update, context)
        return ConversationHandler.END
    
    if query.data == 'toggle_test_mode':
        await toggle_test_mode(update, context)
        return ConversationHandler.END
    
    # Обработка действий с заказами
    if query.data.startswith('complete_') or query.data.startswith('confirm_') or query.data.startswith('cancel_'):
        await handle_admin_actions(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('show_user_id_'):
        await show_user_id(update, context)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def main(set_webhook=True):
    """Асинхронная функция запуска бота"""
    # Явная инициализация базы данных
    import database as db
    db.init_db()
    print("🚀 База данных проверена")
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # !!! В САМОМ НАЧАЛЕ определяем функцию отмены !!!
    async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        await update.message.reply_text("Действие отменено.")
        return ConversationHandler.END
    
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
            BAGS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_bags),
                CallbackQueryHandler(bags_callback, pattern='^bags_')
            ],
            CONFIRM_ORDER: [CallbackQueryHandler(final_confirm_order, pattern='^final_confirm$')],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )

    # ConversationHandler для отправки сообщений клиенту
    message_to_user_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_write_to_user, pattern='^admin_write_to_user$'),
            CallbackQueryHandler(admin_write_to_user, pattern='^write_to_user_')
        ],
        states={
            ENTER_USER_ID_FOR_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_user_id_for_message)],
            SEND_MESSAGE_TO_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_user)],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для избранных адресов (добавление)
    favorite_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(favorite_add, pattern='^favorite_add$')],
        states={
            FAVORITE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, favorite_save)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для редактирования избранных адресов
    favorite_edit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_favorite_name, pattern='^edit_name_')
        ],
        states={
            EDIT_FAVORITE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_favorite_name)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для черного списка (с добавлением удаления)
    blacklist_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(blacklist_add_user, pattern='^blacklist_add_user$'),
            CallbackQueryHandler(blacklist_remove_user, pattern='^blacklist_remove_user$')
        ],
        states={
            BLACKLIST_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_add_process)],
            BLACKLIST_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_remove_process)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для рассылки
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_new, pattern='^broadcast_new$')],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для сообщений в поддержку
    support_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_start, pattern='^support_write$')],
        states={
            SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_message)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для приветствия (ЭТО ГЛАВНЫЙ ОБРАБОТЧИК /start)
    welcome_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WELCOME: [CallbackQueryHandler(button_handler, pattern='^(welcome_yes|welcome_no)$')]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для редактирования цен
    price_edit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_price_start, pattern='^edit_price_')
        ],
        states={
            EDITING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_price)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для времени работы
    working_hours_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_start_hour, pattern='^edit_start_hour$'),
            CallbackQueryHandler(edit_end_hour, pattern='^edit_end_hour$')
        ],
        states={
            EDIT_WORKING_HOURS_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_working_hours)],
            EDIT_WORKING_HOURS_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_working_hours)],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # Добавляем все обработчики В ПРАВИЛЬНОМ ПОРЯДКЕ
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(welcome_handler)
    app.add_handler(conv_handler)
    app.add_handler(message_to_user_handler)
    app.add_handler(favorite_handler)
    app.add_handler(favorite_edit_handler)
    app.add_handler(blacklist_handler)
    app.add_handler(broadcast_handler)
    app.add_handler(support_handler)
    app.add_handler(price_edit_handler)
    app.add_handler(working_hours_handler)
    app.add_handler(CallbackQueryHandler(button_handler))  # Обработчик кнопок
    app.add_handler(CallbackQueryHandler(toggle_test_mode, pattern='^toggle_test_mode$'))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    
    # Добавляем команду отмены
    app.add_handler(CommandHandler('cancel', cancel_command))
    
    if set_webhook:
        # Режим polling (для локальной разработки)
        print("🚀 Бот ЧистоBOT запущен в режиме polling...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)
    else:
        # Режим webhook (только инициализация)
        print("🚀 Бот ЧистоBOT инициализирован для webhook")
        await app.initialize()
        await app.start()
        return app