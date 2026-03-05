# handlers/admin.py
import html  # добавь в начале файла
from config import admin_data, WORK_HOURS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
import datetime
from constants import BLACKLIST_REMOVE, BROADCAST_MESSAGE, BLACKLIST_ADD, EDIT_WORKING_HOURS_START, EDIT_WORKING_HOURS_END, SEND_MESSAGE_TO_USER, ENTER_USER_ID_FOR_MESSAGE
import io
from utils.export import (
    export_orders_to_excel, export_clients_to_excel, export_stats_to_excel,
    export_blacklist_to_excel, export_messages_to_excel
)

async def admin_export_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню экспорта данных"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    text = (
        "📊 <b>ЭКСПОРТ ДАННЫХ</b>\n\n"
        "Выберите, что хотите экспортировать:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📦 Заказы", callback_data='export_orders')],
        [InlineKeyboardButton("👥 Клиенты", callback_data='export_clients')],
        [InlineKeyboardButton("📈 Статистика", callback_data='export_stats')],
        [InlineKeyboardButton("🚫 Чёрный список", callback_data='export_blacklist')],
        [InlineKeyboardButton("💬 Сообщения", callback_data='export_messages')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def export_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт заказов в Excel"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    # Сначала показываем меню выбора фильтра
    text = "📦 <b>Экспорт заказов</b>\n\nВыберите, какие заказы экспортировать:"
    
    keyboard = [
        [InlineKeyboardButton("📋 Все заказы", callback_data='export_orders_all')],
        [InlineKeyboardButton("🆕 Новые", callback_data='export_orders_new')],
        [InlineKeyboardButton("✅ Подтверждённые", callback_data='export_orders_confirmed')],
        [InlineKeyboardButton("✅ Выполненные", callback_data='export_orders_completed')],
        [InlineKeyboardButton("❌ Отменённые", callback_data='export_orders_cancelled')],
        [InlineKeyboardButton("📅 За сегодня", callback_data='export_orders_today')],
        [InlineKeyboardButton("📅 За неделю", callback_data='export_orders_week')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_export')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def export_orders_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка экспорта заказов с фильтром"""
    query = update.callback_query
    await query.answer()
    
    filter_type = query.data.replace('export_orders_', '')
    
    # Получаем заказы по фильтру
    import database as db
    all_orders = db.get_all_orders()
    
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%d.%m.%Y")
    
    if filter_type == 'all':
        orders = all_orders
        filename = f"orders_all_{today}.xlsx"
    elif filter_type == 'new':
        orders = [o for o in all_orders if o[13] == 'new']
        filename = f"orders_new_{today}.xlsx"
    elif filter_type == 'confirmed':
        orders = [o for o in all_orders if o[13] == 'confirmed']
        filename = f"orders_confirmed_{today}.xlsx"
    elif filter_type == 'completed':
        orders = [o for o in all_orders if o[13] == 'completed']
        filename = f"orders_completed_{today}.xlsx"
    elif filter_type == 'cancelled':
        orders = [o for o in all_orders if o[13] == 'cancelled']
        filename = f"orders_cancelled_{today}.xlsx"
    elif filter_type == 'today':
        orders = [o for o in all_orders if o[9] == today]
        filename = f"orders_today_{today}.xlsx"
    elif filter_type == 'week':
        orders = [o for o in all_orders if o[9] >= week_ago]
        filename = f"orders_week_{today}.xlsx"
    else:
        await query.edit_message_text("❌ Неизвестный фильтр")
        return
    
    if not orders:
        await query.edit_message_text("❌ Нет заказов для экспорта")
        return
    
    # Создаём Excel
    await query.edit_message_text("⏳ Создаю файл Excel, подождите...")
    
    try:
        excel_file = export_orders_to_excel(orders)
        
        # Отправляем файл
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_file,
            filename=filename,
            caption=f"📊 Экспорт заказов ({len(orders)} шт.)"
        )
        
        await query.edit_message_text("✅ Файл отправлен!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

async def export_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт клиентов в Excel"""
    query = update.callback_query
    await query.answer()
    
    import database as db
    clients = db.get_all_users()
    
    if not clients:
        await query.edit_message_text("❌ Нет клиентов для экспорта")
        return
    
    await query.edit_message_text("⏳ Создаю файл Excel, подождите...")
    
    try:
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        excel_file = export_clients_to_excel(clients)
        
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_file,
            filename=f"clients_{today}.xlsx",
            caption=f"📊 Экспорт клиентов ({len(clients)} шт.)"
        )
        
        await query.edit_message_text("✅ Файл отправлен!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

async def export_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт статистики в Excel"""
    query = update.callback_query
    await query.answer()
    
    import database as db
    orders = db.get_all_orders()
    users = db.get_all_users()
    
    # Собираем статистику
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    # Ежедневная статистика
    daily_stats = {}
    for o in orders:
        date = o[9]
        if date not in daily_stats:
            daily_stats[date] = {'orders': 0, 'revenue': 0, 'bags': 0}
        daily_stats[date]['orders'] += 1
        daily_stats[date]['revenue'] += o[12]
        daily_stats[date]['bags'] += o[11]
    
    stats_data = {
        'total_orders': len(orders),
        'new_orders': len([o for o in orders if o[13] == 'new']),
        'confirmed_orders': len([o for o in orders if o[13] == 'confirmed']),
        'completed_orders': len([o for o in orders if o[13] == 'completed']),
        'cancelled_orders': len([o for o in orders if o[13] == 'cancelled']),
        'total_clients': len(users),
        'active_clients': len([u for u in users if u[0] not in admin_data.get('blocked_users', [])]),
        'total_revenue': sum(o[12] for o in orders),
        'avg_check': sum(o[12] for o in orders) // len(orders) if orders else 0,
        'total_bags': sum(o[11] for o in orders),
        'daily_stats': [{'date': d, **s} for d, s in daily_stats.items()]
    }
    
    await query.edit_message_text("⏳ Создаю файл Excel, подождите...")
    
    try:
        excel_file = export_stats_to_excel(stats_data)
        
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_file,
            filename=f"stats_{today}.xlsx",
            caption="📊 Экспорт статистики"
        )
        
        await query.edit_message_text("✅ Файл отправлен!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

async def export_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт чёрного списка"""
    query = update.callback_query
    await query.answer()
    
    import database as db
    blacklist = db.get_blacklist()
    
    if not blacklist:
        await query.edit_message_text("📭 Чёрный список пуст")
        return
    
    await query.edit_message_text("⏳ Создаю файл Excel, подождите...")
    
    try:
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        excel_file = export_blacklist_to_excel(blacklist)
        
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_file,
            filename=f"blacklist_{today}.xlsx",
            caption=f"🚫 Чёрный список ({len(blacklist)} записей)"
        )
        
        await query.edit_message_text("✅ Файл отправлен!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

async def export_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт сообщений"""
    query = update.callback_query
    await query.answer()
    
    import database as db
    messages = db.get_all_messages()
    
    if not messages:
        await query.edit_message_text("📭 Нет сообщений для экспорта")
        return
    
    await query.edit_message_text("⏳ Создаю файл Excel, подождите...")
    
    try:
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        excel_file = export_messages_to_excel(messages)
        
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_file,
            filename=f"messages_{today}.xlsx",
            caption=f"💬 Сообщения ({len(messages)} шт.)"
        )
        
        await query.edit_message_text("✅ Файл отправлен!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

# Константы для пагинации
ORDERS_PER_PAGE = 5
ORDER_FILTER_ALL = 'all'
ORDER_FILTER_NEW = 'new'
ORDER_FILTER_CONFIRMED = 'confirmed'
ORDER_FILTER_COMPLETED = 'completed'
ORDER_FILTER_CANCELLED = 'cancelled'

async def reopen_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат заказа в статус confirmed"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    order_id = int(query.data.replace('reopen_', ''))
    db.update_order_status(order_id, 'confirmed')
    
    # Показываем обновлённый заказ
    await admin_order_detail(update, context)

async def notify_admin(update, context, admin_id, order_id):
    """Уведомление администратора о новом заказе"""
    order = db.get_order_by_id(order_id)
    if not order:
        return
    
    # order: (id, user_id, name, phone, street_address, entrance, floor, apartment, intercom, date, time, bags, price, status, created)
    # Формируем полный адрес
    full_address = order[4]  # street_address
    details = []
    if order[5]:  # entrance
        details.append(f"под. {order[5]}")
    if order[6]:  # floor
        details.append(f"эт. {order[6]}")
    if order[7]:  # apartment
        details.append(f"кв. {order[7]}")
    if order[8]:  # intercom
        details.append(f"домофон {order[8]}")
    
    if details:
        full_address += f" ({', '.join(details)})"
    
    # Получаем username клиента
    username = db.get_username_by_id(order[1])
    username_text = f" (@{username})" if username and username != "неизвестно" else ""
    
    text = (
        f"🚨 <b>НОВЫЙ ЗАКАЗ #{order_id} (НА ВЫНОС)</b>\n\n"
        f"👤 {order[2]}{username_text}\n"
        f"📞 {order[3]}\n"
        f"📍 {full_address}\n"
        f"📅 {order[9]} {order[10]}\n"
        f"🛍 {order[11]} пакетов\n"
        f"💰 {order[12]} ₽\n"
    )
    
    # Кнопки для админа
    keyboard = []
    
    # Кнопка связи если есть username
    if username and username != "неизвестно":
        clean_username = username.replace('@', '')
        keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{clean_username}")])
    
    # Кнопки управления заказом - теперь три!
    keyboard.append([
        InlineKeyboardButton("✅ Подтверждаю", callback_data=f'confirm_{order_id}'),
        InlineKeyboardButton("✅ Выполнено", callback_data=f'complete_{order_id}'),
        InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
    ])
    
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        print(f"✅ Уведомление о заказе #{order_id} отправлено админу {admin_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления админу {admin_id}: {e}")

# =============== НОВАЯ ФУНКЦИЯ ДЛЯ УВЕДОМЛЕНИЯ О СООБЩЕНИЯХ ===============

async def notify_admin_about_message(update, context, admin_id, user_id, username, first_name, message_text, message_id):
    """Уведомление администратора о новом сообщении от клиента"""
    try:
        # Получаем информацию о пользователе из базы
        user_info = db.get_user_by_id(user_id)
        phone = user_info[4] if user_info and len(user_info) > 4 else "не указан"
        
        # Формируем текст уведомления
        text = (
            f"💬 <b>НОВОЕ СООБЩЕНИЕ #{message_id}</b>\n\n"
            f"👤 {first_name}\n"
            f"🆔 {user_id}\n"
        )
        
        if username and username != "неизвестно":
            clean_username = username.replace('@', '')
            text += f"📱 <a href='https://t.me/{clean_username}'>@{username}</a>\n"
        else:
            text += f"📱 нет username\n"
        
        text += f"📞 {phone}\n"
        text += f"📅 {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        text += f"📝 <b>Сообщение:</b>\n{message_text}"
        
        # Кнопки для ответа
        keyboard = []

        # Если есть username - ссылка на Telegram
        if username and username != "неизвестно":
            clean_username = username.replace('@', '')
            keyboard.append([InlineKeyboardButton("💬 Ответить в Telegram", url=f"https://t.me/{clean_username}")])

        # НОВАЯ КНОПКА: Написать по ID (работает даже без username)
        keyboard.append([InlineKeyboardButton("✏️ Написать по ID", callback_data=f'write_to_user_{user_id}')])

        # Кнопка "Отметить как прочитано"
        keyboard.append([InlineKeyboardButton("✅ Отметить как прочитано", callback_data=f'mark_read_{message_id}')])

        # Кнопка перехода к списку сообщений
        keyboard.append([InlineKeyboardButton("📋 Все сообщения", callback_data='admin_messages')])
        
        await context.bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        print(f"✅ Уведомление о сообщении #{message_id} отправлено админу {admin_id}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления о сообщении админу {admin_id}: {e}")

async def admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальный просмотр конкретного заказа"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    # Получаем ID заказа из callback_data
    order_id = int(query.data.replace('order_detail_', ''))
    
    # Получаем заказ из базы
    import database as db
    order = db.get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    
    # БЕЗОПАСНАЯ РАСПАКОВКА через индексы
    order_id = order[0]
    user_id = order[1]
    name = order[2] if len(order) > 2 else ''
    phone = order[3] if len(order) > 3 else ''
    street = order[4] if len(order) > 4 else ''
    entrance = order[5] if len(order) > 5 else ''
    floor = order[6] if len(order) > 6 else ''
    apt = order[7] if len(order) > 7 else ''
    intercom = order[8] if len(order) > 8 else ''
    date = order[9] if len(order) > 9 else ''
    time = order[10] if len(order) > 10 else ''
    bags = order[11] if len(order) > 11 else 0
    price = order[12] if len(order) > 12 else 0
    status = order[13] if len(order) > 13 else 'unknown'
    created = order[14] if len(order) > 14 else ''
    
    # Получаем информацию о клиенте
    user_info = db.get_user_by_id(user_id)
    username = user_info[1] if user_info else None
    
    # Формируем полный адрес
    full_address = street
    details = []
    if entrance and entrance not in ['0', '-']:
        details.append(f"под. {entrance}")
    if floor and floor not in ['0', '-']:
        details.append(f"эт. {floor}")
    if apt and apt not in ['0', '-']:
        details.append(f"кв. {apt}")
    if intercom and intercom not in ['0', '-']:
        details.append(f"домофон {intercom}")
    if details:
        full_address += f" ({', '.join(details)})"
    
    # Статус
    status_emoji = {
        'new': '🆕', 
        'confirmed': '✅', 
        'completed': '✅', 
        'cancelled': '❌'
    }.get(status, '📝')
    
    status_text = {
        'new': 'Новый',
        'confirmed': 'Подтверждён',
        'completed': 'Выполнен',
        'cancelled': 'Отменён'
    }.get(status, status)
    
    # Формируем детальную информацию
    text = (
        f"{status_emoji} <b>ЗАКАЗ #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Клиент:</b> {name}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    )
    
    if username and username != "неизвестно":
        clean_username = username.replace('@', '')
        text += f"📱 <b>Username:</b> <a href='https://t.me/{clean_username}'>@{username}</a>\n"
    
    text += (
        f"📍 <b>Адрес:</b> {full_address}\n"
        f"📅 <b>Дата:</b> {date}\n"
        f"⏰ <b>Время:</b> {time}\n"
        f"🛍 <b>Пакетов:</b> {bags}\n"
        f"💰 <b>Сумма:</b> {price} ₽\n"
        f"📊 <b>Статус:</b> {status_emoji} {status_text}\n"
        f"📝 <b>Создан:</b> {created}\n"
    )
    
    # Кнопки действий
    keyboard = []
    
    # Кнопки связи
    contact_row = []
    if username and username != "неизвестно":
        clean_username = username.replace('@', '')
        contact_row.append(InlineKeyboardButton("💬 В Telegram", url=f"https://t.me/{clean_username}"))
    contact_row.append(InlineKeyboardButton("✏️ По ID", callback_data=f'write_to_user_{user_id}'))
    keyboard.append(contact_row)
    
    # Кнопки управления статусом
    if status == 'new':
        keyboard.append([
            InlineKeyboardButton("✅ Подтвердить", callback_data=f'confirm_{order_id}'),
            InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
        ])
        keyboard.append([InlineKeyboardButton("✅ Выполнить", callback_data=f'complete_{order_id}')])
    elif status == 'confirmed':
        keyboard.append([
            InlineKeyboardButton("✅ Выполнить", callback_data=f'complete_{order_id}'),
            InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
        ])
    elif status == 'completed':
        keyboard.append([InlineKeyboardButton("↩️ Вернуть в работу", callback_data=f'reopen_{order_id}')])
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton("◀️ Назад к списку", callback_data='admin_orders')])
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== ЧЕРНЫЙ СПИСОК ===============

async def admin_blacklist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню черного списка"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    blacklist = db.get_blacklist()
    
    text = "🚫 <b>ЧЕРНЫЙ СПИСОК</b>\n\n"
    
    if blacklist:
        for user in blacklist[:10]:
            user_id, reason, added_date, username, first_name, phone = user
            name = first_name or username or f"ID {user_id}"
            text += f"• <b>{name}</b>\n"
            text += f"  🆔 {user_id}\n"
            if reason:
                text += f"  📝 {reason}\n"
            text += f"  📅 {added_date}\n\n"
        text += f"Всего: {len(blacklist)} пользователей"
    else:
        text += "Черный список пуст"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить в ЧС", callback_data='blacklist_add_user')],
        [InlineKeyboardButton("➖ Удалить из ЧС", callback_data='blacklist_remove_user')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def blacklist_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление пользователя в черный список"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Введите ID пользователя для добавления в черный список:\n"
        "(можно узнать в разделе 'Все клиенты')"
    )
    return BLACKLIST_ADD

async def blacklist_add_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка добавления в ЧС"""
    try:
        user_id = int(update.message.text.strip())
        db.add_to_blacklist(user_id, "Добавлен администратором")
        
        await update.message.reply_text(
            f"✅ Пользователь {user_id} добавлен в черный список",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В админку", callback_data='admin')
            ]])
        )
    except ValueError:
        await update.message.reply_text("❌ Введите корректный ID")
    
    return ConversationHandler.END

async def blacklist_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления пользователя из ЧС"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return ConversationHandler.END
    
    await query.edit_message_text(
        "Введите ID пользователя для удаления из черного списка:"
    )
    return BLACKLIST_REMOVE

async def blacklist_remove_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления из ЧС"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    try:
        target_user_id = int(update.message.text.strip())
        
        # Удаляем из черного списка
        db.remove_from_blacklist(target_user_id)
        
        # Также удаляем из admin_data['blocked_users'] если есть
        if target_user_id in admin_data['blocked_users']:
            admin_data['blocked_users'].remove(target_user_id)
        
        await update.message.reply_text(
            f"✅ Пользователь {target_user_id} удален из черного списка",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В админку", callback_data='admin')
            ]])
        )
    except ValueError:
        await update.message.reply_text("❌ Введите корректный ID (только цифры)")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
    return ConversationHandler.END

# =============== РАССЫЛКА ===============

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню рассылки"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    broadcasts = db.get_all_broadcasts()
    
    text = "📢 <b>РАССЫЛКА УВЕДОМЛЕНИЙ</b>\n\n"
    
    if broadcasts:
        text += "Последние рассылки:\n"
        for b in broadcasts[:3]:
            b_id, admin_id, msg, date, count = b
            # Преобразуем datetime в строку
            if date:
                date_str = date.strftime("%d.%m.%Y")
            else:
                date_str = "неизвестно"
            # Экранируем HTML в сообщении
            safe_msg = html.escape(msg[:30])
            text += f"• {date_str}: {safe_msg}... ({count} пол.)\n"
        text += "\n"
    
    text += "Выберите действие:"
    
    keyboard = [
        [InlineKeyboardButton("📨 Сделать рассылку", callback_data='broadcast_new')],
        [InlineKeyboardButton("📋 История рассылок", callback_data='broadcast_history')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def broadcast_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Новая рассылка"""
    query = update.callback_query
    await query.answer()
    
    # Кнопка отмены
    cancel_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast')
    ]])
    
    await query.edit_message_text(
        "📝 Введите текст сообщения для рассылки всем клиентам:",
        reply_markup=cancel_keyboard
    )
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки"""
    admin_id = update.effective_user.id
    
    if admin_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    message_text = update.message.text
    
    # Кнопка отмены во время отправки
    await update.message.reply_text(
        "📨 Рассылка началась... это может занять некоторое время.\n"
        "Вы получите отчёт о результате."
    )
    
    # Получаем всех пользователей
    users = db.get_all_users()
    
    # Сохраняем рассылку
    broadcast_id = db.save_broadcast(admin_id, message_text)
    
    # Отправляем сообщения
    success = 0
    failed = 0
    
    for user in users:
        user_id = user[0]
        try:
            # Пропускаем заблокированных
            if user_id in admin_data['blocked_users']:
                continue
            
            # Формируем клавиатуру с кнопкой ответа
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Ответить", callback_data='support_write')
            ]])
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Рассылка от администратора</b>\n\n{message_text}",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            success += 1
        except Exception as e:
            failed += 1
            print(f"❌ Ошибка отправки пользователю {user_id}: {e}")
    
    # Обновляем статистику
    db.update_broadcast_count(broadcast_id, success)
    
    # Кнопка возврата
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Назад к рассылкам", callback_data='admin_broadcast')
    ]])
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n"
        f"📨 Успешно отправлено: {success}\n"
        f"❌ Не удалось отправить: {failed}",
        reply_markup=keyboard
    )
    
    return ConversationHandler.END

async def broadcast_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История рассылок"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    broadcasts = db.get_all_broadcasts()
    
    if not broadcasts:
        await query.edit_message_text(
            "📭 История рассылок пуста",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin_broadcast')
            ]])
        )
        return
    
    text = "📋 <b>ИСТОРИЯ РАССЫЛОК</b>\n\n"
    
    for i, b in enumerate(broadcasts[:10]):
        b_id, admin_id, msg, date, count = b
        
        # Преобразуем datetime в строку
        if date:
            date_str = date.strftime("%d.%m.%Y %H:%M")
        else:
            date_str = "неизвестно"
        
        # Обрезаем длинное сообщение
        short_msg = msg[:50] + "..." if len(msg) > 50 else msg
        
        text += f"<b>#{b_id}</b> от {date_str}\n"
        text += f"📝 {short_msg}\n"
        text += f"👥 Получателей: {count}\n\n"
    
    if len(broadcasts) > 10:
        text += f"... и ещё {len(broadcasts) - 10} рассылок"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад к рассылкам", callback_data='admin_broadcast')],
        [InlineKeyboardButton("📨 Новая рассылка", callback_data='broadcast_new')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== АДМИН ПАНЕЛЬ ===============

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель (компактная версия)"""
    query = update.callback_query
    
    if query.from_user.id not in admin_data['admins']:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await query.answer()
    
    orders = db.get_all_orders()
    clients = db.get_all_users()
    messages = db.get_all_messages()
    new_messages = sum(1 for m in messages if len(m) > 7 and m[7] == 'new') if messages else 0
    
    test_status = "🧪" if admin_data.get('test_mode', False) else "✅"
    
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    today_orders = [o for o in orders if o[9] == today] if orders else []
    
    # КОМПАКТНАЯ СТАТИСТИКА В ОДНУ СТРОКУ
    text = (
        f"👑 <b>АДМИН</b> {test_status}\n"
        f"📦 {len(today_orders)} | 👥 {len(clients)} | 💬 {new_messages}\n"
        f"💰 {admin_data['prices']['1']}/{admin_data['prices']['2']}/{admin_data['prices']['3+']}₽\n"
        f"⬇️ Выберите действие:"
    )
    
    # КОМПАКТНАЯ КЛАВИАТУРА (ПО 2 КНОПКИ В РЯДУ)
    keyboard = [
        [
            InlineKeyboardButton("📦 Заказы", callback_data='admin_orders'),
            InlineKeyboardButton("👥 Клиенты", callback_data='admin_clients')
        ],
        [
            InlineKeyboardButton("💬 Сообщения", callback_data='admin_messages'),
            InlineKeyboardButton("📢 Написать", callback_data='admin_write_to_user')
        ],
        [
            InlineKeyboardButton("💰 Цены", callback_data='admin_prices_menu'),
            InlineKeyboardButton("⏰ Время", callback_data='admin_working_hours')
        ],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast'),
            InlineKeyboardButton("🚫 ЧС", callback_data='admin_blacklist')
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
            InlineKeyboardButton("🧪 Тест", callback_data='toggle_test_mode')
        ],
        [
            InlineKeyboardButton("🎁 Рефералы", callback_data='admin_referral_stats'),  # ← НОВАЯ КНОПКА
            InlineKeyboardButton("📊 Экспорт", callback_data='admin_export_menu')
        ],
        [
            InlineKeyboardButton("🚪 Выйти", callback_data='admin_logout'),  # ← НОВАЯ КНОПКА
            InlineKeyboardButton("◀️ Меню", callback_data='back_to_menu')
        ]
    ]
    
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== УПРАВЛЕНИЕ ЗАКАЗАМИ ===============

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий админа с уведомлением клиента"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    # Проверяем тестовый режим
    test_mode = admin_data.get('test_mode', False)
    if test_mode:
        await query.edit_message_text("🧪 Тестовый режим: действие не выполнено")
        return
    
    if data.startswith('complete_'):
        order_id = int(data.replace('complete_', ''))
        
        # Сначала освобождаем слот и обновляем статус
        db.complete_order(order_id)
        
        order = db.get_order_by_id(order_id)
        if order:
            client_id = order[1]
            try:
                # Уведомление клиенту
                await context.bot.send_message(
                    chat_id=client_id,
                    text=f"✅ <b>Заказ #{order_id} выполнен!</b>\n\n"
                         f"Спасибо, что воспользовались нашим сервисом!\n"
                         f"Будем рады видеть вас снова.",
                    parse_mode='HTML'
                )
                print(f"✅ Уведомление о выполнении отправлено клиенту {client_id}")
            except Exception as e:
                print(f"❌ Не удалось уведомить клиента {client_id}: {e}")
        
        await query.edit_message_text(f"✅ Заказ #{order_id} выполнен, слот освобождён")
    
    elif data.startswith('confirm_'):
        order_id = int(data.replace('confirm_', ''))
        
        try:
            # Подтверждаем заказ
            db.confirm_order(order_id)
            
            order = db.get_order_by_id(order_id)
            if order:
                client_id = order[1]
                try:
                    # Уведомление клиенту о подтверждении
                    await context.bot.send_message(
                        chat_id=client_id,
                        text=f"✅ <b>Ваш заказ #{order_id} подтверждён!</b>\n\n"
                             f"Ожидайте курьера в назначенное время.\n"
                             f"Спасибо, что воспользовались нашим сервисом!",
                        parse_mode='HTML'
                    )
                    print(f"✅ Уведомление о подтверждении отправлено клиенту {client_id}")
                except Exception as e:
                    print(f"❌ Не удалось уведомить клиента {client_id}: {e}")
            
            await query.edit_message_text(f"✅ Заказ #{order_id} подтверждён")
            
        except Exception as e:
            print(f"❌ Ошибка при подтверждении заказа {order_id}: {e}")
            await query.edit_message_text(f"❌ Ошибка при подтверждении заказа #{order_id}")
    
    elif data.startswith('cancel_'):
        order_id = int(data.replace('cancel_', ''))
        
        # Отменяем заказ (функция уже удаляет слот)
        db.cancel_order(order_id)
        
        order = db.get_order_by_id(order_id)
        if order:
            client_id = order[1]
            try:
                # Уведомление клиенту об отмене
                await context.bot.send_message(
                    chat_id=client_id,
                    text=f"❌ <b>Заказ #{order_id} отменён</b>\n\n"
                         f"Если у вас есть вопросы, свяжитесь с поддержкой.",
                    parse_mode='HTML'
                )
                print(f"✅ Уведомление об отмене отправлено клиенту {client_id}")
            except Exception as e:
                print(f"❌ Не удалось уведомить клиента {client_id}: {e}")
        
        await query.edit_message_text(f"❌ Заказ #{order_id} отменён, слот освобождён")

# =============== СТАТИСТИКА ===============

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшенная статистика"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    orders = db.get_all_orders()
    users = db.get_all_users()
    
    # Общая статистика по заказам с учётом новых статусов
    total_orders = len(orders)
    new_orders = [o for o in orders if o[13] == 'new']
    confirmed_orders = [o for o in orders if o[13] == 'confirmed']
    completed = [o for o in orders if o[13] == 'completed']
    cancelled = [o for o in orders if o[13] == 'cancelled']
    
    # Статистика по дням
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    today_orders = [o for o in orders if o[9] == today]
    
    # Статистика по неделе
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    week_orders = []
    for o in orders:
        try:
            order_date = datetime.datetime.strptime(o[9], "%d.%m.%Y")
            if order_date >= week_ago:
                week_orders.append(o)
        except:
            pass
    
    # Финансовая статистика
    total_revenue = sum(o[12] for o in orders)
    today_revenue = sum(o[12] for o in today_orders)
    week_revenue = sum(o[12] for o in week_orders)
    
    # Средний чек
    avg_check = total_revenue / total_orders if total_orders > 0 else 0
    
    # Статистика по пакетам
    total_bags = sum(o[11] for o in orders)
    avg_bags = total_bags / total_orders if total_orders > 0 else 0
    
    # Самая популярная дата/время
    time_stats = {}
    for o in orders:
        time_slot = o[10]  # order_time
        time_stats[time_slot] = time_stats.get(time_slot, 0) + 1
    
    most_popular_time = max(time_stats.items(), key=lambda x: x[1]) if time_stats else ("нет данных", 0)
    
    # Статистика по дням недели
    day_stats = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    for o in orders:
        try:
            order_date = datetime.datetime.strptime(o[9], "%d.%m.%Y")
            day_stats[order_date.weekday()] += 1
        except:
            pass
    
    most_popular_day = max(day_stats.items(), key=lambda x: x[1])
    
    text = (
        f"📊 <b>РАСШИРЕННАЯ СТАТИСТИКА</b>\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• За сегодня: {today_revenue} ₽\n"
        f"• За неделю: {week_revenue} ₽\n"
        f"• Всего: {total_revenue} ₽\n"
        f"• Средний чек: {avg_check:.0f} ₽\n\n"
        
        f"📅 <b>Заказы:</b>\n"
        f"• За сегодня: {len(today_orders)}\n"
        f"• За неделю: {len(week_orders)}\n"
        f"• Всего: {total_orders}\n\n"
        
        f"📦 <b>Статусы:</b>\n"
        f"• 🆕 Новых: {len(new_orders)}\n"
        f"• ✅ Подтверждённых: {len(confirmed_orders)}\n"
        f"• ✅ Выполнено: {len(completed)}\n"
        f"• ❌ Отменено: {len(cancelled)}\n\n"
        
        f"🛍 <b>Пакеты:</b>\n"
        f"• Всего вынесено: {total_bags} пакетов\n"
        f"• В среднем: {avg_bags:.1f} пакета/заказ\n\n"
        
        f"⏰ <b>Популярное время:</b>\n"
        f"• {most_popular_time[0]} — {most_popular_time[1]} заказов\n"
        f"• Популярный день: {days_names[most_popular_day[0]]} — {most_popular_day[1]} заказов\n\n"
        
        f"👥 <b>Клиенты:</b>\n"
        f"• Всего: {len(users)}\n"
        f"• Активных: {len([u for u in users if u[0] not in admin_data.get('blocked_users', [])])}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Детальная статистика", callback_data='admin_stats_detailed')],
        [InlineKeyboardButton("📈 Графики", callback_data='admin_stats_charts')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats_detailed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальная статистика по дням"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    orders = db.get_all_orders()
    
    # Группировка по датам
    daily_stats = {}
    for o in orders:
        date = o[9]
        if date not in daily_stats:
            daily_stats[date] = {'count': 0, 'revenue': 0, 'bags': 0, 'new': 0, 'confirmed': 0, 'completed': 0, 'cancelled': 0}
        daily_stats[date]['count'] += 1
        daily_stats[date]['revenue'] += o[12]
        daily_stats[date]['bags'] += o[11]
        
        # Считаем по статусам
        status = o[13]
        if status == 'new':
            daily_stats[date]['new'] += 1
        elif status == 'confirmed':
            daily_stats[date]['confirmed'] += 1
        elif status == 'completed':
            daily_stats[date]['completed'] += 1
        elif status == 'cancelled':
            daily_stats[date]['cancelled'] += 1
    
    # Сортируем по дате (последние 7 дней)
    sorted_dates = sorted(daily_stats.keys(), reverse=True)[:7]
    
    text = "📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА (последние 7 дней)</b>\n\n"
    
    for date in sorted_dates:
        stats = daily_stats[date]
        text += f"<b>{date}:</b>\n"
        text += f"  • Заказов: {stats['count']}\n"
        text += f"  • Выручка: {stats['revenue']} ₽\n"
        text += f"  • Пакетов: {stats['bags']}\n"
        text += f"  • Статусы: 🆕{stats['new']} ✅{stats['confirmed']} ✅{stats['completed']} ❌{stats['cancelled']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад к статистике", callback_data='admin_stats')],
        [InlineKeyboardButton("◀️ В админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats_charts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Визуальная статистика (текстовые графики)"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    orders = db.get_all_orders()
    
    # Статистика по часам
    hour_stats = {}
    for o in orders:
        time_slot = o[10].split('-')[0]  # берём только начало
        hour_stats[time_slot] = hour_stats.get(time_slot, 0) + 1
    
    text = "📈 <b>ГРАФИКИ (текстовое представление)</b>\n\n"
    text += "<b>Заказы по времени:</b>\n"
    
    # Сортируем по часу
    sorted_hours = sorted(hour_stats.keys())
    max_count = max(hour_stats.values()) if hour_stats else 1
    
    for hour in sorted_hours:
        count = hour_stats[hour]
        bar_length = int(20 * count / max_count)
        bar = "█" * bar_length
        text += f"{hour}: {bar} {count}\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад к статистике", callback_data='admin_stats')],
        [InlineKeyboardButton("◀️ В админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== УПРАВЛЕНИЕ ВРЕМЕНЕМ РАБОТЫ ===============

async def admin_working_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления временем работы"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    from config import WORK_HOURS
    
    text = (
        "⏰ <b>ВРЕМЯ РАБОТЫ БОТА</b>\n\n"
        f"Текущее время работы:\n"
        f"• Начало: {WORK_HOURS['start']}:00\n"
        f"• Окончание: {WORK_HOURS['end']}:00\n\n"
        "Выберите, что хотите изменить:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Время начала", callback_data='edit_start_hour')],
        [InlineKeyboardButton("✏️ Время окончания", callback_data='edit_end_hour')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_start_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение времени начала работы"""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем тип редактирования
    context.user_data['editing_working_hours'] = 'start'
    
    await query.edit_message_text(
        "Введите новое время начала работы (час от 0 до 23):\n"
        "Например: 10"
    )
    return EDIT_WORKING_HOURS_START

async def edit_end_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение времени окончания работы"""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем тип редактирования
    context.user_data['editing_working_hours'] = 'end'
    
    await query.edit_message_text(
        "Введите новое время окончания работы (час от 1 до 24):\n"
        "Например: 22"
    )
    return EDIT_WORKING_HOURS_END

async def set_working_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка нового времени работы"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    try:
        hour = int(update.message.text)
        editing_type = context.user_data.get('editing_working_hours')
        
        if not editing_type:
            # Если тип не сохранён, пытаемся определить по состоянию
            if context.user_data.get('EDIT_WORKING_HOURS_START'):
                editing_type = 'start'
            elif context.user_data.get('EDIT_WORKING_HOURS_END'):
                editing_type = 'end'
            else:
                await update.message.reply_text("❌ Ошибка: не удалось определить, что вы меняете")
                return ConversationHandler.END
        
        from config import WORK_HOURS
        
        if editing_type == 'start':
            if 0 <= hour <= 23:
                WORK_HOURS['start'] = hour
                await update.message.reply_text(
                    f"✅ Время начала работы изменено на {hour}:00",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Назад к времени работы", callback_data='admin_working_hours')
                    ]])
                )
            else:
                await update.message.reply_text("❌ Введите час от 0 до 23!")
                return EDIT_WORKING_HOURS_START
        elif editing_type == 'end':
            if 1 <= hour <= 24:
                WORK_HOURS['end'] = hour
                await update.message.reply_text(
                    f"✅ Время окончания работы изменено на {hour}:00",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Назад к времени работы", callback_data='admin_working_hours')
                    ]])
                )
            else:
                await update.message.reply_text("❌ Введите час от 1 до 24!")
                return EDIT_WORKING_HOURS_END
                
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        # Определяем, какое состояние вернуть
        editing_type = context.user_data.get('editing_working_hours')
        if editing_type == 'start':
            return EDIT_WORKING_HOURS_START
        else:
            return EDIT_WORKING_HOURS_END
    
    return ConversationHandler.END

# =============== ОТПРАВКА СООБЩЕНИЙ КЛИЕНТАМ ===============

async def admin_write_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки сообщения клиенту по ID"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    # Если передан конкретный user_id (из кнопки)
    data = query.data
    if data.startswith('write_to_user_'):
        user_id = int(data.replace('write_to_user_', ''))
        context.user_data['write_to_user_id'] = user_id
        
        # Получаем информацию о пользователе
        user_info = db.get_user_by_id(user_id)
        if user_info:
            name = user_info[2] or user_info[1] or f"ID {user_id}"
            
            # Кнопка отмены
            cancel_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data='admin')
            ]])
            
            await query.edit_message_text(
                f"✏️ <b>Написать пользователю {name}</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📞 Телефон: {user_info[4] or 'не указан'}\n\n"
                f"Введите текст сообщения для отправки:",
                parse_mode='HTML',
                reply_markup=cancel_keyboard
            )
            return SEND_MESSAGE_TO_USER
        else:
            await query.edit_message_text(
                "❌ Пользователь не найден",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data='admin_clients')
                ]])
            )
            return ConversationHandler.END
    
    # Если просто вызвали команду (без ID) - добавляем кнопку отмены
    cancel_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Отмена", callback_data='admin')
    ]])
    
    await query.edit_message_text(
        "✏️ <b>Отправка сообщения клиенту</b>\n\n"
        "Введите ID пользователя, которому хотите написать:",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    return ENTER_USER_ID_FOR_MESSAGE

async def enter_user_id_for_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ID пользователя для отправки сообщения"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    try:
        target_user_id = int(update.message.text.strip())
        context.user_data['write_to_user_id'] = target_user_id
        
        # Проверяем, есть ли такой пользователь в базе
        user_info = db.get_user_by_id(target_user_id)
        
        if user_info:
            name = user_info[2] or user_info[1] or f"ID {target_user_id}"
            
            # Кнопка отмены
            cancel_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data='admin')
            ]])
            
            await update.message.reply_text(
                f"✏️ <b>Написать пользователю {name}</b>\n\n"
                f"🆔 ID: <code>{target_user_id}</code>\n"
                f"📞 Телефон: {user_info[4] or 'не указан'}\n\n"
                f"Введите текст сообщения для отправки:",
                parse_mode='HTML',
                reply_markup=cancel_keyboard
            )
            return SEND_MESSAGE_TO_USER
        else:
            # Кнопка отмены при ошибке
            cancel_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data='admin')
            ]])
            
            await update.message.reply_text(
                "❌ Пользователь с таким ID не найден в базе.\n"
                "Попробуйте другой ID:",
                reply_markup=cancel_keyboard
            )
            return ENTER_USER_ID_FOR_MESSAGE
            
    except ValueError:
        # Кнопка отмены при ошибке ввода
        cancel_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='admin')
        ]])
        
        await update.message.reply_text(
            "❌ Введите корректный ID (только цифры):",
            reply_markup=cancel_keyboard
        )
        return ENTER_USER_ID_FOR_MESSAGE

async def send_message_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка сообщения клиенту"""
    admin_id = update.effective_user.id
    
    if admin_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    target_user_id = context.user_data.get('write_to_user_id')
    message_text = update.message.text
    
    if not target_user_id:
        await update.message.reply_text(
            "❌ Ошибка: ID пользователя не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В админку", callback_data='admin')
            ]])
        )
        return ConversationHandler.END
    
    try:
        # Отправляем сообщение клиенту
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Ответить администратору", callback_data='support_write')
        ]])
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📢 <b>Сообщение от администратора</b>\n\n{message_text}",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        # Сохраняем в историю сообщений
        db.save_message(target_user_id, f"[ОТ АДМИНА] {message_text}")
        
        # Уведомляем админа об успехе
        await update.message.reply_text(
            f"✅ <b>Сообщение отправлено!</b>\n\n"
            f"Пользователю с ID: <code>{target_user_id}</code>\n"
            f"Текст: {message_text}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В админку", callback_data='admin')
            ]])
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка отправки</b>\n\n"
            f"Не удалось отправить сообщение пользователю {target_user_id}.\n"
            f"Возможно, пользователь не запускал бота или заблокировал его.\n\n"
            f"Ошибка: {e}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В админку", callback_data='admin')
            ]])
        )
    
    # Очищаем данные
    if 'write_to_user_id' in context.user_data:
        del context.user_data['write_to_user_id']
    
    return ConversationHandler.END

# =============== ОСТАЛЬНЫЕ ФУНКЦИИ ===============

async def toggle_test_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включение/выключение тестового режима"""
    query = update.callback_query
    await query.answer()
    
    admin_data['test_mode'] = not admin_data.get('test_mode', False)
    status = "🧪 ВКЛЮЧЕН" if admin_data['test_mode'] else "✅ ВЫКЛЮЧЕН"
    
    await query.edit_message_text(
        f"Тестовый режим: {status}\n\n"
        f"В тестовом режиме заказы не сохраняются в базу данных.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data='admin')
        ]])
    )

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр заказов с пагинацией и фильтрацией (компактный вид)"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    # Получаем параметры из callback_data или устанавливаем по умолчанию
    data = query.data
    
    # Определяем текущую страницу и фильтр
    if data == 'admin_orders':
        page = 0
        filter_type = ORDER_FILTER_ALL
    elif data.startswith('orders_page_'):
        parts = data.replace('orders_page_', '').split('_')
        page = int(parts[0])
        filter_type = parts[1] if len(parts) > 1 else ORDER_FILTER_ALL
    elif data.startswith('orders_filter_'):
        filter_type = data.replace('orders_filter_', '')
        page = 0
    else:
        page = 0
        filter_type = ORDER_FILTER_ALL
    
    context.user_data['orders_page'] = page
    context.user_data['orders_filter'] = filter_type
    
    all_orders = db.get_all_orders()
    
    # Фильтруем по статусу
    filter_config = {
        ORDER_FILTER_ALL: (all_orders, "📋 ВСЕ ЗАКАЗЫ"),
        ORDER_FILTER_NEW: ([o for o in all_orders if o[13] == 'new'], "🆕 НОВЫЕ"),
        ORDER_FILTER_CONFIRMED: ([o for o in all_orders if o[13] == 'confirmed'], "✅ ПОДТВЕРЖДЁННЫЕ"),
        ORDER_FILTER_COMPLETED: ([o for o in all_orders if o[13] == 'completed'], "✅ ВЫПОЛНЕННЫЕ"),
        ORDER_FILTER_CANCELLED: ([o for o in all_orders if o[13] == 'cancelled'], "❌ ОТМЕНЁННЫЕ"),
    }
    
    filtered_orders, filter_name = filter_config.get(filter_type, (all_orders, "📋 ВСЕ ЗАКАЗЫ"))
    
    total_orders = len(filtered_orders)
    total_pages = (total_orders + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
    
    # Корректируем страницу
    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0
    
    start_idx = page * ORDERS_PER_PAGE
    end_idx = min(start_idx + ORDERS_PER_PAGE, total_orders)
    
    # Если нет заказов
    if total_orders == 0:
        text = f"{filter_name}\n\n📭 Нет заказов в этой категории"
        keyboard = [
            [
                InlineKeyboardButton("🆕 Новые", callback_data='orders_filter_new'),
                InlineKeyboardButton("✅ Подтв.", callback_data='orders_filter_confirmed')
            ],
            [
                InlineKeyboardButton("✅ Выполн.", callback_data='orders_filter_completed'),
                InlineKeyboardButton("❌ Отмен.", callback_data='orders_filter_cancelled')
            ],
            [InlineKeyboardButton("📋 Все заказы", callback_data='orders_filter_all')],
            [InlineKeyboardButton("🗑 Очистка", callback_data='admin_orders_cleanup')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
        ]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ЗАГОЛОВОК
    text = f"🔍 <b>{filter_name}</b> | {page+1}/{total_pages} | {total_orders} зак.\n\n"
    
    # КОМПАКТНЫЙ СПИСОК ЗАКАЗОВ
    current_orders = []
    for i, order in enumerate(filtered_orders[start_idx:end_idx], 1):
        # Безопасная распаковка через индексы
        order_id = order[0]
        user_id = order[1]
        name = order[2] if len(order) > 2 else ''
        phone = order[3] if len(order) > 3 else ''
        street = order[4] if len(order) > 4 else ''
        entrance = order[5] if len(order) > 5 else ''
        floor = order[6] if len(order) > 6 else ''
        apt = order[7] if len(order) > 7 else ''
        intercom = order[8] if len(order) > 8 else ''
        date = order[9] if len(order) > 9 else ''
        time = order[10] if len(order) > 10 else ''
        bags = order[11] if len(order) > 11 else 0
        price = order[12] if len(order) > 12 else 0
        status = order[13] if len(order) > 13 else 'unknown'
        created = order[14] if len(order) > 14 else ''
        
        current_orders.append(order_id)
        
        status_emoji = {
            'new': '🆕', 
            'confirmed': '✅', 
            'completed': '✅', 
            'cancelled': '❌'
        }.get(status, '📝')
        
        # Короткий адрес
        short_address = street.split(',')[0][:20]
        if apt and apt not in ['0', '-']:
            short_address += f" кв.{apt}"
        
        # Текст заказа
        text += f"{status_emoji} #{order_id} {name[:15]} | {short_address} | {bags}меш | {price}₽\n"
        text += f"   📅 {date} {time} | 👤 ID{user_id}\n\n"
    
    # СОЗДАЕМ КЛАВИАТУРУ
    keyboard = []
    
    # Кнопки фильтров (первый ряд)
    keyboard.append([
        InlineKeyboardButton("🆕 Новые", callback_data='orders_filter_new'),
        InlineKeyboardButton("✅ Подтв.", callback_data='orders_filter_confirmed')
    ])
    keyboard.append([
        InlineKeyboardButton("✅ Выполн.", callback_data='orders_filter_completed'),
        InlineKeyboardButton("❌ Отмен.", callback_data='orders_filter_cancelled')
    ])
    keyboard.append([InlineKeyboardButton("📋 Все заказы", callback_data='orders_filter_all')])
    
    # Кнопки для каждого заказа (переход к деталям)
    for order_id in current_orders:
        keyboard.append([InlineKeyboardButton(f"🔍 Заказ #{order_id}", callback_data=f'order_detail_{order_id}')])
    
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f'orders_page_{page-1}_{filter_type}'))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f'orders_page_{page+1}_{filter_type}'))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton("🗑 Очистка", callback_data='admin_orders_cleanup'),
        InlineKeyboardButton("◀️ Назад", callback_data='admin')
    ])
    
    # Отправляем сообщение
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        # Если сообщение не изменилось, просто игнорируем
        if "Message is not modified" not in str(e):
            print(f"Ошибка: {e}")

async def admin_orders_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка старых/выполненных заказов"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    text = (
        "🗑 <b>ОЧИСТКА ЗАКАЗОВ</b>\n\n"
        "Выберите, что хотите очистить:\n\n"
        "• <b>Выполненные</b> — удалить все выполненные заказы\n"
        "• <b>Отменённые</b> — удалить все отменённые заказы\n"
        "• <b>Старые</b> — удалить заказы старше 30 дней\n"
        "• <b>Всё</b> — удалить все заказы (кроме новых)"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Выполненные", callback_data='cleanup_completed'),
            InlineKeyboardButton("❌ Отменённые", callback_data='cleanup_cancelled')
        ],
        [
            InlineKeyboardButton("📅 Старые (>30д)", callback_data='cleanup_old'),
            InlineKeyboardButton("💥 Всё", callback_data='cleanup_all')
        ],
        [InlineKeyboardButton("◀️ Назад к заказам", callback_data='admin_orders')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def process_orders_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка очистки заказов"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    cleanup_type = query.data.replace('cleanup_', '')
    all_orders = db.get_all_orders()
    deleted_count = 0
    
    if cleanup_type == 'completed':
        # Удаляем выполненные
        for order in all_orders:
            if order[13] == 'completed':
                db.complete_order(order[0])  # Освобождаем слот
                db.delete_order(order[0])     # Удаляем заказ
                deleted_count += 1
        message = f"✅ Удалено {deleted_count} выполненных заказов"
    
    elif cleanup_type == 'cancelled':
        # Удаляем отменённые
        for order in all_orders:
            if order[13] == 'cancelled':
                db.delete_order(order[0])
                deleted_count += 1
        message = f"✅ Удалено {deleted_count} отменённых заказов"
    
    elif cleanup_type == 'old':
        # Удаляем старше 30 дней
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        for order in all_orders:
            try:
                order_date = datetime.strptime(order[9], "%d.%m.%Y")
                if order_date < thirty_days_ago and order[13] in ['completed', 'cancelled']:
                    db.delete_order(order[0])
                    deleted_count += 1
            except:
                pass
        message = f"✅ Удалено {deleted_count} старых заказов"
    
    elif cleanup_type == 'all':
        # Удаляем все кроме новых
        for order in all_orders:
            if order[13] in ['confirmed', 'completed', 'cancelled']:
                if order[13] == 'completed' or order[13] == 'confirmed':
                    db.complete_order(order[0])  # Освобождаем слот
                db.delete_order(order[0])
                deleted_count += 1
        message = f"✅ Удалено {deleted_count} заказов (кроме новых)"
    
    else:
        message = "❌ Неизвестный тип очистки"
    
    keyboard = [[InlineKeyboardButton("◀️ К заказам", callback_data='admin_orders')]]
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр всех клиентов с активными ссылками и кнопкой для отправки сообщения"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем права доступа
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    clients = db.get_all_users()
    
    if not clients:
        await query.edit_message_text(
            "📭 Нет клиентов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
            ]])
        )
        return
    
    # Отправляем заголовок
    await query.edit_message_text(
        "👥 <b>Список клиентов:</b>\n\n"
        "👇 Ниже показаны первые 10 клиентов с кнопками для действий.",
        parse_mode='HTML'
    )
    
    # Отправляем каждого клиента отдельным сообщением с кнопкой
    for i, client in enumerate(clients[:10]):  # Показываем первых 10
        user_id, username, first_name, last_name, phone, street, entrance, floor, apt, intercom, reg_date = client
        
        # Формируем имя
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        full_name = " ".join(name_parts) if name_parts else "Не указано"
        
        # Статус блокировки
        block_status = "🔴" if user_id in admin_data['blocked_users'] else "🟢"
        
        # Username с ссылкой если есть
        if username and username != "неизвестно" and username != "нет username":
            clean_username = username.replace('@', '')
            username_text = f"<a href='https://t.me/{clean_username}'>@{username}</a>"
        else:
            username_text = "нет username"
        
        # Формируем текст для одного клиента
        text = (
            f"{block_status} <b>{full_name}</b>\n"
            f"  📱 {username_text}\n"
            f"  📞 {phone or 'нет'}\n"
            f"  🆔 <code>{user_id}</code>\n"
            f"  📅 {reg_date}\n"
        )

        # КНОПКИ ДЛЯ КЛИЕНТА
        keyboard = []

        # Кнопка "Написать сообщение"
        keyboard.append([InlineKeyboardButton("💬 Написать сообщение", callback_data=f'write_to_user_{user_id}')])

        # Кнопка "Заблокировать/Разблокировать"
        if user_id in admin_data['blocked_users']:
            keyboard.append([InlineKeyboardButton("🔓 Разблокировать", callback_data=f'unblock_user_{user_id}')])
        else:
            keyboard.append([InlineKeyboardButton("🔒 Заблокировать", callback_data=f'block_user_{user_id}')])
        
        # 👇 ЭТА КНОПКА ДОЛЖНА БЫТЬ ЗДЕСЬ (ПОСЛЕ if-else, НО ВНУТРИ keyboard) 👇
        keyboard.append([InlineKeyboardButton("🗑️ ПОЛНОСТЬЮ УДАЛИТЬ", callback_data=f'delete_user_{user_id}')])
        
        # Кнопка "Написать по ID" (если нужна)
        keyboard.append([InlineKeyboardButton("✏️ Написать по ID", callback_data=f'write_to_user_{user_id}')])

        # Отправляем сообщение для этого клиента
        if i == 0:
            await query.message.reply_text(
                text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.message.reply_text(
                text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # Добавляем кнопку для возврата в админку
    await query.message.reply_text(
        f"🔍 <b>Всего клиентов:</b> {len(clients)}\n"
        f"Показаны первые 10.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
        ]])
    )
    
async def show_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ID пользователя для связи"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('show_user_id_', ''))
    
    # Получаем информацию о пользователе
    user_info = db.get_user_by_id(user_id)
    
    text = f"🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n"
    
    if user_info:
        if user_info[2]:  # first_name
            text += f"👤 <b>Имя:</b> {user_info[2]}\n"
        if user_info[3]:  # last_name
            text += f"👤 <b>Фамилия:</b> {user_info[3]}\n"
        if user_info[4]:  # phone
            text += f"📞 <b>Телефон:</b> {user_info[4]}\n"
    
    text += f"\nСвязаться с ним можно только по телефону из заказа."
    
    await query.edit_message_text(
        text,
        parse_mode='HTML'
    )

async def admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню сообщений (мини-мессенджер)"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    # Получаем статистику из базы данных
    import database as db
    total_new = db.get_total_unread_messages()
    dialogs_count = db.get_dialogs_count()
    
    text = (
        "💬 <b>ЦЕНТР СООБЩЕНИЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 Новых сообщений: {total_new}\n"
        f"👥 Диалогов: {dialogs_count}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите раздел:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📥 Все диалоги", callback_data='admin_dialogs_all'),
            InlineKeyboardButton("🆕 Новые", callback_data='admin_dialogs_new')
        ],
        [
            InlineKeyboardButton("⭐ Важные", callback_data='admin_dialogs_important'),
            InlineKeyboardButton("📤 Исходящие", callback_data='admin_dialogs_outbox')
        ],
        [
            InlineKeyboardButton("🔍 Поиск", callback_data='admin_messages_search'),
            InlineKeyboardButton("🗑 Корзина", callback_data='admin_messages_trash')
        ],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_messages_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр всех сообщений с деталями"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    messages = db.get_all_messages()
    
    if not messages:
        await query.edit_message_text(
            "📭 Нет сообщений от клиентов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
            ]])
        )
        return
    
    # Отправляем первые 5 сообщений с деталями
    for i, msg in enumerate(messages[:5]):
        msg_id, user_id, username, first_name, phone, user_msg, reply, status, created = msg
        
        status_text = "🆕 Новое" if status == 'new' else "✅ Отвечено"
        
        # Username с ссылкой если есть
        if username and username != "неизвестно" and username != "нет username":
            clean_username = username.replace('@', '')
            username_text = f"<a href='https://t.me/{clean_username}'>@{username}</a>"
        else:
            username_text = "нет username"
        
        text = (
            f"<b>Сообщение #{msg_id}</b>\n"
            f"Статус: {status_text}\n"
            f"От: {first_name} {username_text}\n"
            f"ID: {user_id}\n"
            f"📞 {phone if phone else 'не указан'}\n"
            f"📅 {created}\n\n"
            f"📝 <b>Вопрос:</b>\n{user_msg}\n"
        )
        
        if reply:
            text += f"\n✅ <b>Ответ:</b>\n{reply}"
        
        # Кнопки для ответа
        keyboard = []
        if username and username != "неизвестно" and username != "нет username":
            clean_username = username.replace('@', '')
            keyboard.append([InlineKeyboardButton("💬 Ответить", url=f"https://t.me/{clean_username}")])

        # НОВАЯ КНОПКА: Написать по ID
        keyboard.append([InlineKeyboardButton("✏️ Написать по ID", callback_data=f'write_to_user_{user_id}')])

        # Кнопка "Отметить как прочитано"
        if status == 'new':
            keyboard.append([InlineKeyboardButton("✅ Отметить как прочитано", callback_data=f'mark_read_{msg_id}')])
        
        if i == 0:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
        else:
            await query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    
    await query.message.reply_text(
        f"Показаны первые 5 сообщений из {len(messages)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
        ]])
    )

async def admin_prices_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления ценами"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    text = (
        "💰 <b>УПРАВЛЕНИЕ ЦЕНАМИ</b>\n\n"
        f"Текущие цены:\n"
        f"• 🟢 1 пакет: {admin_data['prices']['1']} ₽ (за один пакет)\n"
        f"• 🟡 2 пакета: {admin_data['prices']['2']} ₽ (за два пакета, общая цена)\n"
        f"• 🔴 3+ пакетов: {admin_data['prices']['3+']} ₽ (фиксированная цена за весь объём)\n\n"
        "Выберите, что хотите изменить:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ 1 пакет", callback_data='edit_price_1')],
        [InlineKeyboardButton("✏️ 2 пакета", callback_data='edit_price_2')],
        [InlineKeyboardButton("✏️ 3+ пакетов", callback_data='edit_price_3')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования цены"""
    query = update.callback_query
    await query.answer()
    
    price_type = query.data.replace('edit_price_', '')
    context.user_data['editing_price'] = price_type
    
    price_names = {'1': '1 пакет', '2': '2 пакета', '3': '3+ пакетов'}
    
    await query.edit_message_text(
        f"✏️ Введите новую цену для <b>{price_names[price_type]}</b> (только число):",
        parse_mode='HTML'
    )
    return 100  # EDITING_PRICE

async def set_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка новой цены"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return ConversationHandler.END
    
    try:
        new_price = int(update.message.text)
        price_type = context.user_data.get('editing_price')
        
        if price_type:
            # Преобразуем ключ '3+' в строку для БД
            if price_type == '3':
                price_key = '3+'
            else:
                price_key = price_type
            
            admin_data['prices'][price_key] = new_price
            
            # Сохраняем в БД
            db.save_prices(admin_data['prices'])
            
            await update.message.reply_text(
                f"✅ Цена успешно изменена!\n\n"
                f"Новые цены:\n"
                f"• 1 пакет: {admin_data['prices']['1']} ₽\n"
                f"• 2 пакета: {admin_data['prices']['2']} ₽\n"
                f"• 3+ пакетов: {admin_data['prices']['3+']} ₽",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ В админку", callback_data='admin')
                ]])
            )
        else:
            await update.message.reply_text("❌ Не удалось определить тип цены")
            
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return 100  # EDITING_PRICE
    
    return ConversationHandler.END

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных (заглушка для будущего функционала)"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "📈 <b>ЭКСПОРТ ДАННЫХ</b>\n\n"
        "Функция находится в разработке.\n\n"
        "В будущем здесь можно будет экспортировать:\n"
        "• Заказы в Excel\n"
        "• Статистику в CSV\n"
        "• Отчёты по дням/неделям/месяцам"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки админки (заглушка для будущего функционала)"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "⚙️ <b>НАСТРОЙКИ</b>\n\n"
        "Функция находится в разработке.\n\n"
        "В будущем здесь можно будет настраивать:\n"
        "• Уведомления\n"
        "• Права администраторов\n"
        "• Параметры заказов"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# Для обратной совместимости
async def admin_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старая функция черного списка (заглушка)"""
    await admin_blacklist_menu(update, context)

async def admin_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика реферальной системы для админа"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    conn = db.get_connection()
    cur = conn.cursor()
    
    try:
        # Общая статистика
        cur.execute('SELECT COUNT(*) FROM users WHERE referral_code IS NOT NULL')
        total_with_codes = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM referrals')
        total_referrals = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM referrals WHERE rewarded = TRUE')
        rewarded = cur.fetchone()[0]
        
        cur.execute('SELECT SUM(amount) FROM referral_earnings')
        total_points = cur.fetchone()[0] or 0
        
        cur.execute('SELECT SUM(amount) FROM referral_spendings')
        spent_points = cur.fetchone()[0] or 0
        
        text = (
            "📊 <b>РЕФЕРАЛЬНАЯ СТАТИСТИКА</b>\n\n"
            f"👥 Пользователей с кодами: {total_with_codes}\n"
            f"🔗 Всего рефералов: {total_referrals}\n"
            f"✅ Активировано заказами: {rewarded}\n"
            f"💰 Всего начислено баллов: {total_points}\n"
            f"💸 Потрачено баллов: {spent_points}\n"
            f"📈 В обороте: {total_points - spent_points}\n\n"
        )
        
        # Топ-5 рефералов
        cur.execute('''
            SELECT u.first_name, u.username, u.total_earned
            FROM users u
            WHERE u.total_earned > 0
            ORDER BY u.total_earned DESC
            LIMIT 5
        ''')
        
        text += "<b>🏆 Топ-5 рефералов:</b>\n"
        top = cur.fetchall()
        if top:
            for i, row in enumerate(top, 1):
                name = row[0] or f"@{row[1]}" if row[1] else "Пользователь"
                text += f"{i}. {name} — {row[2]} баллов\n"
        else:
            text += "Пока нет данных\n"
        
    except Exception as e:
        text = f"❌ Ошибка загрузки статистики: {e}"
        print(f"Ошибка в admin_referral_stats: {e}")
    finally:
        cur.close()
        conn.close()
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== REPLY-ВЕРСИИ ФУНКЦИЙ ===============

async def admin_panel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия admin_panel для обычных сообщений (с клавиатурой)"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    
    orders = db.get_all_orders()
    clients = db.get_all_users()
    messages = db.get_all_messages()
    new_messages = sum(1 for m in messages if len(m) > 7 and m[7] == 'new') if messages else 0
    active_users = len([c for c in clients if c[0] not in admin_data['blocked_users']])
    
    test_status = "🧪 ВКЛ" if admin_data.get('test_mode', False) else "✅ ВЫКЛ"
    
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    today_orders = [o for o in orders if o[9] == today] if orders else []
    
    text = (
        f"👑 <b>СУПЕР-АДМИН ПАНЕЛЬ</b>\n\n"
        f"🧪 <b>Тестовый режим:</b> {test_status}\n\n"
        f"📊 <b>Краткая статистика:</b>\n"
        f"• 📦 Заказов сегодня: {len(today_orders)}\n"
        f"• 👥 Всего клиентов: {len(clients)} (🟢 {active_users} активных)\n"
        f"• 💬 Новых сообщений: {new_messages}\n\n"
        f"💰 <b>Текущие цены:</b>\n"
        f"• 1 пакет: {admin_data['prices']['1']} ₽\n"
        f"• 2 пакета: {admin_data['prices']['2']} ₽\n"
        f"• 3+ пакетов: {admin_data['prices']['3+']} ₽/мешок\n\n"
        f"<b>Выберите раздел:</b>"
    )
    
    # КОМПАКТНАЯ КЛАВИАТУРА (ПО 2 КНОПКИ В РЯДУ)
    keyboard = [
        [
            InlineKeyboardButton("📦 Заказы", callback_data='admin_orders'),
            InlineKeyboardButton("👥 Клиенты", callback_data='admin_clients')
        ],
        [
            InlineKeyboardButton("💬 Сообщения", callback_data='admin_messages'),
            InlineKeyboardButton("📢 Написать", callback_data='admin_write_to_user')
        ],
        [
            InlineKeyboardButton("💰 Цены", callback_data='admin_prices_menu'),
            InlineKeyboardButton("⏰ Время", callback_data='admin_working_hours')
        ],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast'),
            InlineKeyboardButton("🚫 ЧС", callback_data='admin_blacklist')
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
            InlineKeyboardButton("🧪 Тест", callback_data='toggle_test_mode')
        ],
        [
            InlineKeyboardButton("📈 Экспорт", callback_data='admin_export'),
            InlineKeyboardButton("⚙️ Настройки", callback_data='admin_settings')
        ],
        [
            InlineKeyboardButton("🚪 Выйти", callback_data='admin_logout'),
            InlineKeyboardButton("◀️ Меню", callback_data='back_to_menu')
        ]
    ]
    
    await update.message.reply_text(
        text, 
        parse_mode='HTML', 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_orders_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия admin_orders для reply-кнопок"""
    user_id = update.effective_user.id
    
    if user_id not in admin_data['admins']:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    orders = db.get_all_orders()
    
    if not orders:
        await update.message.reply_text("📭 Нет заказов")
        return
    
    for i, order in enumerate(orders[:6]):
        order_id, user_id, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created = order
        
        full_address = street
        details = []
        if entrance:
            details.append(f"под. {entrance}")
        if floor:
            details.append(f"эт. {floor}")
        if apt:
            details.append(f"кв. {apt}")
        if intercom:
            details.append(f"домофон {intercom}")
        if details:
            full_address += f" ({', '.join(details)})"
        
        status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        status_text = {'new': 'Новый', 'confirmed': 'Подтверждён', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
        
        text = (
            f"{status_emoji} <b>Заказ #{order_id}</b>\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📍 {full_address}\n"
            f"📅 {date} {time}\n"
            f"🛍 {bags} пакетов - {price} ₽\n"
            f"Статус: {status_text}\n"
        )
        
        await update.message.reply_text(text, parse_mode='HTML')

# =============== УДАЛЕНИЕ КЛИЕНТОВ ===============

async def admin_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса удаления клиента"""
    query = update.callback_query
    await query.answer()
    
    from config import admin_data
    
    # Проверка прав доступа
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    user_id = int(query.data.replace('delete_user_', ''))
    
    # Получаем статистику пользователя
    import database as db
    stats = db.get_user_stats_for_deletion(user_id)
    
    if not stats:
        await query.edit_message_text(
            "❌ Не удалось получить информацию о пользователе",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='admin_clients')
            ]])
        )
        return
    
    text = (
        f"⚠️ <b>Удаление клиента</b>\n\n"
        f"👤 <b>{stats['name']}</b>\n"
        f"📱 Username: @{stats['username']}\n"
        f"📞 Телефон: {stats['phone']}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"📊 <b>Будет удалено НАВСЕГДА:</b>\n"
        f"• Заказов: {stats['orders']}\n"
        f"• Сообщений: {stats['messages']}\n"
        f"• Избранных адресов: {stats['favorites']}\n"
        f"• Реферальных связей: {stats['referrals_sent'] + stats['referrals_received']}\n\n"
        f"<b>❗️ Это действие необратимо!</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_user_{user_id}'),
            InlineKeyboardButton("❌ Нет", callback_data='admin_clients')
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и выполнение удаления клиента"""
    query = update.callback_query
    await query.answer()
    
    from config import admin_data
    
    # Проверка прав доступа
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    user_id = int(query.data.replace('confirm_delete_user_', ''))
    
    await query.edit_message_text(
        f"⏳ Удаляю пользователя {user_id}...\nЭто может занять несколько секунд."
    )
    
    import database as db
    success = db.delete_user_completely(user_id)
    
    if success:
        text = f"✅ <b>Пользователь {user_id} ПОЛНОСТЬЮ УДАЛЁН из базы данных</b>"
    else:
        text = f"❌ <b>Ошибка при удалении пользователя {user_id}</b>"
    
    keyboard = [[InlineKeyboardButton("◀️ К списку клиентов", callback_data='admin_clients')]]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )