# handlers/reply_handlers.py
from telegram import Update
from telegram.ext import ContextTypes
from config import admin_data
from keyboards.reply_keyboards import get_main_reply_keyboard, get_admin_reply_keyboard

async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка нажатий на reply-кнопки - УПРОЩЁННАЯ ВЕРСИЯ
    """
    text = update.message.text
    user_id = update.effective_user.id
    is_admin = user_id in admin_data['admins']
    
    print(f"🔘 Нажата reply-кнопка: {text}")
    
    # =============== ГЛАВНОЕ МЕНЮ ===============
    if text == "📦 Заказать вынос":
        from handlers.client import start_order_reply
        await start_order_reply(update, context)
        return
    
    elif text == "💰 Цены":
        from handlers.common import show_prices_reply
        await show_prices_reply(update, context)
        return
    
    elif text == "📋 Мои заказы":
        from handlers.client import my_orders_detail_reply
        await my_orders_detail_reply(update, context)
        return
    
    elif text == "⭐ Избранное":
        from handlers.client import favorite_addresses_menu_reply
        await favorite_addresses_menu_reply(update, context)
        return
    
    elif text == "📞 Связаться с нами":
        from handlers.common import show_contact_reply
        await show_contact_reply(update, context)
        return
    
    elif text == "📋 Правила":
        from handlers.common import show_rules_reply
        await show_rules_reply(update, context)
        return
    
    # =============== АДМИН-МЕНЮ ===============
    elif text == "👑 Админ-панель" and is_admin:
        from handlers.admin import admin_panel_reply
        await admin_panel_reply(update, context)
        # Меняем клавиатуру на админскую
        await update.message.reply_text(
            "👑 Вы в админ-панели. Используйте кнопки ниже:",
            reply_markup=get_admin_reply_keyboard()
        )
        return
    
    elif text == "📦 Заказы" and is_admin:
        from handlers.admin import admin_orders_reply
        await admin_orders_reply(update, context)
        return
    
    elif text == "👥 Клиенты" and is_admin:
        from handlers.admin import admin_clients_reply
        await admin_clients_reply(update, context)
        return
    
    elif text == "💰 Цены" and is_admin:
        from handlers.admin import admin_prices_menu_reply
        await admin_prices_menu_reply(update, context)
        return
    
    elif text == "⏰ Время работы" and is_admin:
        from handlers.admin import admin_working_hours_reply
        await admin_working_hours_reply(update, context)
        return
    
    elif text == "📢 Рассылка" and is_admin:
        from handlers.admin import admin_broadcast_reply
        await admin_broadcast_reply(update, context)
        return
    
    elif text == "🚫 Черный список" and is_admin:
        from handlers.admin import admin_blacklist_menu_reply
        await admin_blacklist_menu_reply(update, context)
        return
    
    elif text == "📊 Статистика" and is_admin:
        from handlers.admin import admin_stats_reply
        await admin_stats_reply(update, context)
        return
    
    elif text == "⚙️ Настройки" and is_admin:
        from handlers.admin import admin_settings_reply
        await admin_settings_reply(update, context)
        return
    
    elif text == "◀️ Назад в главное меню" and is_admin:
        await update.message.reply_text(
            "👋 Главное меню:",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
        return
    
    else:
        await update.message.reply_text(
            "Используйте кнопки внизу экрана для навигации 👇",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
