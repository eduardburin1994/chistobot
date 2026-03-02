# keyboards/client_keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import datetime
from datetime import timedelta

def create_date_keyboard():
    """Создает клавиатуру с ближайшими 5 датами"""
    keyboard = []
    today = datetime.datetime.now()
    
    for i in range(1, 6):
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        weekday = weekdays[date.weekday()]
        button_text = f"{date_str} ({weekday})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'date_{date_str}')])
    
    return keyboard

def get_main_keyboard(is_admin=False):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📦 Заказать вывоз", callback_data='new_order')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders_detail')],
        [InlineKeyboardButton("⭐ Избранные адреса", callback_data='favorite_menu')],
        [InlineKeyboardButton("💰 Наши расценки", callback_data='prices')],
        [InlineKeyboardButton("📋 Правила", callback_data='rules')],
        [InlineKeyboardButton("📞 Связаться", callback_data='contact')],
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin')])
    
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
