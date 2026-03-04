from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
import datetime
from keyboards.courier_keyboards import get_courier_main_keyboard, get_courier_back_button
import logging

logger = logging.getLogger(__name__)

# Константы
ORDERS_PER_PAGE = 5

async def courier_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню курьера"""
    user = update.effective_user
    
    # Получаем статистику за сегодня
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    stats = db.get_courier_daily_stats(user.id, today)
    
    text = (
        f"🚚 <b>Кабинет курьера</b>\n\n"
        f"👤 {user.first_name}\n"
        f"📅 {today}\n"
        f"📊 Сегодня: {stats['completed']} заказов, {stats['bags']} мешков, {stats['earned']} ₽\n\n"
        f"Выберите действие:"
    )
    
    # Если это reply на сообщение
    if update.message:
        await update.message.reply_text(
            text, 
            parse_mode='HTML', 
            reply_markup=get_courier_main_keyboard()
        )
    # Если это callback
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=get_courier_main_keyboard()
        )

async def courier_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список активных заказов с сортировкой по срочности"""
    # Определяем источник вызова
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        user_id = query.from_user.id
    else:
        message = update.message
        user_id = update.effective_user.id
    
    # Получаем заказы
    orders = db.get_courier_active_orders()
    
    if not orders:
        text = "📭 На сегодня и завтра нет активных заказов"
        if update.callback_query:
            await query.edit_message_text(text, reply_markup=get_courier_back_button())
        else:
            await message.reply_text(text, reply_markup=get_courier_back_button())
        return
    
    # Группируем по дням и сортируем по срочности
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
    
    today_orders = []
    tomorrow_orders = []
    
    for order in orders:
        if order[9] == today:
            today_orders.append(order)
        elif order[9] == tomorrow:
            tomorrow_orders.append(order)
    
    # Сортируем внутри дня по времени
    today_orders.sort(key=lambda x: x[10])  # order_time
    tomorrow_orders.sort(key=lambda x: x[10])
    
    # Отправляем заголовок
    header_text = "📦 <b>Активные заказы</b>\n\n"
    if update.callback_query:
        await query.edit_message_text(header_text, parse_mode='HTML')
    else:
        await message.reply_text(header_text, parse_mode='HTML')
    
    # Отправляем заказы по дням
    if today_orders:
        await message.reply_text("🔹 <b>СЕГОДНЯ</b>", parse_mode='HTML')
        for order in today_orders:
            await send_order_card(message, order, context)
    
    if tomorrow_orders:
        await message.reply_text("🔹 <b>ЗАВТРА</b>", parse_mode='HTML')
        for order in tomorrow_orders:
            await send_order_card(message, order, context)
    
    # Отправляем кнопку возврата
    await message.reply_text("Выберите действие:", reply_markup=get_courier_back_button())

async def send_order_card(message, order, context):
    """Отправляет карточку заказа"""
    order_id, user_id, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, courier_id = order
    
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
    
    # Рассчитываем срочность
    now = datetime.datetime.now()
    try:
        order_datetime = datetime.datetime.strptime(f"{date} {time.split('-')[0]}", "%d.%m.%Y %H:%M")
        hours_until = (order_datetime - now).total_seconds() / 3600
        
        if hours_until < 2:
            urgency = "🔴 Срочно"
        elif hours_until < 4:
            urgency = "🟡 Скоро"
        else:
            urgency = "🟢 Есть время"
        
        # Таймер до выезда
        if hours_until > 0:
            hours = int(hours_until)
            minutes = int((hours_until - hours) * 60)
            timer = f"🕒 Осталось: {hours}ч {minutes}мин"
        else:
            timer = "⚠️ Уже началось!"
    except:
        urgency = "⚪ Время неизвестно"
        timer = ""
    
    # Текст заказа
    text = (
        f"🆔 <b>Заказ #{order_id}</b> {urgency}\n"
        f"📅 {date} {time}\n"
        f"📍 {full_address}\n"
        f"🛍 {bags} мешков — {price} ₽\n"
        f"📞 {phone}\n"
        f"{timer}\n"
    )
    
    # Кнопки
    keyboard = []
    
    # Карта
    street_encoded = street.replace(' ', '+')
    maps_url = f"https://yandex.ru/maps/?text={street_encoded}"
    keyboard.append([InlineKeyboardButton("🗺 Открыть карту", url=maps_url)])
    
    # Контакты
    contact_row = []
    if phone:
        contact_row.append(InlineKeyboardButton("📞 Позвонить", callback_data=f'show_phone_{user_id}'))
    
    # Получаем username из базы
    import database as db
    username = db.get_username_by_id(user_id)
    if username and username != "неизвестно":
        clean_username = username.replace('@', '')
        contact_row.append(InlineKeyboardButton("💬 Написать", url=f"https://t.me/{clean_username}"))
    
    if contact_row:
        keyboard.append(contact_row)
    
    # Действия с заказом
    if status == 'new':
        keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f'courier_take_{order_id}')])
    elif status == 'confirmed' and courier_id == message.chat.id:
        keyboard.append([InlineKeyboardButton("✅ Выполнено", callback_data=f'courier_done_{order_id}')])
    elif status == 'confirmed' and courier_id != message.chat.id:
        text += "\n⚠️ Заказ уже взят другим курьером"
    
    await message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def courier_take_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Курьер берёт заказ в работу"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.replace('courier_take_', ''))
    courier_id = query.from_user.id
    
    # Проверяем, не взят ли уже заказ
    import database as db
    order = db.get_order_by_id(order_id)
    
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    
    if order[13] != 'new':  # status
        await query.edit_message_text("❌ Этот заказ уже нельзя взять")
        return
    
    # Берём заказ
    db.assign_courier_to_order(order_id, courier_id)
    
    # Показываем подтверждение с деталями
    text = (
        f"✅ <b>Вы взяли заказ #{order_id}</b>\n\n"
        f"📍 {order[4]}\n"  # street
        f"📅 {order[9]} {order[10]}\n"  # date, time
        f"🛍 {order[11]} мешков — {order[12]} ₽\n"
        f"📞 {order[3]}\n\n"
        f"Когда выполните, нажмите кнопку 'Выполнено' в карточке заказа."
    )
    
    keyboard = [[InlineKeyboardButton("📦 К заказам", callback_data='courier_active_orders')]]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def courier_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Курьер отмечает заказ выполненным"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.replace('courier_done_', ''))
    courier_id = query.from_user.id
    
    import database as db
    
    # Проверяем, что это его заказ
    order = db.get_order_by_id(order_id)
    if not order or order[14] != courier_id:  # courier_id
        await query.edit_message_text("❌ Это не ваш заказ")
        return
    
    # Отмечаем выполненным
    db.complete_order(order_id)
    
    # Получаем обновлённую статистику
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    stats = db.get_courier_daily_stats(courier_id, today)
    
    text = (
        f"✅ <b>Заказ #{order_id} выполнен!</b>\n\n"
        f"📊 Статистика за сегодня:\n"
        f"• Заказов: {stats['completed']}\n"
        f"• Мешков: {stats['bags']}\n"
        f"• Заработано: {stats['earned']} ₽"
    )
    
    keyboard = [
        [InlineKeyboardButton("📦 К заказам", callback_data='courier_active_orders')],
        [InlineKeyboardButton("📊 Моя статистика", callback_data='courier_stats')]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def courier_completed_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История выполненных заказов курьера"""
    courier_id = update.effective_user.id
    
    import database as db
    orders = db.get_courier_completed_orders(courier_id)
    
    if not orders:
        text = "📭 У вас пока нет выполненных заказов"
    else:
        text = "✅ <b>Ваши выполненные заказы:</b>\n\n"
        for order in orders[:10]:
            order_id, date, time, bags, price = order
            text += f"#{order_id} — {date} {time}, {bags} мешков — {price} ₽\n"
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_courier_back_button())
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_courier_back_button())

async def courier_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расширенная статистика курьера"""
    courier_id = update.effective_user.id
    
    import database as db
    
    # Статистика за разные периоды
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%d.%m.%Y")
    month_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%d.%m.%Y")
    
    stats_today = db.get_courier_stats_period(courier_id, today, today)
    stats_week = db.get_courier_stats_period(courier_id, week_ago, today)
    stats_month = db.get_courier_stats_period(courier_id, month_ago, today)
    stats_all = db.get_courier_stats(courier_id)
    
    # Аналитика по часам
    hourly = db.get_courier_hourly_stats(courier_id)
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"<b>Сегодня:</b>\n"
        f"• Заказов: {stats_today['total']}\n"
        f"• Мешков: {stats_today['bags']}\n"
        f"• Заработано: {stats_today['earned']} ₽\n"
        f"• Средний чек: {stats_today['avg']} ₽\n\n"
        
        f"<b>За неделю:</b>\n"
        f"• Заказов: {stats_week['total']}\n"
        f"• Мешков: {stats_week['bags']}\n"
        f"• Заработано: {stats_week['earned']} ₽\n\n"
        
        f"<b>За месяц:</b>\n"
        f"• Заказов: {stats_month['total']}\n"
        f"• Мешков: {stats_month['bags']}\n"
        f"• Заработано: {stats_month['earned']} ₽\n\n"
        
        f"<b>Всего:</b>\n"
        f"• Заказов: {stats_all['total']}\n"
        f"• Мешков: {stats_all['bags']}\n"
        f"• Заработано: {stats_all['earned']} ₽\n"
    )
    
    if hourly:
        text += "\n<b>⏰ Активные часы:</b>\n"
        # Показываем топ-3 часа
        top_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:3]
        for hour, count in top_hours:
            text += f"• {hour}:00 — {count} заказов\n"
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_courier_back_button())
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_courier_back_button())

async def courier_show_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает телефон клиента"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace('show_phone_', ''))
    
    import database as db
    user_info = db.get_user_by_id(user_id)
    
    if user_info and user_info[4]:
        phone = user_info[4]
    else:
        phone = "не указан"
    
    await query.answer(f"📞 Телефон: {phone}", show_alert=True)

async def courier_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню курьера"""
    query = update.callback_query
    await query.answer()
    await courier_main_menu(update, context)