# handlers/referral/keyboard.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_referral_keyboard():
    """Клавиатура для реферального раздела"""
    keyboard = [
        [
            InlineKeyboardButton("📋 История", callback_data='referral_history'),
            InlineKeyboardButton("🏆 Топ", callback_data='referral_top')
        ],
        [
            InlineKeyboardButton("❓ Как это работает", callback_data='referral_help'),
            InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
