# handlers/reply_handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # ВАЖНО: добавил InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import admin_data
from keyboards.reply_keyboards import get_main_reply_keyboard, get_admin_reply_keyboard, hide_keyboard
from constants import *

# Вспомогательный класс для имитации callback_query
class MockCallbackQuery:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = type('', (), {})()
        self.from_user.id = user_id
        self.message = message
    
    async def answer(self):
        pass

async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка нажатий на reply-кнопки
    """
    text = update.message.text
    user_id = update.effective_user.id
    is_admin = user_id in admin_data['admins']
    
    print(f"🔘 Нажата reply-кнопка: {text}")
    
    # =============== ГЛАВНОЕ МЕНЮ ===============
    if text == "📦 Заказать вынос":
        from handlers.client import start_order
        mock_query = MockCallbackQuery('new_order', user_id, update.message)
        await start_order(update, context)
        return
    
    elif text == "💰 Цены":
        from handlers.common import show_prices
        # Показываем расценки прямо в чате
        price_text = (
            "💰 <b>Наши расценки:</b>\n\n"
            f"• 🟢 <b>1 пакет</b> — {admin_data['prices']['1']} ₽\n"
            f"  <i>(курьер заберёт и утилизирует один пакет)</i>\n\n"
            f"• 🟡 <b>2 пакета</b> — {admin_data['prices']['2']} ₽\n"
            f"  <i>(за два пакета, включая вынос)</i>\n\n"
            f"• 🔴 <b>3 и более пакетов</b> — {admin_data['prices']['3+']} ₽\n"
            f"  <i>(фиксированная цена за весь объём)</i>\n\n"
            "⚠️ <b>Важно:</b> Общий вес всех пакетов не должен превышать 15 кг!\n\n"
            "💳 Оплата наличными или переводом курьеру после выполнения."
        )
        await update.message.reply_text(price_text, parse_mode='HTML')
        return
    
    elif text == "📋 Мои заказы":
        from handlers.client import my_orders_detail
        mock_query = MockCallbackQuery('my_orders_detail', user_id, update.message)
        await my_orders_detail(update, context)
        return
    
    elif text == "⭐ Избранное":
        from handlers.client import favorite_addresses_menu
        mock_query = MockCallbackQuery('favorite_menu', user_id, update.message)
        await favorite_addresses_menu(update, context)
        return
    
    elif text == "📞 Связаться с нами":
        from handlers.common import show_contact
        contact_text = (
            "📞 <b>Связаться с нами:</b>\n\n"
            "Выберите способ связи:"
        )
        keyboard = [
            [InlineKeyboardButton("💬 Написать админу", callback_data='support_write')],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
        ]
        await update.message.reply_text(
            contact_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)  # Теперь работает!
        )
        return
    
    elif text == "📋 Правила":
        rules_text = (
            "📋 <b>Правила и условия:</b>\n\n"
            "1️⃣ <b>Вес:</b> Общий вес всех пакетов не более 15 кг.\n"
            "2️⃣ <b>Отмена:</b> Вы можете отменить заказ за 4 часа до прихода курьера.\n"
            "3️⃣ <b>Время работы:</b> Заявки принимаются с 10:00 до 22:00.\n"
            "4️⃣ <b>Отказ:</b> При превышении веса курьер вправе отказаться от выноса.\n"
            "5️⃣ <b>Что можно выносить:</b> Обычные бытовые отходы. Строительный мусор и опасные отходы не принимаются.\n"
            "6️⃣ <b>Как это работает:</b> Курьер забирает пакеты прямо от вашей двери и самостоятельно утилизирует их в ближайшем баке."
        )
        await update.message.reply_text(rules_text, parse_mode='HTML')
        return
    
    # =============== АДМИН-МЕНЮ ===============
    elif text == "👑 Админ-панель" and is_admin:
        from handlers.admin import admin_panel
        mock_query = MockCallbackQuery('admin', user_id, update.message)
        await admin_panel(update, context)
        # Меняем клавиатуру на админскую
        await update.message.reply_text(
            "👑 Вы в админ-панели. Используйте кнопки ниже:",
            reply_markup=get_admin_reply_keyboard()
        )
        return
    
    elif text == "📦 Заказы" and is_admin:
        from handlers.admin import admin_orders
        mock_query = MockCallbackQuery('admin_orders', user_id, update.message)
        await admin_orders(update, context)
        return
    
    elif text == "👥 Клиенты" and is_admin:
        from handlers.admin import admin_clients
        mock_query = MockCallbackQuery('admin_clients', user_id, update.message)
        await admin_clients(update, context)
        return
    
    elif text == "💰 Цены" and is_admin:
        from handlers.admin import admin_prices_menu
        mock_query = MockCallbackQuery('admin_prices_menu', user_id, update.message)
        await admin_prices_menu(update, context)
        return
    
    elif text == "⏰ Время работы" and is_admin:
        from handlers.admin import admin_working_hours
        mock_query = MockCallbackQuery('admin_working_hours', user_id, update.message)
        await admin_working_hours(update, context)
        return
    
    elif text == "📢 Рассылка" and is_admin:
        from handlers.admin import admin_broadcast
        mock_query = MockCallbackQuery('admin_broadcast', user_id, update.message)
        await admin_broadcast(update, context)
        return
    
    elif text == "🚫 Черный список" and is_admin:
        from handlers.admin import admin_blacklist_menu
        mock_query = MockCallbackQuery('admin_blacklist', user_id, update.message)
        await admin_blacklist_menu(update, context)
        return
    
    elif text == "📊 Статистика" and is_admin:
        from handlers.admin import admin_stats
        mock_query = MockCallbackQuery('admin_stats', user_id, update.message)
        await admin_stats(update, context)
        return
    
    elif text == "⚙️ Настройки" and is_admin:
        from handlers.admin import admin_settings
        mock_query = MockCallbackQuery('admin_settings', user_id, update.message)
        await admin_settings(update, context)
        return
    
    elif text == "◀️ Назад в главное меню" and is_admin:
        await update.message.reply_text(
            "👋 Главное меню:",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
        return
    
    else:
        # Если текст не соответствует ни одной кнопке
        await update.message.reply_text(
            "Используйте кнопки внизу экрана для навигации 👇",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
