# handlers/admin.py (дополненный)
from config import admin_data
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
import datetime
from constants import BROADCAST_MESSAGE, BLACKLIST_ADD

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
        f"🚨 <b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n\n"
        f"👤 {order[2]}{username_text}\n"
        f"📞 {order[3]}\n"
        f"📍 {full_address}\n"
        f"📅 {order[9]} {order[10]}\n"
        f"🛍 {order[11]} мешков\n"
        f"💰 {order[12]} ₽\n"
    )
    
    # Кнопки для админа
    keyboard = []
    
    # Кнопка связи если есть username
    if username and username != "неизвестно":
        clean_username = username.replace('@', '')
        keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{clean_username}")])
    
    # Кнопки управления заказом
    keyboard.append([
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
            text += f"• {date[:10]}: {msg[:30]}... ({count} пол.)\n"
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
    
    await query.edit_message_text(
        "📝 Введите текст сообщения для рассылки всем клиентам:"
    )
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки"""
    admin_id = update.effective_user.id
    message_text = update.message.text
    
    # Получаем всех пользователей
    users = db.get_all_users()
    
    # Сохраняем рассылку
    broadcast_id = db.save_broadcast(admin_id, message_text)
    
    await update.message.reply_text(
        f"📨 Начинаю рассылку {len(users)} пользователям...\n"
        f"Это может занять некоторое время."
    )
    
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
                InlineKeyboardButton("💬 Ответить", callback_data=f'support_write')
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
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n"
        f"📨 Успешно отправлено: {success}\n"
        f"❌ Не удалось отправить: {failed}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В админку", callback_data='admin')
        ]])
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
        # Обрезаем длинное сообщение
        short_msg = msg[:50] + "..." if len(msg) > 50 else msg
        text += f"<b>#{b_id}</b> от {date[:16]}\n"
        text += f"📝 {short_msg}\n"
        text += f"👥 Получателей: {count}\n"
        text += f"🆔 Админ: {admin_id}\n\n"
    
    if len(broadcasts) > 10:
        text += f"... и ещё {len(broadcasts) - 10} рассылок"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад к рассылкам", callback_data='admin_broadcast')],
        [InlineKeyboardButton("📨 Новая рассылка", callback_data='broadcast_new')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# =============== АДМИН ПАНЕЛЬ ===============

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель с кнопкой тестового режима"""
    query = update.callback_query
    
    if query.from_user.id not in admin_data['admins']:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await query.answer()
    
    orders = db.get_all_orders()
    clients = db.get_all_users()
    messages = db.get_all_messages()
    new_messages = sum(1 for m in messages if len(m) > 7 and m[7] == 'new') if messages else 0
    active_users = len([c for c in clients if c[0] not in admin_data['blocked_users']])
    
    test_status = "🧪 ВКЛ" if admin_data.get('test_mode', False) else "✅ ВЫКЛ"
    
    text = (
        f"👑 <b>СУПЕР-АДМИН ПАНЕЛЬ</b>\n\n"
        f"🧪 <b>Тестовый режим:</b> {test_status}\n\n"
        f"📊 <b>Текущие цены:</b>\n"
        f"• 1 мешок: {admin_data['prices']['1']} ₽\n"
        f"• 2 мешка: {admin_data['prices']['2']} ₽\n"
        f"• 3+ мешков: {admin_data['prices']['3+']} ₽/мешок\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• 📦 Заказов: {len(orders)}\n"
        f"• 👥 Клиентов: {len(clients)} (🟢 {active_users} активных)\n"
        f"• 💬 Сообщений: {len(messages)} (🆕 {new_messages} новых)\n\n"
        f"<b>Выберите раздел:</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📦 Управление заказами", callback_data='admin_orders')],
        [InlineKeyboardButton("👥 Управление клиентами", callback_data='admin_clients')],
        [InlineKeyboardButton("💬 Вопросы от клиентов", callback_data='admin_messages')],
        [InlineKeyboardButton("💰 ИЗМЕНИТЬ ЦЕНЫ", callback_data='admin_prices_menu')],
        [InlineKeyboardButton("📢 МАССОВАЯ РАССЫЛКА", callback_data='admin_broadcast')],
        [InlineKeyboardButton("🚫 Черный список", callback_data='admin_blacklist')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("🧪 Тестовый режим", callback_data='toggle_test_mode')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
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
        db.update_order_status(order_id, 'completed')
        
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
        
        await query.edit_message_text(f"✅ Заказ #{order_id} выполнен")
    
    elif data.startswith('cancel_'):
        order_id = int(data.replace('cancel_', ''))
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
        
        await query.edit_message_text(f"❌ Заказ #{order_id} отменён")
        
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
    """Просмотр всех заказов с кнопкой 'Написать клиенту' для каждого"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        await query.edit_message_text("⛔ Доступ запрещён")
        return
    
    orders = db.get_all_orders()
    
    if not orders:
        await query.edit_message_text(
            "📭 Нет заказов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
            ]])
        )
        return
    
    # Отправляем по 3 заказа
    for i, order in enumerate(orders[:6]):
        order_id, user_id, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created = order
        
        # Формируем адрес
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
        
        # Статус
        status_emoji = {'new': '🆕', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        status_text = {'new': 'Новый', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
        
        text = (
            f"{status_emoji} <b>Заказ #{order_id}</b>\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📍 {full_address}\n"
            f"📅 {date} {time}\n"
            f"🛍 {bags} мешков - {price} ₽\n"
            f"Статус: {status_text}\n"
        )
        
        # Получаем полную информацию о клиенте
        user_info = db.get_user_by_id(user_id)
        username = user_info[1] if user_info and len(user_info) > 1 else None
        
        # Кнопки управления
        keyboard = []
        
        # Кнопка "Написать клиенту" (если есть username)
        if username and username != "неизвестно" and username != "нет username" and username:
            clean_username = username.replace('@', '')
            keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{clean_username}")])
        else:
            # Если нет username, показываем ID
            keyboard.append([InlineKeyboardButton("🆔 Показать ID клиента", callback_data=f'show_user_id_{user_id}')])
        
        # Кнопки управления заказом
        if status == 'new':
            keyboard.append([
                InlineKeyboardButton("✅ Выполнено", callback_data=f'complete_{order_id}'),
                InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
            ])
        
        if i == 0:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    
    await query.message.reply_text(
        f"Показаны первые {min(6, len(orders))} заказов из {len(orders)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')
        ]])
    )

async def admin_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр всех клиентов с активными ссылками"""
    query = update.callback_query
    await query.answer()
    
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
    
    text = "👥 <b>Все клиенты:</b>\n\n"
    
    for client in clients[:10]:
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
        
        text += f"{block_status} <b>{full_name}</b>\n"
        text += f"  📱 {username_text}\n"
        text += f"  📞 {phone or 'нет'}\n"
        text += f"  🆔 <code>{user_id}</code>\n"
        text += f"  📅 {reg_date}\n\n"
    
    text += f"Всего клиентов: {len(clients)}"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

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
    """Просмотр всех сообщений от клиентов"""
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
    
    text = "💬 <b>Сообщения от клиентов:</b>\n\n"
    
    for msg in messages[:10]:
        # msg: (id, user_id, username, first_name, phone, user_msg, reply, status, created)
        msg_id, user_id, username, first_name, phone, user_msg, reply, status, created = msg
        
        status_emoji = "🆕" if status == 'new' else "✅"
        username_text = f"@{username}" if username else first_name
        
        # Обрезаем длинные сообщения
        short_msg = user_msg[:50] + "..." if len(user_msg) > 50 else user_msg
        
        text += f"{status_emoji} <b>#{msg_id}</b> от {username_text}\n"
        text += f"📝 {short_msg}\n"
        text += f"📅 {created}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Подробнее", callback_data='admin_messages_all')],
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
        f"• 🟢 1 мешок: {admin_data['prices']['1']} ₽ (за один мешок)\n"
        f"• 🟡 2 мешка: {admin_data['prices']['2']} ₽ (за два мешка, общая цена)\n"
        f"• 🔴 3+ мешков: {admin_data['prices']['3+']} ₽ (фиксированная цена за весь объём)\n\n"
        "Выберите, что хотите изменить:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ 1 мешок", callback_data='edit_price_1')],
        [InlineKeyboardButton("✏️ 2 мешка", callback_data='edit_price_2')],
        [InlineKeyboardButton("✏️ 3+ мешков", callback_data='edit_price_3')],
        [InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования цены"""
    query = update.callback_query
    await query.answer()
    
    price_type = query.data.replace('edit_price_', '')
    context.user_data['editing_price'] = price_type
    
    price_names = {'1': '1 мешок', '2': '2 мешка', '3': '3+ мешков'}
    
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
            admin_data['prices'][price_type] = new_price
            
            await update.message.reply_text(
                f"✅ Цена успешно изменена!\n\n"
                f"Новые цены:\n"
                f"• 1 мешок: {admin_data['prices']['1']} ₽\n"
                f"• 2 мешка: {admin_data['prices']['2']} ₽\n"
                f"• 3+ мешков: {admin_data['prices']['3+']} ₽/мешок",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ В админку", callback_data='admin')
                ]])
            )
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return 100  # EDITING_PRICE
    
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in admin_data['admins']:
        return
    
    orders = db.get_all_orders()
    
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    today_orders = [o for o in orders if o[9] == today]
    
    new_orders = [o for o in orders if o[13] == 'new']
    completed = [o for o in orders if o[13] == 'completed']
    cancelled = [o for o in orders if o[13] == 'cancelled']
    
    total_revenue = sum(o[12] for o in orders)
    today_revenue = sum(o[12] for o in today_orders)
    
    text = (
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"💰 <b>Выручка:</b>\n"
        f"• За сегодня: {today_revenue} ₽\n"
        f"• Всего: {total_revenue} ₽\n\n"
        f"📅 <b>За сегодня:</b> {len(today_orders)} заказов\n"
        f"🆕 <b>Новых:</b> {len(new_orders)}\n"
        f"✅ <b>Выполнено:</b> {len(completed)}\n"
        f"❌ <b>Отменено:</b> {len(cancelled)}\n"
        f"📦 <b>Всего заказов:</b> {len(orders)}\n"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад в админку", callback_data='admin')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# Для обратной совместимости
async def admin_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старая функция черного списка (заглушка)"""
    await admin_blacklist_menu(update, context)