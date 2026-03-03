# keyboards/reply_keyboards.py
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def get_main_reply_keyboard(is_admin=False):
    """
    Главная reply-клавиатура (появляется только в главном меню)
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
    
    # Кнопка для админа
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админ-панель")])
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="👇 Нажмите кнопку или напишите сообщение...",
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
    return ReplyKeyboardRemove()
