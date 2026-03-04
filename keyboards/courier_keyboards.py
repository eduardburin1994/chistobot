from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def get_courier_main_keyboard():
    """Главное меню курьера (reply)"""
    keyboard = [
        [KeyboardButton("📦 Активные заказы")],
        [KeyboardButton("✅ Мои выполненные")],
        [KeyboardButton("📊 Моя статистика")],
        [KeyboardButton("🚪 Выйти")]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Меню курьера..."
    )

def get_courier_back_button():
    """Кнопка возврата в главное меню"""
    keyboard = [[InlineKeyboardButton("◀️ В главное меню", callback_data='courier_back')]]
    return InlineKeyboardMarkup(keyboard)

def get_courier_orders_navigation():
    """Кнопки навигации по заказам"""
    keyboard = [
        [
            InlineKeyboardButton("◀️ Назад", callback_data='courier_active_orders'),
            InlineKeyboardButton("🔄 Обновить", callback_data='courier_active_orders')
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='courier_back')]
    ]
    return InlineKeyboardMarkup(keyboard)