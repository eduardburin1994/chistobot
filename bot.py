# bot.py
# ========== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (ТОЛЬКО ДЛЯ ЛОКАЛЬНОЙ РАЗРАБОТКИ) ==========
import traceback
import os
from dotenv import load_dotenv
from pathlib import Path

# Проверяем, запущены ли мы на Render
if not os.environ.get('RENDER'):
    # Если не на Render - загружаем .env файл
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
    print("🚀 Загружен .env файл (локальный режим)")
# =====================================================================

import logging
import asyncio
import warnings
# Импорты для реферальной системы
from handlers.referral.core import referral_info, referral_history
from handlers.referral.stats import referral_top
from handlers.admin_access import admin_command_start, admin_login_check, admin_logout
from constants import ENTER_ADMIN_PASSWORD

# 👇 ДОБАВЬ ЭТУ СТРОКУ 👇
from handlers.courier_auth import courier_command_start, courier_login_check, courier_logout

# Импорты для мини-мессенджера
from handlers.messages.dialogs import admin_dialogs_list
from handlers.messages.dialog import admin_dialog_open, admin_dialog_mark_read
from handlers.messages.actions import (
    admin_dialog_reply, admin_dialog_send_reply,
    admin_dialog_delete, admin_dialog_delete_confirm,
    admin_show_phone
)
from handlers.messages.search import admin_messages_search, admin_messages_search_results
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
    bags_callback, confirm_order_before_final, repeat_order, final_confirm_order,
    use_bonus_handler  # Добавлен импорт
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
    blacklist_remove_user, blacklist_remove_process,
    admin_referral_stats,admin_delete_user, 
    admin_confirm_delete_user
    # Экспорт в Excel (закомментировано до добавления функций)
    # admin_export_menu, export_orders, export_orders_process,
    # export_clients, export_stats, export_blacklist, export_messages
)
from handlers.common import (
    start, welcome_callback, back_to_menu, show_prices, show_rules, show_contact, 
    handle_new_chat_members, rules_command, text_command_handler  # Добавлен импорт
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

    # ========== ОБРАБОТКА ДАТ ==========
    if query.data.startswith('date_'):
        print(f"🔥🔥🔥 ОБРАБОТКА ДАТЫ В button_handler: {query.data}")
        
        selected_date = query.data.replace('date_', '')
        print(f"📅 Выбрана дата: {selected_date}")
        
        from config import user_data
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['order_date'] = selected_date
        
        import database as db
        available_slots, slot_info = db.get_available_slots(selected_date)
        
        print(f"📅 Доступные слоты: {available_slots}")
        
        if not available_slots:
            from keyboards.client_keyboards import create_date_keyboard
            keyboard = create_date_keyboard()
            await query.edit_message_text(
                f"❌ На {selected_date} нет свободных слотов.\n"
                f"Пожалуйста, выберите другую дату:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return DATE
        
        time_keyboard = []
        for slot in available_slots:
            time_keyboard.append([InlineKeyboardButton(slot, callback_data=f'time_{slot}')])
        
        await query.edit_message_text(
            f"📅 Дата: {selected_date}\n\n"
            f"⏰ Выберите удобное время:",
            reply_markup=InlineKeyboardMarkup(time_keyboard)
        )
        return TIME

    # ========== ОБРАБОТКА ВРЕМЕНИ ==========
    if query.data.startswith('time_'):
        print(f"⏰ ОБРАБОТКА ВРЕМЕНИ В button_handler: {query.data}")
        
        selected_time = query.data.replace('time_', '')
        
        from config import user_data
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['order_time'] = selected_time
        
        from keyboards.client_keyboards import get_bags_keyboard
        await query.edit_message_text(
            f"📅 {user_data[user_id]['order_date']} {selected_time}\n\n"
            f"🛍 Шаг 3: Сколько мешков нужно вынести?",
            reply_markup=get_bags_keyboard()
        )
        return BAGS

    # ========== ОБРАБОТКА КОЛИЧЕСТВА МЕШКОВ ==========
    if query.data.startswith('bags_'):
        print(f"🛍 ОБРАБОТКА МЕШКОВ В button_handler: {query.data}")
        
        bags_count = int(query.data.replace('bags_', ''))
        
        from config import user_data
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['bags_count'] = bags_count
        
        from keyboards.client_keyboards import get_payment_keyboard
        await query.edit_message_text(
            f"🛍 Выбрано: <b>{bags_count} мешков</b>\n\n"
            f"💳 Шаг 4: Выберите способ оплаты",
            parse_mode='HTML',
            reply_markup=get_payment_keyboard()
        )
        return PAYMENT_METHOD

    # ========== ОБРАБОТКА ОПЛАТЫ ==========
    if query.data.startswith('pay_'):
        print(f"💳 ОБРАБОТКА ОПЛАТЫ В button_handler: {query.data}")
        
        payment_method = query.data.replace('pay_', '')
        
        from config import user_data
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['payment_method'] = payment_method
        
        # ==== ПРОВЕРЯЕМ, ЕСТЬ ЛИ ВСЕ НЕОБХОДИМЫЕ ДАННЫЕ ====
        # Если нет имени или телефона - запрашиваем их
        if 'name' not in user_data[user_id] or 'phone' not in user_data[user_id]:
            print(f"⚠️ Нет имени или телефона, запрашиваем...")
            
            # Получаем данные пользователя из базы
            import database as db
            user_info = db.get_user_by_id(user_id)
            
            if user_info and user_info[2]:  # если есть имя
                user_data[user_id]['name'] = user_info[2]
            if user_info and user_info[4]:  # если есть телефон
                user_data[user_id]['phone'] = user_info[4]
            
            # Если всё ещё нет имени - запрашиваем
            if 'name' not in user_data[user_id]:
                await query.edit_message_text(
                    "📝 Шаг 1: Введите ваше имя:",
                    reply_markup=None
                )
                return NAME
            
            if 'phone' not in user_data[user_id]:
                await query.edit_message_text(
                    "📞 Шаг 2: Введите номер телефона:",
                    reply_markup=None
                )
                return PHONE
        
        # Если все данные есть - показываем подтверждение
        from handlers.client import confirm_order_before_final
        await confirm_order_before_final(update, context)
        return CONFIRM_ORDER

    # ========== ПОДТВЕРЖДЕНИЕ ЗАКАЗА ==========
    if query.data == 'final_confirm':
        print(f"🔍 НАЖАТА КНОПКА final_confirm для пользователя {user_id}")
        from handlers.client import final_confirm_order
        await final_confirm_order(update, context)
        return ConversationHandler.END

    # ========== ИСПОЛЬЗОВАНИЕ БОНУСОВ ==========
    if query.data in ['use_bonus_yes', 'use_bonus_no']:
        await use_bonus_handler(update, context)
        return USE_BONUS

    # Сначала обрабатываем точное совпадение
    if query.data == 'order_detail_select':
        await order_detail_select(update, context)
        return ConversationHandler.END

    # Кнопки админки
    if query.data == 'admin':
        await admin_panel(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_logout':
        await admin_logout(update, context)
        return ConversationHandler.END
    
    # Потом обрабатываем все, что начинается с order_detail_
    if query.data.startswith('order_detail_'):
        await admin_order_detail(update, context)
        return ConversationHandler.END
        
    # Реферальная система
    if query.data == 'referral_info':
        await referral_info(update, context)
        return ConversationHandler.END
    
    if query.data == 'referral_history':
        await referral_history(update, context)
        return ConversationHandler.END
    
    if query.data == 'referral_top':
        await referral_top(update, context)
        return ConversationHandler.END

    if query.data == 'admin_referral_stats':
        await admin_referral_stats(update, context)
        return ConversationHandler.END
        
    if query.data == 'referral_help':
        help_text = (
            "❓ <b>Как работает реферальная программа?</b>\n\n"
            "1️⃣ <b>Получи ссылку</b> в разделе 'Приведи друга'\n"
            "2️⃣ <b>Отправь друзьям</b>\n"
            "3️⃣ Когда друг сделает первый заказ — ты получишь <b>100 баллов</b>\n"
            "4️⃣ Если друг тоже пригласит кого-то — ты получишь <b>30 баллов</b> за реферала 2 уровня\n"
            "5️⃣ <b>300 баллов = бесплатный вывоз</b>\n"
            "6️⃣ Баллы можно использовать как скидку при заказе\n\n"
            "💡 <b>Совет:</b> Чем больше друзей, тем больше баллов!"
        )
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='referral_info')
            ]])
        )
        return ConversationHandler.END

    # Повтор заказа
    if query.data.startswith('repeat_order_'):
        from handlers.client import repeat_order
        await repeat_order(update, context)
        return ConversationHandler.END

    # Изменение адреса
    if query.data == 'change_address':
        user_id = query.from_user.id
        print(f"🔄 Пользователь {user_id} изменяет адрес")
        
        from config import user_data
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
    
    # Кнопки избранных адресов
    if query.data == 'favorite_menu':
        await favorite_addresses_menu(update, context)
        return ConversationHandler.END
    
    if query.data == 'favorite_add':
        await favorite_add(update, context)
        return ConversationHandler.END
    
    if query.data == 'favorite_add_new_address':
        print(f"➕ ДОБАВЛЕНИЕ НОВОГО АДРЕСА ИЗ ИЗБРАННОГО")
        
        user_id = query.from_user.id
        from config import user_data
        
        # Инициализируем данные пользователя
        if user_id not in user_data:
            user_data[user_id] = {}
        
        # Устанавливаем флаг, что это добавление из избранного
        user_data[user_id]['adding_from_favorites'] = True
        
        # Запрашиваем адрес
        await query.edit_message_text(
            "🏠 <b>Добавление нового адреса в избранное</b>\n\n"
            "Введите адрес (улица и номер дома):\n"
            "<i>Например: ул. Ленина, д. 10</i>",
            parse_mode='HTML'
        )
        return NEW_ADDRESS

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
    
    if query.data == 'back_to_bags':
        await back_to_bags(update, context)
        return ConversationHandler.END
    
    # ========== ВОЗВРАТ К ВЫБОРУ ВРЕМЕНИ ==========
    if query.data in ['back_to_times', 'back_to_dates']:
        print(f"⏪ ВОЗВРАТ К ВЫБОРУ ВРЕМЕНИ: {query.data}")
        
        from config import user_data
        user_id = query.from_user.id
        
        # Получаем сохраненную дату
        order_date = user_data.get(user_id, {}).get('order_date')
        
        if not order_date:
            # Если дата не сохранена - возвращаем к выбору даты
            from keyboards.client_keyboards import create_date_keyboard
            await query.edit_message_text(
                "📅 Выберите дату:",
                reply_markup=InlineKeyboardMarkup(create_date_keyboard())
            )
            return DATE
        
        # Получаем доступные слоты для этой даты
        import database as db
        available_slots, slot_info = db.get_available_slots(order_date)
        
        if not available_slots:
            # Если нет слотов - возвращаем к выбору другой даты
            from keyboards.client_keyboards import create_date_keyboard
            await query.edit_message_text(
                f"❌ На {order_date} больше нет свободных слотов.\n"
                f"Пожалуйста, выберите другую дату:",
                reply_markup=InlineKeyboardMarkup(create_date_keyboard())
            )
            return DATE
        
        # Показываем доступные слоты времени
        time_keyboard = []
        for slot in available_slots:
            time_keyboard.append([InlineKeyboardButton(slot, callback_data=f'time_{slot}')])
        
        # Добавляем кнопку возврата к датам
        time_keyboard.append([InlineKeyboardButton("◀️ К выбору даты", callback_data="back_to_date_selection")])
        
        await query.edit_message_text(
            f"📅 Дата: {order_date}\n\n"
            f"⏰ Выберите удобное время:",
            reply_markup=InlineKeyboardMarkup(time_keyboard)
        )
        return TIME
    
    # ========== ВОЗВРАТ К ВЫБОРУ ДАТЫ ==========
    if query.data == 'back_to_date_selection':
        print(f"📅 ВОЗВРАТ К ВЫБОРУ ДАТЫ")
        
        from keyboards.client_keyboards import create_date_keyboard
        await query.edit_message_text(
            "📅 Выберите дату:",
            reply_markup=InlineKeyboardMarkup(create_date_keyboard())
        )
        return DATE
    
    # Кнопки админки
    if query.data == 'admin_write_to_user':
        await admin_write_to_user(update, context)
        return ConversationHandler.END
    
    if query.data == 'admin_orders':
        await admin_orders(update, context)
        return ConversationHandler.END
    
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
    
    # ============= МИНИ-МЕССЕНДЖЕР =============
    if query.data.startswith('admin_dialogs_'):
        await admin_dialogs_list(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('dialog_open_'):
        await admin_dialog_open(update, context)
        return DIALOG_VIEW
    
    if query.data.startswith('dialog_reply_'):
        await admin_dialog_reply(update, context)
        return DIALOG_REPLY
    
    if query.data.startswith('dialog_mark_read_'):
        await admin_dialog_mark_read(update, context)
        return DIALOG_VIEW
    
    if query.data.startswith('dialog_delete_confirm_'):
        await admin_dialog_delete_confirm(update, context)
        return DIALOG_VIEW
    
    if query.data.startswith('dialog_delete_'):
        await admin_dialog_delete(update, context)
        return DIALOG_VIEW
    
    if query.data.startswith('show_phone_'):
        await admin_show_phone(update, context)
        return DIALOG_VIEW
    
    if query.data == 'admin_messages_search':
        await admin_messages_search(update, context)
        return SEARCH_MESSAGES
    
    if query.data == 'admin_messages_trash':
        await query.edit_message_text(
            "🗑 <b>Корзина</b>\n\nФункция в разработке",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin_messages')
            ]])
        )
        return ConversationHandler.END
    
    # Обработка действий с заказами
    if query.data.startswith('complete_') or query.data.startswith('confirm_') or query.data.startswith('cancel_'):
        await handle_admin_actions(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('show_user_id_'):
        await show_user_id(update, context)
        return ConversationHandler.END
    
    # Возврат заказа в работу
    if query.data.startswith('reopen_'):
        await reopen_order(update, context)
        return ConversationHandler.END
    
    return ConversationHandler.END



async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки и не дает боту упасть."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # Отправляем сообщение админу
    try:
        error_trace = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        message = f"❌ Произошла ошибка:\n`{error_trace[-3500:]}`"
        await context.bot.send_message(chat_id=MAIN_ADMIN_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке админу: {e}")

# !!! ЭТА ЧАСТЬ ДОЛЖНА БЫТЬ ВНЕ error_handler !!!
async def main(set_webhook=True):
    """Асинхронная функция запуска бота"""
    # Явная инициализация базы данных
    import database as db
    db.init_db()
    db.init_referral_tables()
    db.debug_messages_table()
    db.check_database_integrity()
    print("🚀 База данных проверена")
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()

    # Определяем функцию отмены
    async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        user_id = update.effective_user.id
        
        # Сбрасываем флаг процесса заказа
        from config import user_data
        if user_id in user_data:
            user_data[user_id]['in_order_process'] = False
            print(f"🔄 Заказ отменён пользователем {user_id}, флаг сброшен")
        
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

    # ConversationHandler для входа в админку
    admin_login_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_command_start)],
        states={
            ENTER_ADMIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_login_check)]
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
    
    # ConversationHandler для черного списка
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
    
    # ConversationHandler для приветствия
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
    
    # ConversationHandler для ответов в диалогах
    dialog_reply_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_dialog_reply, pattern='^dialog_reply_')],
        states={
            DIALOG_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_dialog_send_reply)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ConversationHandler для поиска сообщений
    messages_search_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_messages_search, pattern='^admin_messages_search$')],
        states={
            SEARCH_MESSAGES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_messages_search_results)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )
    
    # ============== ДОБАВЛЯЕМ ВСЕ ОБРАБОТЧИКИ ==============
    # Английские команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("courier", courier_command_start))
    app.add_handler(CommandHandler("admin", admin_command_start))
    
    # Команда отмены
    app.add_handler(CommandHandler('cancel', cancel_command))
    
    app.add_error_handler(error_handler)

    # ConversationHandler'ы
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
    app.add_handler(admin_login_handler)
    app.add_handler(dialog_reply_handler)
    app.add_handler(messages_search_handler)
    app.add_handler(CallbackQueryHandler(admin_delete_user, pattern='^delete_user_'))
    app.add_handler(CallbackQueryHandler(admin_confirm_delete_user, pattern='^confirm_delete_user_'))
    
    # Обработчики кнопок с pattern
    app.add_handler(CallbackQueryHandler(toggle_test_mode, pattern='^toggle_test_mode$'))
    
    # Общий обработчик кнопок (В САМОМ КОНЦЕ!)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    
    # ============== ОБРАБОТЧИК ТЕКСТОВЫХ КОМАНД (русские аналоги) ==============
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_command_handler), group=2)

    print(f"🔍 [ОТЛАДКА] set_webhook = {set_webhook}")
    
    if set_webhook:
        # Режим webhook (для Render)
        print("🚀 Бот ЧистоBOT инициализирован для webhook")
        await app.initialize()
        await app.start()
        
        # Отладка для app.py
        print(f"🔍 Отладка: main() возвращает {app}")
        print(f"🔍 Отладка: есть ли app.bot? {hasattr(app, 'bot')}")
        
        return app
    else:
        # Режим polling (для локальной разработки)
        print("🚀 Бот ЧистоBOT запущен в режиме polling...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)

# ============== ЗАПУСК БОТА ==============
if __name__ == "__main__":
    # Определяем режим запуска в зависимости от окружения
    import os
    
    # ОТЛАДКА: печатаем все переменные окружения
    print("🔍 Переменные окружения:")
    print(f"RENDER: {os.environ.get('RENDER')}")
    print(f"PORT: {os.environ.get('PORT')}")
    print(f"Все переменные: {list(os.environ.keys())}")
    
    # Если есть переменная RENDER или PORT - значит мы на Render
    if os.environ.get('RENDER') or os.environ.get('PORT'):
        print("🚀 Запуск на Render в режиме webhook")
        asyncio.run(main(set_webhook=True))
    else:
        # Локальная разработка
        print("🚀 Запуск локально в режиме polling")
        asyncio.run(main(set_webhook=False))
        # Алиас для обратной совместимости
get_user_favorites = get_user_favorite_addresses