# handlers/client.py
from constants import (
    USE_BONUS, NAME, PHONE, ADDRESS, ENTRANCE, FLOOR, APARTMENT, INTERCOM, 
    DATE, TIME, BAGS, PAYMENT_METHOD, SUPPORT_MESSAGE, CHECK_ADDRESS, 
    NEW_ADDRESS, NEW_ENTRANCE, NEW_FLOOR, NEW_APARTMENT, NEW_INTERCOM, 
    FAVORITE_NAME, SELECT_ADDRESS, MANAGE_FAVORITES, EDIT_FAVORITE_NAME,
    CONFIRM_ORDER, ASK_FAVORITE  # Добавлена ASK_FAVORITE
)
from keyboards.client_keyboards import create_date_keyboard, get_back_button, get_payment_keyboard, get_bags_keyboard
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import user_data
import datetime
import re
from utils.order_state import order_state  # Импорт для сохранения состояния

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
    "лемешева", "ул лемешева", "улица лемешева"
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

def get_bag_word(count):
    """Склонение слова 'мешок'"""
    if count == 1:
        return "мешок"
    elif 2 <= count <= 4:
        return "мешка"
    else:
        return "мешков"
# ======================================================

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса заказа - выбор адреса (из избранного или новый)"""
    # Определяем источник вызова
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        user = update.effective_user
    else:
        user_id = update.effective_user.id
        user = update.effective_user
    
    print(f"👤 Новый заказ от пользователя {user_id}")
    print(f"  • Username: @{user.username}")
    print(f"  • First name: {user.first_name}")
    print(f"  • Last name: {user.last_name}")
    
    # 👇 ВОТ СЮДА ВСТАВЛЯЙ ЭТОТ КОД 👇
    from config import user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['in_order_process'] = True
    # 👆 ДО СЮДА 👆

    # Проверяем, админ ли пользователь для обхода ограничений
    from config import admin_data
    if user_id in admin_data['admins']:
        print(f"👑 Админ {user_id} оформляет заказ без ограничений")
    
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
    
    # Сохраняем начальное состояние
    order_state.save_state(user_id, NAME, user_data.get(user_id, {}))
    
    # Проверяем, есть ли телефон и адрес
    if user_info and user_info[4]:  # если есть телефон
        user_data[user_id]['name'] = user_info[2] or user.first_name
        user_data[user_id]['phone'] = user_info[4]
        user_data[user_id]['has_saved_data'] = True
        
        # Если есть сохранённый адрес, сразу показываем выбор адреса
        return await choose_address(update, context)
    else:
        # Если нет телефона - запрашиваем имя
        if update.callback_query:
            await query.edit_message_text("📝 Шаг 1: Введите ваше имя:")
        else:
            await update.message.reply_text("📝 Шаг 1: Введите ваше имя:")
        return NAME

async def choose_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор адреса при заказе (из избранного или новый)"""
    # Проверяем, откуда пришел вызов - из callback или из сообщения
    if update.callback_query:
        # Если из callback (обычный путь)
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        message_func = query.edit_message_text
    else:
        # Если из сообщения (после ввода телефона)
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
            
            # Формируем краткое описание адреса (только улица)
            short_address = street  # Убираем добавление квартиры, так как она уже есть в названии
            
            button_text = f"{name} - {short_address}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'select_fav_{addr_id}')])
        
        # Кнопка для нового адреса
        keyboard.append([InlineKeyboardButton("➕ Ввести новый адрес", callback_data='new_address_start')])
        keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')])
        
        # Сохраняем состояние
        order_state.save_state(user_id, SELECT_ADDRESS, user_data.get(user_id, {}))
        
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
    
    # Сохраняем состояние
    order_state.save_state(user_id, DATE, user_data[user_id])
    
    # Переходим к выбору даты
    keyboard = create_date_keyboard()
    await query.edit_message_text(
        f"✅ Выбран адрес: <b>{name}</b>\n\n📅 Шаг 2: Выберите дату вывоза:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return DATE

async def bags_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора количества мешков через кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    bags = int(query.data.replace('bags_', ''))
    
    # Сохраняем в user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['bags_count'] = bags
    user_data[user_id]['bags_selected'] = True
    
    # Сохраняем состояние
    order_state.save_state(user_id, PAYMENT_METHOD, user_data[user_id])
    
    # Переходим к выбору способа оплаты
    await query.edit_message_text(
        f"🛍 Выбрано: <b>{bags} {get_bag_word(bags)}</b>\n\n"
        f"💳 Шаг 4: Выберите способ оплаты",
        parse_mode='HTML',
        reply_markup=get_payment_keyboard()
    )
    return PAYMENT_METHOD

async def new_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение адреса"""
    user_id = update.effective_user.id
    address = update.message.text.strip()
    
    print(f"🏠 Получен адрес от пользователя {user_id}: {address}")
    
    # Проверяем, что адрес не пустой
    if not address or len(address) < 5:
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректный адрес (минимум 5 символов).\n"
            "Например: <i>ул. Ленина, д. 10</i>",
            parse_mode='HTML'
        )
        return NEW_ADDRESS
    
    from config import user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Сохраняем адрес
    user_data[user_id]['street_address'] = address
    
    # ========== ПРОВЕРЯЕМ, ДОБАВЛЯЕТСЯ ЛИ АДРЕС ИЗ ИЗБРАННОГО ==========
    if user_data[user_id].get('adding_from_favorites'):
        print(f"⭐ Добавление адреса в избранное из меню избранного")
        
        # Сбрасываем флаг
        user_data[user_id]['adding_from_favorites'] = False
        
        # Подтверждаем получение адреса
        await update.message.reply_text(
            f"✅ Адрес принят: <b>{address}</b>\n\n"
            f"📝 Теперь введите название для этого адреса (например: 'Дом', 'Работа', 'Дача'):",
            parse_mode='HTML'
        )
        return FAVORITE_NAME
    
    # Обычный поток заказа - запрашиваем подъезд с подтверждением
    await update.message.reply_text(
        f"✅ Адрес принят: <b>{address}</b>\n\n"
        f"🚪 Введите номер подъезда:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip_entrance")
        ]])
    )
    return NEW_ENTRANCE
    # ============================================================
    
    # Проверяем, не вводил ли пользователь уже адрес
    if user_id in user_data and user_data[user_id].get('address_confirmed', False):
        await update.message.reply_text(
            "❌ Вы уже ввели адрес. Если хотите изменить адрес, начните заказ заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        return ConversationHandler.END
    
    # =============== ПРОВЕРКА РАЙОНА ===============
    if not is_address_allowed(address):
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
        return NEW_ADDRESS
    # ==============================================
    
    if user_id not in user_data:
        user_data[user_id] = {}
        print(f"⚠️ Создана новая запись для пользователя {user_id}")
    
    user_data[user_id]['street_address'] = address
    user_data[user_id]['address_confirmed'] = True
    print(f"✅ Сохранён новый адрес: {user_data[user_id]['street_address']}")
    print(f"🔄 Переходим к состоянию NEW_ENTRANCE ({NEW_ENTRANCE})")
    
    # Сохраняем состояние
    order_state.save_state(user_id, NEW_ENTRANCE, user_data[user_id])
    
    await update.message.reply_text("🚪 Введите номер подъезда (или 0 если нет):")
    return NEW_ENTRANCE

async def new_entrance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение подъезда"""
    user_id = update.effective_user.id
    entrance = update.message.text.strip()
    
    from config import user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Проверяем, может это кнопка "пропустить"
    if entrance.lower() in ['пропустить', 'skip', '-', ''] or update.callback_query:
        # Если это callback от кнопки "пропустить"
        if update.callback_query:
            await update.callback_query.answer()
            user_data[user_id]['entrance'] = ''
            await update.callback_query.edit_message_text(
                f"✅ Адрес: <b>{user_data[user_id].get('street_address', '')}</b>\n"
                f"🚪 Подъезд: <b>пропущен</b>\n\n"
                f"🏢 Введите этаж:"
            )
        else:
            user_data[user_id]['entrance'] = ''
            await update.message.reply_text(
                f"✅ Подъезд пропущен.\n\n"
                f"🏢 Введите этаж:"
            )
        return NEW_FLOOR
    
    # Сохраняем подъезд
    user_data[user_id]['entrance'] = entrance
    
    await update.message.reply_text(
        f"✅ Подъезд: <b>{entrance}</b>\n\n"
        f"🏢 Введите этаж:",
        parse_mode='HTML'
    )
    return NEW_FLOOR

async def new_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение нового этажа"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    text = update.message.text
    user_data[user_id]['floor'] = text if text not in ['0', '-'] else ''
    
    # Сохраняем состояние
    order_state.save_state(user_id, NEW_APARTMENT, user_data[user_id])
    
    await update.message.reply_text("🔢 Введите номер квартиры (или 0 если нет):")
    return NEW_APARTMENT

async def new_apartment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение новой квартиры"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    text = update.message.text
    user_data[user_id]['apartment'] = text if text not in ['0', '-'] else ''
    
    # Сохраняем состояние
    order_state.save_state(user_id, NEW_INTERCOM, user_data[user_id])
    
    await update.message.reply_text("🔔 Введите код домофона (или 0 если нет):")
    return NEW_INTERCOM

async def new_intercom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение нового домофона и обновление адреса в БД"""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    text = update.message.text
    user_data[user_id]['intercom'] = text if text not in ['0', '-'] else ''
    
    # Сохраняем состояние
    order_state.save_state(user_id, DATE, user_data[user_id])
    
    # Обновляем адрес в базе данных
    import database as db
    db.update_user_address(
        user_id,
        user_data[user_id]['street_address'],
        user_data[user_id].get('entrance', ''),
        user_data[user_id].get('floor', ''),
        user_data[user_id].get('apartment', ''),
        user_data[user_id].get('intercom', '')
    )
    
    # Автоматически добавляем адрес в избранное, если его там нет
    try:
        # Получаем данные для проверки
        street_address = user_data[user_id]['street_address']
        entrance = user_data[user_id].get('entrance', '')
        floor = user_data[user_id].get('floor', '')
        apartment = user_data[user_id].get('apartment', '')
        intercom = user_data[user_id].get('intercom', '')
        
        # Проверяем, есть ли уже этот адрес в избранном
        favorites = db.get_user_favorite_addresses(user_id)
        address_exists = False
        
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
    except Exception as e:
        print(f"⚠️ Ошибка при добавлении в избранное: {e}")
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

async def new_address_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ввода нового адреса"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🏠 Введите новый адрес (улица и дом):\n"
        "Например: ул. Ленина, д. 10\n\n"
        "📍 <b>Мы работаем только в Южном микрорайоне</b> на улицах:\n"
        "• Октябрьский проспект\n"
        "• Улица Можайского\n"
        "• Улица Королева\n"
        "• Улица Левитана\n"
        "• Бульвар Гусева\n"
        "• Улица Псковская\n"
        "• Улица С.Я. Лемешева",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')
        ]]),
        parse_mode='HTML'
    )
    return NEW_ADDRESS

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем имя клиента"""
    user_id = update.effective_user.id
    print(f"🔥🔥🔥 get_name ВЫЗВАНА для пользователя {user_id}")
    print(f"🔥 Текст сообщения: {update.message.text}")
    
    if user_id not in user_data:
        user_data[user_id] = {}
        print(f"🔥 Создана новая запись для {user_id}")
    
    user_data[user_id]['name'] = update.message.text
    print(f"🔥 Имя сохранено: {user_data[user_id]['name']}")
    
    # Сохраняем состояние
    order_state.save_state(user_id, PHONE, user_data[user_id])
    
    await update.message.reply_text("📞 Шаг 2: Введите номер телефона:")
    print(f"🔥 Отправлен запрос телефона, возвращаю PHONE")
    
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем телефон"""
    user_id = update.effective_user.id
    print(f"📞📞📞 get_phone ВЫЗВАНА для пользователя {user_id}")
    print(f"📞 Текст сообщения: {update.message.text}")
    
    if user_id not in user_data:
        user_data[user_id] = {}
        print(f"📞 Создана новая запись для {user_id}")
    
    user_data[user_id]['phone'] = update.message.text
    print(f"📞 Телефон сохранен: {user_data[user_id]['phone']}")
    
    # Сразу сохраняем телефон в базу
    import database as db
    db.update_user_phone(user_id, user_data[user_id]['phone'])
    print(f"📞 Телефон сохранен в БД")
    
    # Сохраняем состояние
    order_state.save_state(user_id, SELECT_ADDRESS, user_data[user_id])
    
    # Переходим к выбору адреса
    print(f"📞 Вызываю choose_address")
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
    
    # Сохраняем состояние
    order_state.save_state(user_id, DATE, user_data[user_id])
    
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
    print(f"🕐 Текущее время: {datetime.datetime.now().strftime('%H:%M:%S')}")
    
    # Получаем доступные слоты с учётом истекших и рабочего времени
    import database as db
    available_slots, slot_info = db.get_available_slots(selected_date)
    
    print(f"📅 Доступные слоты после фильтрации: {available_slots}")
    print(f"📊 Информация о слотах: {slot_info}")
    
    # Сохраняем состояние
    order_state.save_state(user_id, TIME, user_data[user_id])
    
    # Упрощённая клавиатура — только названия слотов
    time_keyboard = []
    for slot in available_slots:
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
    try:
        await query.edit_message_text(
            f"📅 Дата: {selected_date}\n\n"
            f"⏰ Выберите удобное время:",
            reply_markup=InlineKeyboardMarkup(time_keyboard)
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            print(f"Ошибка в date_callback: {e}")
    return TIME

async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени - теперь показывает кнопки с мешками"""
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
        try:
            await query.edit_message_text(
                "❌ К сожалению, это время только что заняли.\n"
                "Пожалуйста, выберите другое время:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                print(f"Ошибка в time_callback (занятое время): {e}")
        
        if user_id in user_data:
            del user_data[user_id]
        return DATE
    
    # Сохраняем состояние
    order_state.save_state(user_id, BAGS, user_data[user_id])
    
    # ПОКАЗЫВАЕМ КНОПКИ С КОЛИЧЕСТВОМ МЕШКОВ
    from keyboards.client_keyboards import get_bags_keyboard
    
    try:
        await query.edit_message_text(
            f"📅 {user_data[user_id]['order_date']} {selected_time}\n\n"
            f"🛍 Шаг 3: Сколько мешков нужно вынести? (до 15 кг суммарно)",
            reply_markup=get_bags_keyboard()
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            print(f"Ошибка в time_callback: {e}")
    
    return BAGS

async def payment_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора способа оплаты"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        print(f"💳 payment_method_handler для пользователя {user_id}")
        
        import database as db
        
        if user_id not in user_data:
            user_data[user_id] = {}
        
        payment_method = query.data.replace('pay_', '')
        
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
        
        # Сохраняем состояние
        order_state.save_state(user_id, CONFIRM_ORDER, user_data[user_id])
        
        # ===== ПРОВЕРКА БАЛАНСА =====
        conn = db.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT referral_balance FROM users WHERE user_id = %s', (user_id,))
            balance = cur.fetchone()
            if balance and balance[0] > 0:
                user_data[user_id]['bonus_balance'] = balance[0]
                
                keyboard = [
                    [
                        InlineKeyboardButton(f"✅ Использовать {balance[0]} баллов", callback_data='use_bonus_yes'),
                        InlineKeyboardButton("❌ Не использовать", callback_data='use_bonus_no')
                    ]
                ]
                
                await query.edit_message_text(
                    f"🎁 <b>У вас есть {balance[0]} бонусных баллов!</b>\n\n"
                    f"1 балл = 1 рубль скидки\n"
                    f"Хотите использовать их для этого заказа?",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return USE_BONUS
        except Exception as e:
            print(f"❌ Ошибка проверки баланса: {e}")
        finally:
            cur.close()
            conn.close()
        # ============================
        
        # Если нет баллов, сразу показываем подтверждение
        await confirm_order_before_final(update, context)
        return CONFIRM_ORDER
        
    except Exception as e:
        print(f"❌ Ошибка в payment_method_handler: {e}")
        return ConversationHandler.END

async def use_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора использования бонусов"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if choice == 'use_bonus_yes':
        user_data[user_id]['use_bonus'] = True
    else:
        user_data[user_id]['use_bonus'] = False
    
    # Сохраняем состояние
    order_state.save_state(user_id, CONFIRM_ORDER, user_data[user_id])
    
    await confirm_order_before_final(update, context)
    return CONFIRM_ORDER

async def back_to_bags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, есть ли данные пользователя
    if user_id not in user_data:
        await query.edit_message_text(
            "❌ Сессия заказа истекла. Начните заказ заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        return ConversationHandler.END
    
    # Проверяем, есть ли нужные поля
    if 'order_date' not in user_data[user_id] or 'order_time' not in user_data[user_id]:
        await query.edit_message_text(
            "❌ Данные заказа повреждены. Начните заказ заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
            ]])
        )
        return ConversationHandler.END
    
    # Сохраняем состояние
    order_state.save_state(user_id, BAGS, user_data[user_id])
    
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
    """Получаем количество пакетов (если ввели вручную, а не через кнопки)"""
    user_id = update.effective_user.id
    
    # Проверяем, не выбрал ли уже пользователь через кнопки
    if user_id in user_data and user_data[user_id].get('bags_selected', False):
        # Уже выбрано через кнопки, игнорируем ручной ввод
        return ConversationHandler.END
    
    from config import admin_data
    is_admin = user_id in admin_data['admins']
    
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
                f"🚫 Максимальное количество пакетов для одного заказа: <b>4</b>\n\n"
                f"Пожалуйста, укажите количество пакетов от 1 до 4:",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return BAGS
        
        # Сохраняем количество
        user_data[user_id]['bags_count'] = bags
        user_data[user_id]['bags_selected'] = True
        
        # Сохраняем состояние
        order_state.save_state(user_id, PAYMENT_METHOD, user_data[user_id])
        
        # Переходим к оплате
        await update.message.reply_text(
            f"🛍 Выбрано: <b>{bags} {get_bag_word(bags)}</b>\n\n"
            f"💳 Шаг 4: Выберите способ оплаты",
            parse_mode='HTML',
            reply_markup=get_payment_keyboard()
        )
        return PAYMENT_METHOD
        
    except ValueError:
        await update.message.reply_text(
            "❌ Введите число! Количество пакетов должно быть от 1 до 4:"
        )
        return BAGS

async def confirm_order_before_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ сводки заказа перед подтверждением"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Собираем всю информацию
    name = user_data[user_id]['name']
    phone = user_data[user_id]['phone']
    address = user_data[user_id]['street_address']
    date = user_data[user_id]['order_date']
    time = user_data[user_id]['order_time']
    bags = user_data[user_id]['bags_count']
    payment = user_data[user_id]['payment_method']
    
    from utils.helpers import calculate_price
    original_price = calculate_price(bags)
    final_price = original_price
    
    # Проверяем, использованы ли бонусы
    use_bonus = user_data[user_id].get('use_bonus', False)
    bonus_text = ""
    
    if use_bonus:
        balance = user_data[user_id].get('bonus_balance', 0)
        if balance >= original_price:
            # Можно оплатить полностью
            final_price = 0
            bonus_text = f"\n🎁 Скидка баллами: -{original_price} ₽\n💰 К оплате: 0 ₽ (бесплатно!)"
        else:
            # Частичная оплата
            final_price = original_price - balance
            bonus_text = f"\n🎁 Скидка баллами: -{balance} ₽\n💰 К оплате: {final_price} ₽"
    
    payment_names = {
        'cash': '💵 Наличные',
        'card': '💳 Перевод на карту',
        'yookassa': '💰 Онлайн'
    }
    
    text = (
        f"📋 <b>Проверьте данные заказа:</b>\n\n"
        f"👤 {name}\n"
        f"📞 {phone}\n"
        f"📍 {address}\n"
        f"📅 {date} {time}\n"
        f"🛍 {bags} {get_bag_word(bags)}\n"
        f"💳 Оплата: {payment_names.get(payment, payment)}"
        f"{bonus_text}\n\n"
        f"✅ Всё верно?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, подтвердить", callback_data='final_confirm'),
            InlineKeyboardButton("✏️ Изменить", callback_data='change_address')
        ]
    ]
    
    # Сохраняем финальную цену
    user_data[user_id]['final_price'] = final_price
    user_data[user_id]['used_bonus'] = balance if use_bonus else 0
    
    # Сохраняем состояние
    order_state.save_state(user_id, CONFIRM_ORDER, user_data[user_id])
    
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if "Message is not modified" not in str(e):
            print(f"Ошибка в confirm_order_before_final: {e}")
    
    return CONFIRM_ORDER

async def final_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальное подтверждение и создание заказа"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        print(f"🔍 FINAL_CONFIRM для пользователя {user_id}")
        
        # Очищаем состояние после успешного заказа
        order_state.clear_state(user_id)
        
        # Проверяем, есть ли данные пользователя
        if user_id not in user_data:
            await query.edit_message_text(
                "❌ Произошла ошибка. Начните заказ заново.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
                ]])
            )
            return ConversationHandler.END
        
        from config import admin_data
        from utils.helpers import calculate_price
        import database as db
        from handlers.admin import notify_admin
        
        # Получаем данные из user_data
        name = user_data[user_id]['name']
        phone = user_data[user_id]['phone']
        street_address = user_data[user_id]['street_address']
        entrance = user_data[user_id].get('entrance', '')
        floor = user_data[user_id].get('floor', '')
        apartment = user_data[user_id].get('apartment', '')
        intercom = user_data[user_id].get('intercom', '')
        order_date = user_data[user_id]['order_date']
        order_time = user_data[user_id]['order_time']
        bags = user_data[user_id]['bags_count']
        payment_method = user_data[user_id]['payment_method']
        
        # Рассчитываем цену
        price = calculate_price(bags)
        
        # Проверяем, свободен ли слот
        is_free = db.is_time_slot_free(order_date, order_time)
        
        if not is_free:
            keyboard = create_date_keyboard()
            await query.edit_message_text(
                "❌ К сожалению, это время только что заняли.\n"
                "Пожалуйста, выберите другую дату:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            if user_id in user_data:
                del user_data[user_id]
            return DATE
        
        # Создаём заказ
        result = db.create_order(
            user_id=user_id,
            client_name=name,
            phone=phone,
            street_address=street_address,
            entrance=entrance,
            floor=floor,
            apartment=apartment,
            intercom=intercom,
            order_date=order_date,
            order_time=order_time,
            bags_count=bags,
            price=price,
            payment_method=payment_method
        )
        
        print(f"🔍 РЕЗУЛЬТАТ СОЗДАНИЯ ЗАКАЗА: {result}")
        
        if result[0] is False:
            print(f"❌ ОШИБКА СОЗДАНИЯ ЗАКАЗА: {result[1]}")
            await query.edit_message_text(
                f"❌ {result[1]}\n\nПожалуйста, попробуйте ещё раз.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 Новый заказ", callback_data='new_order')
                ]])
            )
            if user_id in user_data:
                del user_data[user_id]
            return ConversationHandler.END
        
        order_id = result[0]
        
        # 👇 СТРОКА, КОТОРУЮ НУЖНО ДОБАВИТЬ 👇
        # Заказ успешно создан, снимаем флаг процесса
        user_data[user_id]['in_order_process'] = False
        # 👆
        
        # ===== СОХРАНЕНИЕ АДРЕСА В ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====
        try:
            # Обновляем адрес пользователя в таблице users
            db.update_user_address(
                user_id,
                street_address,
                entrance,
                floor,
                apartment,
                intercom
            )
            print(f"✅ Адрес пользователя {user_id} сохранён в профиль")
        except Exception as e:
            print(f"❌ Ошибка сохранения адреса: {e}")
        # ====================================================
        
        # ===== СПИСАНИЕ БОНУСОВ =====
        if user_data[user_id].get('use_bonus', False):
            used_bonus = user_data[user_id].get('used_bonus', 0)
            if used_bonus > 0:
                conn = db.get_connection()
                cur = conn.cursor()
                try:
                    # Списываем баллы
                    cur.execute('''
                        UPDATE users 
                        SET referral_balance = referral_balance - %s 
                        WHERE user_id = %s
                    ''', (used_bonus, user_id))
                    
                    # Записываем трату
                    cur.execute('''
                        INSERT INTO referral_spendings (user_id, amount, order_id, created_at)
                        VALUES (%s, %s, %s, %s)
                    ''', (user_id, used_bonus, order_id, datetime.datetime.now()))
                    
                    conn.commit()
                    print(f"✅ Списано {used_bonus} баллов у пользователя {user_id}")
                except Exception as e:
                    print(f"❌ Ошибка списания баллов: {e}")
                finally:
                    cur.close()
                    conn.close()
        # ============================
        
        # ===== НАЧИСЛЕНИЕ БАЛЛОВ ЗА РЕФЕРАЛА =====
        conn = db.get_connection()
        cur = conn.cursor()
        try:
            # Проверяем, не пришёл ли пользователь по реферальной ссылке
            cur.execute('SELECT referred_by FROM users WHERE user_id = %s', (user_id,))
            referred_by = cur.fetchone()
            
            if referred_by and referred_by[0]:
                referrer_id = referred_by[0]
                # Начисляем баллы пригласившему
                db.process_referral_reward(referrer_id, user_id, order_id)
                print(f"✅ Начислены баллы за реферала {user_id} пользователю {referrer_id}")
        except Exception as e:
            print(f"❌ Ошибка проверки реферала: {e}")
        finally:
            cur.close()
            conn.close()
        # ========================================
        
        # Формируем полный адрес для сообщения
        full_address = street_address
        details = []
        if entrance and entrance not in ['0', '-']:
            details.append(f"под. {entrance}")
        if floor and floor not in ['0', '-']:
            details.append(f"эт. {floor}")
        if apartment and apartment not in ['0', '-']:
            details.append(f"кв. {apartment}")
        if intercom and intercom not in ['0', '-']:
            details.append(f"домофон {intercom}")
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
        
        await query.edit_message_text(
            f"✅ <b>Заказ #{order_id} принят!</b>\n\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📍 {full_address}\n"
            f"📅 {order_date} {order_time}\n"
            f"🛍 {bags} пакетов\n"
            f"{price_text}\n"
            f"{payment_text}\n\n"
            f"🚶‍♂️ <b>Что дальше?</b>\n"
            f"Курьер приедет в указанное время, поднимется к вам и заберёт пакеты.\n"
            f"Подтверждение заказа придёт отдельно.",
            parse_mode='HTML'
        )
        
        # Уведомление админам
        for admin_id in admin_data['admins']:
            try:
                # Получаем заказ для уведомления
                order = db.get_order_by_id(order_id)
                if order:
                    # Формируем текст уведомления
                    username = db.get_username_by_id(user_id)
                    username_text = f" (@{username})" if username and username != "неизвестно" else ""
                    
                    # Формируем адрес
                    full_address = street_address
                    details = []
                    if entrance and entrance not in ['0', '-']:
                        details.append(f"под. {entrance}")
                    if floor and floor not in ['0', '-']:
                        details.append(f"эт. {floor}")
                    if apartment and apartment not in ['0', '-']:
                        details.append(f"кв. {apartment}")
                    if intercom and intercom not in ['0', '-']:
                        details.append(f"домофон {intercom}")
                    if details:
                        full_address += f" ({', '.join(details)})"
                    
                    text = (
                        f"🚨 <b>НОВЫЙ ЗАКАЗ #{order_id} (НА ВЫНОС)</b>\n\n"
                        f"👤 {name}{username_text}\n"
                        f"📞 {phone}\n"
                        f"📍 {full_address}\n"
                        f"📅 {order_date} {order_time}\n"
                        f"🛍 {bags} пакетов\n"
                        f"💰 {price} ₽\n"
                    )
                    
                    # Кнопки для админа
                    keyboard = []
                    
                    # Кнопка связи если есть username
                    if username and username != "неизвестно":
                        clean_username = username.replace('@', '')
                        keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{clean_username}")])
                    
                    # Кнопки управления заказом
                    keyboard.append([
                        InlineKeyboardButton("✅ Подтверждаю", callback_data=f'confirm_{order_id}'),
                        InlineKeyboardButton("✅ Выполнено", callback_data=f'complete_{order_id}'),
                        InlineKeyboardButton("❌ Отменить", callback_data=f'cancel_{order_id}')
                    ])
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=text,
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    print(f"✅ Уведомление о заказе #{order_id} отправлено админу {admin_id}")
            except Exception as e:
                print(f"❌ Ошибка уведомления админа {admin_id}: {e}")
        
        # Спрашиваем про избранное (сохраняем user_id для этого)
        context.user_data['last_order_user_id'] = user_id
        await ask_add_to_favorites(update, context)
        return ASK_FAVORITE
        
    except Exception as e:
        print(f"❌ Ошибка в final_confirm_order: {e}")
        import traceback
        traceback.print_exc()
        return ConversationHandler.END

async def ask_add_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спрашивает пользователя, хочет ли он добавить адрес в избранное"""
    query = update.callback_query
    await query.answer()
    
    # Получаем user_id из разных возможных источников
    if 'last_order_user_id' in context.user_data:
        user_id = context.user_data['last_order_user_id']
        del context.user_data['last_order_user_id']
    else:
        user_id = query.from_user.id
    
    # Проверяем, есть ли данные пользователя в user_data
    if user_id not in user_data:
        # Если нет, просто показываем главное меню
        from keyboards.client_keyboards import get_main_keyboard
        from config import admin_data
        is_admin = user_id in admin_data['admins']
        keyboard = get_main_keyboard(is_admin)
        
        await query.edit_message_text(
            "👋 Главное меню:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    # Получаем данные адреса из user_data
    street_address = user_data[user_id].get('street_address', '')
    entrance = user_data[user_id].get('entrance', '')
    floor = user_data[user_id].get('floor', '')
    apartment = user_data[user_id].get('apartment', '')
    intercom = user_data[user_id].get('intercom', '')
    
    if not street_address:
        # Если нет адреса, просто возвращаемся в меню
        from keyboards.client_keyboards import get_main_keyboard
        from config import admin_data
        is_admin = user_id in admin_data['admins']
        keyboard = get_main_keyboard(is_admin)
        
        await query.edit_message_text(
            "👋 Главное меню:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    # Формируем красивый адрес
    full_address = street_address
    details = []
    if entrance and entrance not in ['0', '-']:
        details.append(f"под. {entrance}")
    if floor and floor not in ['0', '-']:
        details.append(f"эт. {floor}")
    if apartment and apartment not in ['0', '-']:
        details.append(f"кв. {apartment}")
    if intercom and intercom not in ['0', '-']:
        details.append(f"домофон {intercom}")
    if details:
        full_address += f" ({', '.join(details)})"
    
    # Проверяем, есть ли уже этот адрес в избранном
    import database as db
    favorites = db.get_user_favorite_addresses(user_id)
    address_exists = False
    
    for fav in favorites:
        if (fav[2] == street_address and
            fav[3] == entrance and
            fav[4] == floor and
            fav[5] == apartment and
            fav[6] == intercom):
            address_exists = True
            break
    
    if address_exists:
        # Если адрес уже есть в избранном, просто показываем меню
        text = f"✅ <b>Заказ оформлен!</b>\n\n📍 {full_address}\n\nАдрес уже есть в избранном."
        keyboard = [[InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]]
    else:
        # Спрашиваем, добавить ли в избранное
        text = (
            f"✅ <b>Заказ оформлен!</b>\n\n"
            f"📍 <b>Ваш адрес:</b>\n{full_address}\n\n"
            f"⭐ Хотите добавить этот адрес в избранное?\n"
            f"В следующий раз не нужно будет вводить его заново!"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, добавить", callback_data='favorite_add_after_order'),
                InlineKeyboardButton("❌ Нет", callback_data='back_to_menu')
            ]
        ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_FAVORITE

async def favorite_add_after_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление адреса в избранное после завершения заказа"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, есть ли данные в user_data
    if user_id not in user_data:
        # Если данных нет, показываем сообщение об ошибке
        from keyboards.client_keyboards import get_main_keyboard
        from config import admin_data
        is_admin = user_id in admin_data['admins']
        
        await query.edit_message_text(
            "❌ Данные заказа не найдены. Адрес не добавлен в избранное.",
            reply_markup=get_main_keyboard(is_admin)
        )
        return ConversationHandler.END
    
    # Получаем данные адреса из user_data
    street_address = user_data[user_id].get('street_address', '')
    entrance = user_data[user_id].get('entrance', '')
    floor = user_data[user_id].get('floor', '')
    apartment = user_data[user_id].get('apartment', '')
    intercom = user_data[user_id].get('intercom', '')
    
    if not street_address:
        from keyboards.client_keyboards import get_main_keyboard
        from config import admin_data
        is_admin = user_id in admin_data['admins']
        
        await query.edit_message_text(
            "❌ Адрес не найден",
            reply_markup=get_main_keyboard(is_admin)
        )
        return ConversationHandler.END
    
    import database as db
    
    # Получаем список избранного для определения названия
    favorites = db.get_user_favorite_addresses(user_id)
    
    # Создаем название по умолчанию
    default_name = generate_address_name(user_id, street_address, apartment)
    
    # Сохраняем адрес в избранное
    db.save_favorite_address(
        user_id,
        default_name,
        street_address,
        entrance,
        floor,
        apartment,
        intercom
    )
    
    # Формируем красивый адрес для подтверждения
    full_address = street_address
    details = []
    if entrance and entrance not in ['0', '-']:
        details.append(f"под. {entrance}")
    if floor and floor not in ['0', '-']:
        details.append(f"эт. {floor}")
    if apartment and apartment not in ['0', '-']:
        details.append(f"кв. {apartment}")
    if intercom and intercom not in ['0', '-']:
        details.append(f"домофон {intercom}")
    if details:
        full_address += f" ({', '.join(details)})"
    
    from keyboards.client_keyboards import get_main_keyboard
    from config import admin_data
    is_admin = user_id in admin_data['admins']
    
    await query.edit_message_text(
        f"✅ <b>Адрес добавлен в избранное!</b>\n\n"
        f"📍 {full_address}\n"
        f"🏷 Название: {default_name}\n\n"
        f"Вы можете изменить название в разделе 'Мои адреса'.",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(is_admin)
    )
    
    # Очищаем данные пользователя
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

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
            
            text += f"🏷 <b>{name}</b>\n📍 {full}\n\n"
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

async def favorite_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение адреса в избранное"""
    user_id = update.effective_user.id
    favorite_name = update.message.text
    
    from config import user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Получаем данные адреса
    address_data = {
        'street_address': user_data[user_id].get('street_address'),
        'entrance': user_data[user_id].get('entrance', ''),
        'floor': user_data[user_id].get('floor', ''),
        'apartment': user_data[user_id].get('apartment', ''),
        'intercom': user_data[user_id].get('intercom', '')
    }
    
    # Сохраняем в базу
    import database as db
    favorite_id = db.add_favorite_address(
        user_id=user_id,
        name=favorite_name,
        **address_data
    )
    
    if favorite_id:
        await update.message.reply_text(
            f"✅ Адрес <b>«{favorite_name}»</b> добавлен в избранное!\n\n"
            f"📍 <b>Адрес:</b> {address_data['street_address']}\n"
            f"🚪 <b>Подъезд:</b> {address_data['entrance'] or 'не указан'}\n"
            f"🏢 <b>Этаж:</b> {address_data['floor'] or 'не указан'}\n"
            f"🚪 <b>Квартира:</b> {address_data['apartment'] or 'не указана'}\n"
            f"📞 <b>Домофон:</b> {address_data['intercom'] or 'не указан'}",
            parse_mode='HTML'
        )
        
        # Показываем меню избранного
        from keyboards.client_keyboards import get_favorites_menu_keyboard
        favorites = db.get_user_favorites(user_id)
        
        await update.message.reply_text(
            "📍 <b>Ваши избранные адреса:</b>\n\n"
            "Теперь этот адрес доступен при заказе!",
            parse_mode='HTML',
            reply_markup=get_favorites_menu_keyboard(favorites)
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Ошибка при сохранении адреса")
        return ConversationHandler.END

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

async def my_orders_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список заказов пользователя"""
    # Определяем источник вызова
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        message_func = query.edit_message_text
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text
    
    import database as db
    orders = db.get_user_orders(user_id)
    
    if not orders:
        await message_func(
            "📭 У вас пока нет заказов.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')
            ]])
        )
        return
    
    text = "📋 <b>Ваши заказы:</b>\n\n"
    for order in orders[:5]:
        # БЕЗОПАСНАЯ РАСПАКОВКА через индексы
        order_id = order[0]
        date = order[9] if len(order) > 9 else ''
        time = order[10] if len(order) > 10 else ''
        bags = order[11] if len(order) > 11 else 0
        price = order[12] if len(order) > 12 else 0
        status = order[13] if len(order) > 13 else 'unknown'
        
        status_emoji = {
            'new': '🆕', 
            'confirmed': '✅', 
            'completed': '✅', 
            'cancelled': '❌'
        }.get(status, '📝')
        
        text += f"{status_emoji} #{order_id} — {date} {time}, {bags} мешков — {price} ₽\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]
    await message_func(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

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
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='my_orders_detail')
            ]])
        )
        return
    
    keyboard = []
    for order in orders[:5]:
        order_id, _, _, _, date, time, bags, price, status, _ = order
        status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
        button_text = f"{status_emoji} #{order_id} от {date} {time} ({bags} меш.)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'order_detail_{order_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='my_orders_detail')])
    
    await query.edit_message_text(
        "Выберите заказ для просмотра:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    status_emoji = {'new': '🆕', 'confirmed': '✅', 'completed': '✅', 'cancelled': '❌'}.get(status, '📝')
    status_text = {'new': 'Активен', 'confirmed': 'Подтверждён', 'completed': 'Выполнен', 'cancelled': 'Отменён'}.get(status, status)
    
    text = (
        f"{status_emoji} <b>Заказ #{order_id}</b>\n\n"
        f"👤 {name}\n"
        f"📞 {phone}\n"
        f"📍 {full_address}\n"
        f"📅 {date} {time}\n"
        f"🛍 {bags} мешков — {price} ₽\n"
        f"📊 Статус: {status_text}\n\n"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад к списку", callback_data='order_detail_select')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def repeat_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повтор предыдущего заказа"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.replace('repeat_order_', ''))
    import database as db
    order = db.get_order_by_id(order_id)
    
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    
    # Заполняем данные из прошлого заказа
    user_id = query.from_user.id
    
    # Безопасная распаковка
    name = order[2] if len(order) > 2 else ''
    phone = order[3] if len(order) > 3 else ''
    street = order[4] if len(order) > 4 else ''
    entrance = order[5] if len(order) > 5 else ''
    floor = order[6] if len(order) > 6 else ''
    apt = order[7] if len(order) > 7 else ''
    intercom = order[8] if len(order) > 8 else ''
    
    from config import user_data
    user_data[user_id] = {
        'name': name,
        'phone': phone,
        'street_address': street,
        'entrance': entrance or '',
        'floor': floor or '',
        'apartment': apt or '',
        'intercom': intercom or ''
    }
    
    # Сохраняем состояние
    from utils.order_state import order_state
    order_state.save_state(user_id, DATE, user_data[user_id])
    
    # Переходим к выбору даты
    from keyboards.client_keyboards import create_date_keyboard
    keyboard = create_date_keyboard()
    await query.edit_message_text(
        "📅 Выберите новую дату для повторного заказа:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DATE

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