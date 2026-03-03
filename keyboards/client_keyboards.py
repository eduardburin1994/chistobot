# keyboards/client_keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import datetime
from datetime import timedelta

def create_date_keyboard():
    """Создает клавиатуру с 3 датами: сегодня, завтра, послезавтра"""
    keyboard = []
    today = datetime.datetime.now()
    
    # Названия дней недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    for i in range(0, 3):  # 0 - сегодня, 1 - завтра, 2 - послезавтра
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekday = weekdays[date.weekday()]
        
        if i == 0:
            button_text = f"📅 Сегодня ({date_str} {weekday})"
        elif i == 1:
            button_text = f"📅 Завтра ({date_str} {weekday})"
        else:
            button_text = f"📅 Послезавтра ({date_str} {weekday})"
            
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'date_{date_str}')])
    
    return keyboard

def get_main_keyboard(is_admin=False):
    """Главное меню (компактная версия)"""
    keyboard = [
        [
            InlineKeyboardButton("📦 Заказать вынос", callback_data='new_order'),
            InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders_detail')
        ],
        [
            InlineKeyboardButton("⭐ Избранное", callback_data='favorite_menu'),
            InlineKeyboardButton("💰 Цены", callback_data='prices')
        ],
        [
            InlineKeyboardButton("📋 Правила", callback_data='rules'),
            InlineKeyboardButton("📞 Связаться", callback_data='contact')
        ]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админка", callback_data='admin')])
    
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

def get_back_button():
    """Кнопка возврата в главное меню"""
    keyboard = [[InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]]
    return InlineKeyboardMarkup(keyboard)
