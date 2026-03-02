# keyboards/reply_keyboards.py
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def get_main_reply_keyboard(is_admin=False):
    """
    Главная reply-клавиатура (постоянные кнопки внизу)
    Появляется после /start и остается до скрытия
    """
    
    # Основные кнопки для всех пользователей
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
            KeyboardButton("📞 Связаться с нами"),
            KeyboardButton("📋 Правила")
        ]
    ]
    
    # Кнопка для админа (если пользователь в списке админов)
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админ-панель")])
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,  # Автоматически подгонять размер под экран
        input_field_placeholder="👇 Нажмите кнопку или напишите сообщение...",
        one_time_keyboard=False  # Клавиатура не исчезает после нажатия
    )

def get_admin_reply_keyboard():
    """
    Клавиатура для админ-панели (более детальная)
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

def hide_keyboard():
    """
    Скрыть reply-клавиатуру
    """
    return ReplyKeyboardRemove()