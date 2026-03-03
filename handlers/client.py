# handlers/client.py
from constants import NAME, PHONE, ADDRESS, ENTRANCE, FLOOR, APARTMENT, INTERCOM, DATE, TIME, BAGS, PAYMENT_METHOD, TIME_SLOTS, SUPPORT_MESSAGE, CHECK_ADDRESS, NEW_ADDRESS, NEW_ENTRANCE, NEW_FLOOR, NEW_APARTMENT, NEW_INTERCOM, FAVORITE_NAME, SELECT_ADDRESS, MANAGE_FAVORITES, EDIT_FAVORITE_NAME, PAYMENT_METHODS
from keyboards.client_keyboards import create_date_keyboard, get_back_button, get_payment_keyboard
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import user_data
from constants import NAME, PHONE, ADDRESS, ENTRANCE, FLOOR, APARTMENT, INTERCOM, DATE, TIME, BAGS, TIME_SLOTS, SUPPORT_MESSAGE, CHECK_ADDRESS, NEW_ADDRESS, NEW_ENTRANCE, NEW_FLOOR, NEW_APARTMENT, NEW_INTERCOM, FAVORITE_NAME, SELECT_ADDRESS, MANAGE_FAVORITES, EDIT_FAVORITE_NAME

# =============== НАСТРОЙКИ ГЕОГРАФИИ ===============
ALLOWED_STREETS = [
    # Основные улицы Южного микрорайона
    "октябрьский проспект", "октябрьский пр", "окт пр", "октябрьский",
    "можайского", "ул можайского", "улица можайского",
    "королева", "ул королева", "улица королева",
    "левитана", "ул левитана", "улица левитана",
    "гусева", "бульвар гусева", "б-р гусева",
    
    # Добавленные улицы
    "псковская", "ул псковская", "улица псковская",
    "лемешева", "ся лемешева", "улица лемешева", "ул лемешева"
]

def is_address_allowed(address):
    """Проверяет, относится ли адрес к разрешённому району"""
    address_lower = address.lower()
    
    # Убираем лишние пробелы и приводим к нормальному виду
    address_lower = " ".join(address_lower.split())
    
    for street in ALLOWED_STREETS:
        if street in address_lower:
            return True
    
    return False
# ==================================================
# =============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===============
def generate_address_name(user_id, street, apartment):
    """Генерирует автоматическое название для адреса"""
    import database as db
    favorites = db.get_user_favorite_addresses(user_id)
    
    # Если есть квартира, используем её
    if apartment and apartment not in ['0', '-', '']:
        return f"Кв. {apartment}"
    
    # Иначе по номеру
    return f"Адрес {len(favorites) + 1}"
# ======================================================
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса заказа - выбор адреса (из избранного или новый)"""
    # Проверяем, есть ли мок-объект в контексте (вызов из reply-кнопки)
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        # Очищаем после использования
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    user_id = query.from_user.id
    user = update.effective_user
    
    print(f"👤 Новый заказ от пользователя {user_id}")
    print(f"  • Username: @{user.username}")
    print(f"  • First name: {user.first_name}")
    print(f"  • Last name: {user.last_name}")
    
    # Инициализируем данные пользователя
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Сохраняем данные пользователя в базу данных
    import database as db
    
    db.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if user.username:
        db.update_user_username(user_id, user.username)
        print(f"✅ Username @{user.username} сохранён для пользователя {user_id}")
    
    user_info = db.get_user_by_id(user_id)
    
    if user_info and user_info[4]:  # если есть телефон
        user_data[user_id]['name'] = user_info[2] or user.first_name
        user_data[user_id]['phone'] = user_info[4]
        user_data[user_id]['has_saved_data'] = True
        
        return await choose_address(update, context)
    else:
        await query.edit_message_text("📝 Шаг 1: Введите ваше имя:")
        return NAME

async def choose_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор адреса при заказе (из избранного или новый)"""
    # Проверяем, откуда пришел вызов - из callback или напрямую
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        message_func = query.edit_message_text
    else:
        # Если вызвана не из callback (например, из start_order)
        user_id = update.effective_user.id
        message_func = update.message.reply_text
    
    import database as db
    
    # Получаем избранные адреса пользователя
    favorites = db.get_user_favorite_addresses(user_id)
    
    text = "📍 <b>Выберите адрес для вывоза:</b>\n\n"
    
    keyboard = []
    
    # Добавляем кнопки с избранными адресами
    if favorites:
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, _ = addr
            
            # Формируем краткое описание адреса
            short_address = street
            if apt:
                short_address += f", кв.{apt}"
            
            button_text = f"{name} - {short_address}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'select_fav_{addr_id}')])
    
    # Кнопка для нового адреса
    keyboard.append([InlineKeyboardButton("➕ Ввести новый адрес", callback_data='new_address_start')])
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')])
    
    await message_func(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_ADDRESS

async def select_favorite_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор избранного адреса с проверкой района"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    address_id = int(query.data.replace('select_fav_', ''))
    
    import database as db
    address = db.get_favorite_address(address_id)
    
    if not address:
        await query.edit_message_text(
            "❌ Адрес не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='choose_address')
            ]])
        )
        return SELECT_ADDRESS
    
    # =============== ПРОВЕРКА РАЙОНА ===============
    if not is_address_allowed(address[3]):  # address[3] - это street_address
        # Формируем список улиц для красивой отправки
        streets_list = (
            "📍 <b>Зона обслуживания - Южный микрорайон:</b>\n\n"
            "• Октябрьский проспект\n"
            "• Улица Можайского\n"
            "• Улица Королева\n"
            "• Улица Левитана\n"
            "• Бульвар Гусева\n"
            "• Улица Псковская\n"
            "• Улица С.Я. Лемешева\n\n"
        )
        
        await query.edit_message_text(
            f"❌ <b>Этот адрес находится за пределами зоны обслуживания</b>\n\n"
            f"{streets_list}"
            f"Пожалуйста, выберите адрес из списка или введите новый в Южном микрорайоне.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к выбору", callback_data='choose_address')
            ]])
        )
        return SELECT_ADDRESS
    # ==============================================
    
    # Сохраняем выбранный адрес в данные пользователя
    if user_id not in user_data:
        user_data[user_id] = {}
    
    addr_id, user_id, name, street, entrance, floor, apt, intercom, created = address
    
    user_data[user_id]['street_address'] = street
    user_data[user_id]['entrance'] = entrance or ''
    user_data[user_id]['floor'] = floor or ''
    user_data[user_id]['apartment'] = apt or ''
    user_data[user_id]['intercom'] = intercom or ''
    user_data[user_id]['address_name'] = name
    
    # Переходим к выбору даты
    keyboard = create_date_keyboard()
    await query.edit_message_text(
        f"✅ Выбран адрес: <b>{name}</b>\n\n📅 Шаг 2: Выберите дату вывоза:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return DATE

async def new_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение нового адреса с проверкой района"""
    user_id = update.effective_user.id
    address = update.message.text
    
    print(f"🏠 new_address: пользователь {user_id} вводит новый адрес: {address}")
    
    # =============== ПРОВЕРКА РАЙОНА ===============
    if not is_address_allowed(address):
        # Формируем список улиц для красивой отправки
        streets_list = (
            "📍 <b>Зона обслуживания - Южный микрорайон:</b>\n\n"
            "• Октябрьский проспект\n"
            "• Улица Можайского\n"
            "• Улица Королева\n"
            "• Улица Левитана\n"
            "• Бульвар Гусева\n"
            "• Улица Псковская\n"
            "• Улица С.Я. Лемешева\n\n"
        )
        
        await update.message.reply_text(
            f"❌ <b>К сожалению, этот адрес не входит в зону обслуживания</b>\n\n"
            f"{streets_list}"
            f"Пожалуйста, введите адрес в Южном микрорайоне:\n"
            f"Например: <i>Октябрьский проспект, д. 50</i>",
            parse_mode='HTML'
        )
        return NEW_ADDRESS  # Остаёмся в том же состоянии, просим ввести снова
    # ==============================================
    if user_id not in user_data:
        user_data[user_id] = {}
        print(f"⚠️ Создана новая запись для пользователя {user_id}")
    
    user_data[user_id]['street_address'] = address
    print(f"✅ Сохранён новый адрес: {user_data[user_id]['street_address']}")
    print(f"🔄 Переходим к состоянию NEW_ENTRANCE ({NEW_ENTRANCE})")
    
    await update.message.reply_text("🚪 Введите номер подъезда (или 0 если нет):")
    return NEW_ENTRANCE

    for fav in favorites:
        if (len(fav) > 6 and
            fav[2] == street_address and
            fav[3] == entrance and
            fav[4] == floor and
            fav[5] == apartment and
            fav[6] == intercom):
            address_exists = True
            break
    
    if not address_exists:
        # Используем умное название
        default_name = generate_address_name(user_id, street_address, apartment)
        
        db.save_favorite_address(
            user_id,
            default_name,
            street_address,
            entrance,
            floor,
            apartment,
            intercom
        )
        print(f"✅ Адрес автоматически добавлен в избранное для пользователя {user_id} с названием '{default_name}'")
    # =================================================================
    
    # Переходим к выбору даты
    keyboard = create_date_keyboard()
    await update.message.reply_text(
        "✅ Адрес сохранён!\n\n📅 Шаг 2: Выберите дату вывоза:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DATE

async def check_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа про смену адреса"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    print(f"📝 check_address_handler: {query.data} для пользователя {user_id}")
    
    if query.data == 'change_address_yes':
        # Меняем адрес
        print(f"🔄 Пользователь {user_id} хочет изменить адрес")
        
        # Очищаем старые данные адреса
        if user_id in user_data:
            # Удаляем только данные адреса, оставляем имя и телефон
            if 'street_address' in user_data[user_id]:
                del user_data[user_id]['street_address']
            if 'entrance' in user_data[user_id]:
                del user_data[user_id]['entrance']
            if 'floor' in user_data[user_id]:
                del user_data[user_id]['floor']
            if 'apartment' in user_data[user_id]:
                del user_data[user_id]['apartment']
            if 'intercom' in user_data[user_id]:
                del user_data[user_id]['intercom']
        
        # Переходим к выбору адреса
        return await choose_address(update, context)
    else:
        # Оставляем старый адрес - переходим к дате
        print(f"✅ Пользователь {user_id} оставляет старый адрес, переходим к дате")
        keyboard = create_date_keyboard()
        await query.edit_message_text(
            "📅 Шаг 1: Выберите дату вывоза:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DATE

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем имя клиента"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['name'] = update.message.text
    await update.message.reply_text("📞 Шаг 2: Введите номер телефона:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем телефон"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['phone'] = update.message.text
    
    # Сразу сохраняем телефон в базу
    import database as db
    db.update_user_phone(user_id, user_data[user_id]['phone'])
    
    # Переходим к выбору адреса
    return await choose_address(update, context)

async def get_intercom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем код домофона и сохраняем все данные"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли данные пользователя
    if user_id not in user_data:
        user_data[user_id] = {}
    
    text = update.message.text
    user_data[user_id]['intercom'] = text if text not in ['0', '-'] else ''
    
    # Сохраняем все данные пользователя в базу
    import database as db
    db.save_user_details(
        user_id,
        user_data[user_id]['phone'],
        user_data[user_id]['street_address'],
        user_data[user_id].get('entrance', ''),
        user_data[user_id].get('floor', ''),
        user_data[user_id].get('apartment', ''),
        user_data[user_id].get('intercom', '')
    )
    
    # Показываем клавиатуру с датами
    keyboard = create_date_keyboard()
    await update.message.reply_text(
        "✅ Данные сохранены!\n\n📅 Шаг 2: Выберите дату:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DATE

async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора даты - показываем только доступные слоты"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    print(f"📅 date_callback для пользователя {user_id}")
    print(f"📅 Данные пользователя: {user_data.get(user_id, {})}")
    
    # Проверяем, есть ли данные пользователя
    if user_id not in user_data:
        print(f"⚠️ Нет данных для пользователя {user_id}, создаем новые")
        user_data[user_id] = {}
    
    selected_date = query.data.replace('date_', '')
    user_data[user_id]['order_date'] = selected_date
    print(f"📅 Выбрана дата: {selected_date}")
    
    # Получаем доступные слоты с учётом истекших и рабочего времени
    import database as db
    available_slots, slot_info = db.get_available_slots(selected_date)
    
    print(f"📅 Доступные слоты после фильтрации: {available_slots}")
    
    # Упрощённая клавиатура — только названия слотов
    time_keyboard = []
    for slot in available_slots:
        # Просто показываем время слота, без информации о количестве мест
        time_keyboard.append([InlineKeyboardButton(slot, callback_data=f'time_{slot}')])
    
    if not available_slots:
        # Нет свободного времени на эту дату
        print(f"❌ Нет доступных слотов на {selected_date}")
        keyboard = create_date_keyboard()
        await query.edit_message_text(
            "❌ На эту дату нет доступного времени.\n"
            "Пожалуйста, выберите другую дату:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DATE
    
    print(f"✅ Отправляем клавиатуру с {len(available_slots)} слотами")
    await query.edit_message_text(
        f"📅 Дата: {selected_date}\n\n"
        f"⏰ Выберите удобное время:",
        reply_markup=InlineKeyboardMarkup(time_keyboard)
    )
    return TIME

async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    selected_time = query.data.replace('time_', '')
    user_data[user_id]['order_time'] = selected_time
    
    print(f"⏰ time_callback: пользователь {user_id} выбрал {user_data[user_id]['order_date']} {selected_time}")
    
    import database as db
    free_places = db.get_slot_availability(
        user_data[user_id]['order_date'], 
        selected_time
    )
    
    print(f"📊 Свободных мест на это время: {free_places}")
    
    if free_places == 0:
        print(f"❌ Время {selected_time} уже полностью занято!")
        keyboard = create_date_keyboard()
        await query.edit_message_text(
            "❌ К сожалению, это время только что заняли.\n"
            "Пожалуйста, выберите другое время:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if user_id in user_data:
            del user_data[user_id]
        return DATE
    
    # Переходим к выбору способа оплаты
    await query.edit_message_text(
        f"💳 Шаг 4: Выберите способ оплаты\n"
        f"📅 {user_data[user_id]['order_date']} {selected_time}",
        reply_markup=get_payment_keyboard()
    )
    return PAYMENT_METHOD

async def payment_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора способа оплаты"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # ВАЖНО: Проверяем, есть ли данные пользователя
    if user_id not in user_data:
        print(f"⚠️ Нет данных для пользователя {user_id} в payment_method_handler, создаем новые")
        user_data[user_id] = {}
    
    payment_method = query.data.replace('pay_', '')
    
    # Если выбрана онлайн-оплата - показываем заглушку
    if payment_method == 'yookassa':
        await query.edit_message_text(
            "💳 <b>Онлайн-оплата временно недоступна</b>\n\n"
            "🔧 Мы работаем над подключением этого способа.\n"
            "Пожалуйста, выберите другой способ оплаты:\n"
            "• 💵 Наличные курьеру\n"
            "• 💳 Перевод на карту курьера\n\n"
            "Приносим извинения за неудобства!",
            parse_mode='HTML',
            reply_markup=get_payment_keyboard()
        )
        return PAYMENT_METHOD
    
    user_data[user_id]['payment_method'] = payment_method
    
    payment_names = {
        'cash': '💵 Наличные курьеру',
        'card': '💳 Перевод на карту курьера',
        'yookassa': '💰 Онлайн-оплата (ЮKassa)'
    }
    
    await query.edit_message_text(
        f"💳 Выбран способ оплаты: {payment_names[payment_method]}\n\n"
        f"🛍 Введите количество пакетов с мусором (от 1 до 4, суммарный вес до 15 кг):"
    )
    return BAGS
async def back_to_bags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Возвращаемся к выбору времени
    await query.edit_message_text(
        f"🛍 Укажите количество пакетов (от 1 до 4, до 15 кг суммарно)\n"
        f"📅 {user_data[user_id]['order_date']} {user_data[user_id]['order_time']}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад к времени", callback_data='back_to_dates')
        ]])
    )
    return BAGS

async def get_bags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем количество пакетов и сохраняем заказ в БД"""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text(
            "❌ Произошла ошибка. Начните заказ заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        return ConversationHandler.END
    
    try:
        bags = int(update.message.text)
        
        # Проверка на минимальное количество
        if bags < 1:
            await update.message.reply_text(
                "❌ Введите число больше 0. Количество пакетов должно быть не менее 1:"
            )
            return BAGS
        
        # Проверка на максимальное количество (не более 4)
        if bags > 4:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Ввести заново", callback_data='back_to_bags')],
                [InlineKeyboardButton("◀️ Отмена заказа", callback_data='back_to_menu')]
            ])
            
            await update.message.reply_text(
                f"❌ <b>Слишком много пакетов!</b>\n\n"
                f"Вы указали: {bags} пакетов\n\n"
                f"🚫 Максимальное количество пакетов для одного заказа: <b>4</b>\n"
                f"📦 Причины:\n"
                f"• Ограничение по весу (до 15 кг суммарно)\n"
                f"• Удобство транспортировки\n"
                f"• Качество обслуживания\n\n"
                f"Пожалуйста, укажите количество пакетов от 1 до 4:",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return BAGS
        
        required_fields = ['name', 'phone', 'street_address', 'order_date', 'order_time']
        for field in required_fields:
            if field not in user_data[user_id]:
                await update.message.reply_text(
                    "❌ Ошибка данных. Начните заказ заново.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
                    ]])
                )
                if user_id in user_data:
                    del user_data[user_id]
                return ConversationHandler.END
        
        from utils.helpers import calculate_price
        price = calculate_price(bags)
        
        user_data[user_id]['bags_count'] = bags
        
        import database as db
        is_free = db.is_time_slot_free(
            user_data[user_id]['order_date'], 
            user_data[user_id]['order_time']
        )
        
        if not is_free:
            keyboard = create_date_keyboard()
            await update.message.reply_text(
                "❌ К сожалению, это время уже занято.\n"
                "Пожалуйста, выберите другую дату:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            if user_id in user_data:
                del user_data[user_id]
            return DATE
        
        # Получаем способ оплаты
        payment_method = user_data[user_id].get('payment_method', 'cash')
        
        # Сохраняем заказ
        result = db.create_order(
            user_id=user_id,
            client_name=user_data[user_id]['name'],
            phone=user_data[user_id]['phone'],
            street_address=user_data[user_id]['street_address'],
            entrance=user_data[user_id].get('entrance', ''),
            floor=user_data[user_id].get('floor', ''),
            apartment=user_data[user_id].get('apartment', ''),
            intercom=user_data[user_id].get('intercom', ''),
            order_date=user_data[user_id]['order_date'],
            order_time=user_data[user_id]['order_time'],
            bags_count=bags,
            price=price,
            payment_method=payment_method
        )
        
        if result[0] is False:
            keyboard = create_date_keyboard()
            await update.message.reply_text(
                f"❌ {result[1]}\n\nПожалуйста, выберите другую дату:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            if user_id in user_data:
                del user_data[user_id]
            return DATE
        
        order_id = result[0]
        
        # Формируем адрес
        full_address = user_data[user_id]['street_address']
        details = []
        if user_data[user_id].get('entrance'):
            details.append(f"под. {user_data[user_id]['entrance']}")
        if user_data[user_id].get('floor'):
            details.append(f"эт. {user_data[user_id]['floor']}")
        if user_data[user_id].get('apartment'):
            details.append(f"кв. {user_data[user_id]['apartment']}")
        if user_data[user_id].get('intercom'):
            details.append(f"домофон {user_data[user_id]['intercom']}")
        if details:
            full_address += f" ({', '.join(details)})"
        
        # Текст о цене
        if bags == 1:
            price_text = f"💰 {price} ₽ (за 1 пакет)"
        elif bags == 2:
            price_text = f"💰 {price} ₽ (за 2 пакета)"
        else:
            price_text = f"💰 {price} ₽ (фиксированная цена за {bags} пакетов)"
        
        # Текст об оплате
        payment_names = {
            'cash': '💵 Наличные курьеру',
            'card': '💳 Перевод на карту курьера',
            'yookassa': '💰 Онлайн-оплата'
        }
        payment_text = f"💳 Оплата: {payment_names.get(payment_method, 'Неизвестно')}"
        
        # Если выбрана онлайн-оплата, даем ссылку
        if payment_method == 'yookassa':
            payment_text += f"\n🔗 Ссылка для оплаты будет отправлена отдельно"
        
        from keyboards.client_keyboards import get_main_keyboard
        from config import admin_data
        
        await update.message.reply_text(
            f"✅ <b>Заказ #{order_id} принят!</b>\n\n"
            f"👤 {user_data[user_id]['name']}\n"
            f"📞 {user_data[user_id]['phone']}\n"
            f"📍 {full_address}\n"
            f"📅 {user_data[user_id]['order_date']} {user_data[user_id]['order_time']}\n"
            f"🛍 {bags} пакетов\n"
            f"{price_text}\n"
            f"{payment_text}\n\n"
            f"🚶‍♂️ <b>Что дальше?</b>\n"
            f"Курьер приедет в указанное время, поднимется к вам и заберёт пакеты.\n"
            f"Вам останется только открыть дверь!\n"
            f"Подтверждение заказа придёт отдельно.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user_id in admin_data['admins'])
        )
        
        # Уведомление админу
        from handlers.admin import notify_admin
        
        for admin_id in admin_data['admins']:
            try:
                await notify_admin(update, context, admin_id, order_id)
            except Exception as e:
                print(f"❌ Ошибка уведомления админа {admin_id}: {e}")
        
        if user_id in user_data:
            del user_data[user_id]
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Введите число! Количество пакетов должно быть от 1 до 4:"
        )
        return BAGS
    except Exception as e:
        print(f"❌ Ошибка при создании заказа: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Начните заказ заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        if user_id in user_data:
            del user_data[user_id]
        return ConversationHandler.END

async def favorite_addresses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню избранных адресов"""
    # Проверяем, есть ли мок-объект в контексте (вызов из reply-кнопки)
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    
    favorites = db.get_user_favorite_addresses(user_id)
    
    text = "⭐ <b>Мои избранные адреса</b>\n\n"
    
    if favorites:
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, created = addr
            
            full = street
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
                full += f" ({', '.join(details)})"
            
            text += f"🏷 <b>{name}</b>\n"
            text += f"📍 {full}\n\n"
    else:
        text += "У вас пока нет избранных адресов"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить текущий адрес", callback_data='favorite_add')],
        [InlineKeyboardButton("✏️ Управление адресами", callback_data='manage_favorites')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def favorite_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление адреса в избранное из базы данных"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    import database as db
    
    # Получаем данные пользователя из базы данных
    user_info = db.get_user_by_id(user_id)
    
    # Проверяем, есть ли у пользователя сохранённый адрес в базе
    if not user_info or not user_info[5]:
        await query.edit_message_text(
            "❌ У вас ещё нет сохранённого адреса.\n"
            "Сначала оформите заказ, чтобы адрес сохранился в базе.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        return
    
    # Проверяем, не добавлен ли уже этот адрес в избранное
    favorites = db.get_user_favorite_addresses(user_id)
    for fav in favorites:
        if (fav[2] == user_info[5] and
            fav[3] == user_info[6] and
            fav[4] == user_info[7] and
            fav[5] == user_info[8] and
            fav[6] == user_info[9]):
            await query.edit_message_text(
                "❌ Этот адрес уже есть в избранном!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu')
                ]])
            )
            return
    
    # Спрашиваем название для адреса
    await query.edit_message_text(
        "Введите название для этого адреса (например: 'Дом', 'Работа', 'Дача'):"
    )
    return FAVORITE_NAME

async def favorite_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение адреса из базы данных в избранное"""
    user_id = update.effective_user.id
    address_name = update.message.text
    
    import database as db
    
    # Получаем данные пользователя из базы
    user_info = db.get_user_by_id(user_id)
    
    if not user_info or not user_info[5]:
        await update.message.reply_text(
            "❌ Ошибка: адрес не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')
            ]])
        )
        return ConversationHandler.END
    
    # Сохраняем адрес в избранное
    db.save_favorite_address(
        user_id,
        address_name,
        user_info[5],
        user_info[6] or '',
        user_info[7] or '',
        user_info[8] or '',
        user_info[9] or ''
    )
    
    # Формируем красивый адрес для подтверждения
    full_address = user_info[5]
    details = []
    if user_info[6]:
        details.append(f"под. {user_info[6]}")
    if user_info[7]:
        details.append(f"эт. {user_info[7]}")
    if user_info[8]:
        details.append(f"кв. {user_info[8]}")
    if user_info[9]:
        details.append(f"домофон {user_info[9]}")
    if details:
        full_address += f" ({', '.join(details)})"
    
    await update.message.reply_text(
        f"✅ Адрес '{address_name}' сохранён в избранное!\n\n"
        f"📍 {full_address}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu')
        ]])
    )
    
    return ConversationHandler.END

async def favorite_add_after_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление адреса в избранное после завершения заказа"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    
    # Получаем данные пользователя из базы данных
    user_info = db.get_user_by_id(user_id)
    
    # Проверяем, есть ли у пользователя сохранённый адрес в базе
    if not user_info or not user_info[5]:
        await query.edit_message_text(
            "❌ Не удалось найти адрес для сохранения.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')
            ]])
        )
        return
    
    # Проверяем, не добавлен ли уже этот адрес в избранное
    favorites = db.get_user_favorite_addresses(user_id)
    for fav in favorites:
        if (fav[2] == user_info[5] and
            fav[3] == user_info[6] and
            fav[4] == user_info[7] and
            fav[5] == user_info[8] and
            fav[6] == user_info[9]):
            await query.edit_message_text(
                "❌ Этот адрес уже есть в избранном!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu'),
                    InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')
                ]])
            )
            return
    
    # Создаем название по умолчанию
    default_name = f"Адрес {len(favorites) + 1}"
    
    # Сохраняем адрес в избранное
    db.save_favorite_address(
        user_id,
        default_name,
        user_info[5],
        user_info[6] or '',
        user_info[7] or '',
        user_info[8] or '',
        user_info[9] or ''
    )
    
    # Формируем красивый адрес для подтверждения
    full_address = user_info[5]
    details = []
    if user_info[6]:
        details.append(f"под. {user_info[6]}")
    if user_info[7]:
        details.append(f"эт. {user_info[7]}")
    if user_info[8]:
        details.append(f"кв. {user_info[8]}")
    if user_info[9]:
        details.append(f"домофон {user_info[9]}")
    if details:
        full_address += f" ({', '.join(details)})"
    
    await query.edit_message_text(
        f"✅ Адрес добавлен в избранное!\n\n"
        f"📍 {full_address}\n\n"
        f"Вы можете изменить название в разделе 'Мои адреса'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu'),
            InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')
        ]])
    )

async def favorite_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню удаления избранных адресов"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    
    favorites = db.get_user_favorite_addresses(user_id)
    
    if not favorites:
        await query.edit_message_text(
            "📭 У вас нет избранных адресов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='favorite_menu')
            ]])
        )
        return
    
    keyboard = []
    for addr in favorites[:5]:
        addr_id, name, street, entrance, floor, apt, intercom, _ = addr
        # Формируем краткое описание
        short_addr = street
        if apt:
            short_addr += f" кв.{apt}"
        button_text = f"❌ {name} - {short_addr}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'favorite_del_{addr_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='favorite_menu')])
    
    await query.edit_message_text(
        "Выберите адрес для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def favorite_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление избранного адреса"""
    query = update.callback_query
    await query.answer()
    
    address_id = int(query.data.replace('favorite_del_', ''))
    
    import database as db
    db.delete_favorite_address(address_id)
    
    # Показываем обновленный список
    user_id = query.from_user.id
    favorites = db.get_user_favorite_addresses(user_id)
    
    if favorites:
        text = "✅ Адрес удален!\n\n⭐ <b>Остались следующие адреса:</b>\n\n"
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, _ = addr
            full = street
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
                full += f" ({', '.join(details)})"
            text += f"🏷 <b>{name}</b>\n📍 {full}\n\n"
    else:
        text = "✅ Адрес удален!\n\nУ вас больше нет избранных адресов."
    
    keyboard = [
        [InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu')],
        [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def manage_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление избранными адресами"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    
    favorites = db.get_user_favorite_addresses(user_id)
    
    text = "✏️ <b>Управление избранными адресами</b>\n\n"
    
    if not favorites:
        text += "У вас пока нет избранных адресов."
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='favorite_menu')]]
    else:
        keyboard = []
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, _ = addr
            button_text = f"✏️ {name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'edit_fav_{addr_id}')])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='favorite_menu')])
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_favorite_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню редактирования конкретного адреса"""
    query = update.callback_query
    await query.answer()
    
    address_id = int(query.data.replace('edit_fav_', ''))
    context.user_data['editing_address'] = address_id
    
    import database as db
    address = db.get_favorite_address(address_id)
    
    if not address:
        await query.edit_message_text("❌ Адрес не найден")
        return
    
    addr_id, user_id, name, street, entrance, floor, apt, intercom, created = address
    
    # Формируем полный адрес
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
    
    text = (
        f"<b>{name}</b>\n"
        f"📍 {full_address}\n\n"
        f"Что хотите сделать?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить название", callback_data=f'edit_name_{address_id}')],
        [InlineKeyboardButton("🗑 Удалить адрес", callback_data=f'delete_fav_{address_id}')],
        [InlineKeyboardButton("◀️ Назад", callback_data='manage_favorites')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_favorite_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение названия избранного адреса"""
    query = update.callback_query
    await query.answer()
    
    address_id = int(query.data.replace('edit_name_', ''))
    context.user_data['editing_address_name'] = address_id
    
    await query.edit_message_text(
        "Введите новое название для этого адреса:"
    )
    return EDIT_FAVORITE_NAME

async def save_favorite_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового названия"""
    user_id = update.effective_user.id
    new_name = update.message.text
    address_id = context.user_data.get('editing_address_name')
    
    if not address_id:
        await update.message.reply_text("❌ Ошибка: адрес не найден")
        return ConversationHandler.END
    
    import database as db
    address = db.get_favorite_address(address_id)
    
    if address:
        db.delete_favorite_address(address_id)
        db.save_favorite_address(
            user_id,
            new_name,
            address[3],
            address[4] or '',
            address[5] or '',
            address[6] or '',
            address[7] or ''
        )
    
    await update.message.reply_text(
        f"✅ Название изменено на '{new_name}'",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu')
        ]])
    )
    
    return ConversationHandler.END

async def delete_favorite_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления адреса"""
    query = update.callback_query
    await query.answer()
    
    address_id = int(query.data.replace('delete_fav_', ''))
    
    await query.edit_message_text(
        "❓ Вы уверены, что хотите удалить этот адрес?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{address_id}')],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data='manage_favorites')]
        ])
    )

async def confirm_delete_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвержденное удаление адреса"""
    query = update.callback_query
    await query.answer()
    
    address_id = int(query.data.replace('confirm_delete_', ''))
    
    import database as db
    db.delete_favorite_address(address_id)
    
    await query.edit_message_text(
        "✅ Адрес удален из избранного",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Мои адреса", callback_data='favorite_menu')
        ]])
    )

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало обращения в поддержку"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💬 Напишите ваш вопрос, и мы ответим в ближайшее время:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')
        ]])
    )
    return SUPPORT_MESSAGE

async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение сообщения от клиента"""
    user_id = update.effective_user.id
    user = update.effective_user
    message_text = update.message.text
    
    import database as db
    message_id = db.save_message(user_id, message_text)
    
    from keyboards.client_keyboards import get_main_keyboard
    is_admin = user_id in context.bot_data.get('admins', [])
    await update.message.reply_text(
        "✅ <b>Сообщение доставлено!</b>\n\n"
        "Спасибо за обращение. Мы ответим вам в ближайшее время.\n"
        "Обычно мы отвечаем в течение нескольких часов.",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(is_admin)
    )
    
    from config import admin_data
    from handlers.admin import notify_admin_about_message
    
    username = f"@{user.username}" if user.username else "нет username"
    first_name = user.first_name or ""
    
    for admin_id in admin_data['admins']:
        try:
            await notify_admin_about_message(
                update, context, admin_id, user_id, username, first_name, message_text, message_id
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления админа {admin_id}: {e}")
    
    return ConversationHandler.END

async def order_detail_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор заказа для детального просмотра"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    orders = db.get_user_orders(user_id)
    
    if not orders:
        await query.edit_message_text(
            "📭 У вас нет заказов",
            reply_markup=get_back_button()
        )
        return
    
    keyboard = []
    for order in orders[:5]:
        order_id, _, _, _, _, date, time, bags, price, status, _ = order
        status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        button_text = f"{status_emoji} #{order_id} от {date} {time} ({bags} меш.)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'order_detail_{order_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='my_orders_detail')])
    
    await query.edit_message_text(
        "Выберите заказ для просмотра:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def my_orders_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальный просмотр истории заказов"""
    # Проверяем, есть ли мок-объект в контексте (вызов из reply-кнопки)
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    user_id = query.from_user.id
    import database as db
    orders = db.get_user_orders(user_id)
    
    if not orders:
        await query.edit_message_text(
            "📭 У вас пока нет заказов.",
            reply_markup=get_back_button()
        )
        return
    
    text = "📋 <b>Ваши последние заказы:</b>\n\n"
    
    for i, order in enumerate(orders[:3]):
        order_id, _, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created = order
        
        status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        status_text = {'new': 'Активен', 'confirmed': 'Подтверждён', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
        
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
        
        text += f"{status_emoji} <b>Заказ #{order_id}</b>\n"
        text += f"📅 {date} {time}\n"
        text += f"📍 {full_address}\n"
        text += f"🛍 {bags} мешков - {price} ₽\n"
        text += f"📊 Статус: {status_text}\n\n"
    
    if len(orders) > 3:
        text += f"... и ещё {len(orders) - 3} заказов"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Подробнее о заказе", callback_data='order_detail_select')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
    ]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальный просмотр конкретного заказа"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.replace('order_detail_', ''))
    
    import database as db
    order = db.get_order_by_id(order_id)
    
    if not order:
        await query.edit_message_text(
            "❌ Заказ не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='order_detail_select')
            ]])
        )
        return
    
    # order: (id, user_id, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created)
    order_id, user_id, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created = order
    
    status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
    status_text = {'new': 'Активен', 'confirmed': 'Подтверждён', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
    
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
    
    text = (
        f"{status_emoji} <b>Заказ #{order_id}</b>\n\n"
        f"👤 {name}\n"
        f"📞 {phone}\n"
        f"📍 {full_address}\n"
        f"📅 {date} {time}\n"
        f"🛍 {bags} мешков - {price} ₽\n"
        f"📊 Статус: {status_text}\n\n"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад к списку", callback_data='order_detail_select')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
# =============== REPLY-ВЕРСИИ ФУНКЦИЙ ===============


async def start_order_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия start_order для reply-кнопок"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    print(f"👤 Новый заказ от пользователя {user_id} (reply)")
    
    # Инициализируем данные пользователя
    if user_id not in user_data:
        user_data[user_id] = {}
    
    import database as db
    db.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if user.username:
        db.update_user_username(user_id, user.username)
    
    user_info = db.get_user_by_id(user_id)
    
    if user_info and user_info[4]:  # если есть телефон
        user_data[user_id]['name'] = user_info[2] or user.first_name
        user_data[user_id]['phone'] = user_info[4]
        user_data[user_id]['has_saved_data'] = True
        # Вызываем выбор адреса
        return await choose_address_reply(update, context)
    else:
        await update.message.reply_text("📝 Шаг 1: Введите ваше имя:")
        return NAME

# =============== ДОБАВЬ ЭТУ ФУНКЦИЮ ===============
async def choose_address_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия choose_address для reply-кнопок"""
    user_id = update.effective_user.id
    
    import database as db
    favorites = db.get_user_favorite_addresses(user_id)
    
    text = "📍 <b>Выберите адрес для вывоза:</b>\n\n"
    
    keyboard = []
    if favorites:
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, _ = addr
            short_address = street
            if apt:
                short_address += f", кв.{apt}"
            button_text = f"{name} - {short_address}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'select_fav_{addr_id}')])
    
    keyboard.append([InlineKeyboardButton("➕ Ввести новый адрес", callback_data='new_address_start')])
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')])
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_ADDRESS
# =================================================

async def my_orders_detail_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия my_orders_detail для reply-кнопок"""
    # ... остальной код
    user_id = update.effective_user.id
    import database as db
    orders = db.get_user_orders(user_id)
    
    if not orders:
        await update.message.reply_text("📭 У вас пока нет заказов.")
        return
    
    text = "📋 <b>Ваши последние заказы:</b>\n\n"
    
    for i, order in enumerate(orders[:3]):
        order_id, _, name, phone, street, entrance, floor, apt, intercom, date, time, bags, price, status, created = order
        
        status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        status_text = {'new': 'Активен', 'confirmed': 'Подтверждён', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
        
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
        
        text += f"{status_emoji} <b>Заказ #{order_id}</b>\n"
        text += f"📅 {date} {time}\n"
        text += f"📍 {full_address}\n"
        text += f"🛍 {bags} мешков - {price} ₽\n"
        text += f"📊 Статус: {status_text}\n\n"
    
    if len(orders) > 3:
        text += f"... и ещё {len(orders) - 3} заказов"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Подробнее о заказе", callback_data='order_detail_select')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
    ]
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def favorite_addresses_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия favorite_addresses_menu для reply-кнопок"""
    user_id = update.effective_user.id
    import database as db
    
    favorites = db.get_user_favorite_addresses(user_id)
    
    text = "⭐ <b>Мои избранные адреса</b>\n\n"
    
    if favorites:
        for addr in favorites[:5]:
            addr_id, name, street, entrance, floor, apt, intercom, created = addr
            
            full = street
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
                full += f" ({', '.join(details)})"
            
            text += f"🏷 <b>{name}</b>\n📍 {full}\n\n"
    else:
        text += "У вас пока нет избранных адресов"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить текущий адрес", callback_data='favorite_add')],
        [InlineKeyboardButton("✏️ Управление адресами", callback_data='manage_favorites')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
    ]
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
