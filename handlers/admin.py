# handlers/admin.py
from config import admin_data, WORK_HOURS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
import datetime
from constants import BROADCAST_MESSAGE, BLACKLIST_ADD, EDIT_WORKING_HOURS_START, EDIT_WORKING_HOURS_END

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
    """Админ-панель с улучшенным меню"""
    # Проверяем, есть ли мок-объект в контексте (вызов из reply-кнопки)
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
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
    
    keyboard = [
        [InlineKeyboardButton("📦 Управление заказами", callback_data='admin_orders')],
        [InlineKeyboardButton("👥 Управление клиентами", callback_data='admin_clients')],
        [InlineKeyboardButton("💬 Вопросы от клиентов", callback_data='admin_messages')],
        [InlineKeyboardButton("💰 ИЗМЕНИТЬ ЦЕНЫ", callback_data='admin_prices_menu')],
        [InlineKeyboardButton("⏰ ВРЕМЯ РАБОТЫ", callback_data='admin_working_hours')],
        [InlineKeyboardButton("📢 МАССОВАЯ РАССЫЛКА", callback_data='admin_broadcast')],
        [InlineKeyboardButton("🚫 Черный список", callback_data='admin_blacklist')],
        [InlineKeyboardButton("📊 РАСШИРЕННАЯ СТАТИСТИКА", callback_data='admin_stats')],
        [InlineKeyboardButton("🧪 Тестовый режим", callback_data='toggle_test_mode')],
        [InlineKeyboardButton("📈 Экспорт данных", callback_data='admin_export')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='admin_settings')],
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
        
        # Статус с новым статусом confirmed
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
        
        # Кнопки управления заказом в зависимости от статуса
        if status == 'new':
            keyboard.append([
                InlineKeyboardButton("✅ Подтверждаю", callback_data=f'confirm_{order_id}'),
                InlineKeyboardButton("✅ Выполнено", callback_data=f'complete_{order_id}'),
                InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
            ])
        elif status == 'confirmed':
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
            admin_data['prices'][price_type] = new_price
            
            await update.message.reply_text(
                f"✅ Цена успешно изменена!\n\n"
                f"Новые цены:\n"
                f"• 1 пакет: {admin_data['prices']['1']} ₽\n"
                f"• 2 пакета: {admin_data['prices']['2']} ₽\n"
                f"• 3+ пакетов: {admin_data['prices']['3+']} ₽/мешок",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ В админку", callback_data='admin')
                ]])
            )
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

# =============== REPLY-ВЕРСИИ ФУНКЦИЙ ===============

async def admin_panel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия admin_panel для reply-кнопок"""
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
        f"<b>Выберите раздел в меню ниже:</b>"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')

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
