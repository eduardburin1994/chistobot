# keyboards/client_keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import datetime
from datetime import timedelta

def create_date_keyboard():
    """Создает клавиатуру с доступными датами (исключая прошедшие и без слотов)"""
    keyboard = []
    today = datetime.datetime.now()
    
    # Названия дней недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    # Проверяем, есть ли сегодня доступные слоты
    from database import get_available_slots
    
    for i in range(0, 3):  # 0 - сегодня, 1 - завтра, 2 - послезавтра
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = weekdays[date.weekday()]
        
        # Проверяем, есть ли доступные слоты на эту дату
        available_slots, _ = get_available_slots(date_str)
        
        # Если сегодня и уже нет доступных слотов - пропускаем эту дату
        if i == 0 and not available_slots:
            continue
            
        if i == 0:
            button_text = f"📅 Сегодня ({date_str} {weekday})"
        elif i == 1:
            button_text = f"📅 Завтра ({date_str} {weekday})"
        else:
            button_text = f"📅 Послезавтра ({date_str} {weekday})"
            
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'date_{date_str}')])
    
    # Если нет доступных дат, показываем сообщение
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')])
    
    return keyboard

def get_main_keyboard(is_admin=False):
    """Главное меню (компактная версия)"""
    keyboard = [
        [
            InlineKeyboardButton("📦 ЗАКАЗАТЬ", callback_data='new_order'),  # короче
            InlineKeyboardButton("📋 ЗАКАЗЫ", callback_data='my_orders_detail')
        ],
        [
            InlineKeyboardButton("⭐ ИЗБРАННОЕ", callback_data='favorite_menu'),
            InlineKeyboardButton("💰 ЦЕНЫ", callback_data='prices')
        ],
        [
            InlineKeyboardButton("📋 ПРАВИЛА", callback_data='rules'),
            InlineKeyboardButton("📞 СВЯЗЬ", callback_data='contact')
        ],
        [InlineKeyboardButton("🎁 ПРИВЕСТИ ДРУГА", callback_data='referral_info')]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ АДМИНКА", callback_data='admin')])
    
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard():
    """Клавиатура выбора способа оплаты"""
    keyboard = [
        [InlineKeyboardButton("💵 Наличные курьеру", callback_data='pay_cash')],
        [InlineKeyboardButton("💳 Перевод на карту курьера", callback_data='pay_card')],
        [InlineKeyboardButton("💰 Онлайн-оплата (ЮKassa)", callback_data='pay_yookassa')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_bags')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bags_keyboard():
    """Клавиатура для выбора количества мешков"""
    keyboard = [
        [
            InlineKeyboardButton("1 мешок", callback_data='bags_1'),
            InlineKeyboardButton("2 мешка", callback_data='bags_2')
        ],
        [
            InlineKeyboardButton("3 мешка", callback_data='bags_3'),
            InlineKeyboardButton("4 мешка", callback_data='bags_4')
        ],
        [InlineKeyboardButton("◀️ Отмена заказа", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button():
    """Кнопка возврата в главное меню"""
    keyboard = [[InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]]
    return InlineKeyboardMarkup(keyboard)

# =============== REPLY-КЛАВИАТУРЫ ===============

def get_main_reply_keyboard(is_admin=False):
    """Главная reply-клавиатура (компактная)"""
    keyboard = [
        [
            KeyboardButton("📦 Заказать вынос"),
            KeyboardButton("💰 Цены")
        ],
        [
            KeyboardButton("📋 Мои заказы"),
            KeyboardButton("⭐ Избранное")
        ],
        [
            KeyboardButton("📞 Связаться"),
            KeyboardButton("📋 Правила")
        ]
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ Админка")])
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Меню...",
        one_time_keyboard=False
    )

def get_admin_reply_keyboard():
    """
    Клавиатура для админ-панели
    """
    keyboard = [
        [
            KeyboardButton("📦 Заказы"),
            KeyboardButton("👥 Клиенты")
        ],
        [
            KeyboardButton("💰 Цены"),
            KeyboardButton("⏰ Время работы")
        ],
        [
            KeyboardButton("📢 Рассылка"),
            KeyboardButton("🚫 Черный список")
        ],
        [
            KeyboardButton("📊 Статистика"),
            KeyboardButton("⚙️ Настройки")
        ],
        [
            KeyboardButton("◀️ Назад в главное меню")
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Админ-меню...",
        one_time_keyboard=False
    )

def remove_keyboard():
    """
    Скрыть reply-клавиатуру (используется во время диалогов)
    """
    from telegram import ReplyKeyboardRemove
    return ReplyKeyboardRemove()
def get_favorites_menu_keyboard(favorites):
    """
    Клавиатура для меню избранных адресов
    favorites: список кортежей (id, name, address, ...)
    """
    keyboard = []
    
    if not favorites:
        # Если нет избранных адресов
        keyboard.append([
            InlineKeyboardButton("➕ Добавить адрес", callback_data="favorite_add_new_address")
        ])
    else:
        # Показываем все избранные адреса
        for fav in favorites:
            # Предполагаем, что favorites содержит (id, name, ...)
            fav_id = fav[0]
            name = fav[1]
            keyboard.append([
                InlineKeyboardButton(f"📍 {name}", callback_data=f"select_fav_{fav_id}")
            ])
        
        # Кнопка добавления нового адреса
        keyboard.append([
            InlineKeyboardButton("➕ Добавить новый адрес", callback_data="favorite_add_new_address")
        ])
        
        # Кнопки управления
        keyboard.append([
            InlineKeyboardButton("✏️ Управлять адресами", callback_data="manage_favorites")
        ])
    
    # Кнопка возврата в главное меню
    keyboard.append([
        InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)