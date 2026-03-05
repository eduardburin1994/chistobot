# handlers/common.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data, user_data
from keyboards.client_keyboards import get_main_keyboard
from constants import WELCOME
from utils.antiflood import antiflood, rate_limiter
import logging

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полноценный обработчик команды /start"""
    user = update.effective_user
    
    # Проверяем, есть ли реферальный код
    args = context.args
    if args and args[0].startswith('ref_'):
        referral_code = args[0].replace('ref_', '')
        # Регистрируем реферала
        referrer_id = db.register_referral(referral_code, user.id)
        if referrer_id:
            await update.message.reply_text(
                "🎉 Вы пришли по приглашению друга!\n"
                "После первого заказа ваш друг получит 100 баллов."
            )
    
    # Проверяем, есть ли пользователь в базе
    user_info = db.get_user_by_id(user.id)
    
    # Если пользователя нет в базе - добавляем
    if not user_info:
        db.add_user(user.id, user.username, user.first_name, user.last_name)
        print(f"✅ Новый пользователь {user.id} добавлен в базу")
        
        welcome_text = (
            f"👋 <b>Добро пожаловать в ЧистоBOT, {user.first_name}!</b>\n\n"
            f"🚶‍♂️ Я помогу вам быстро и удобно <b>избавиться от накопившегося мусора</b> в Твери.\n\n"
            f"📍 <b>Зона обслуживания:</b> <u>Южный микрорайон</u>\n"
            f"Мы работаем на следующих улицах:\n"
            f"• Октябрьский проспект\n"
            f"• Улица Можайского\n"
            f"• Улица Королева\n"
            f"• Улица Левитана\n"
            f"• Бульвар Гусева\n"
            f"• Улица Псковская\n"
            f"• Улица С.Я. Лемешева\n\n"
            f"📝 <b>Нажмите кнопку ниже, чтобы начать работу:</b>"
        )
    else:
        print(f"✅ Существующий пользователь {user.id} вернулся в бота")
        welcome_text = (
            f"👋 <b>С возвращением, {user.first_name}!</b>\n\n"
            f"🚶‍♂️ <b>ЧистоBOT</b> — твой помощник по выносу мусора в Твери!\n"
            f"Курьер заберёт пакеты прямо от твоей двери и донесёт до бака.\n\n"
            f"📍 <b>Зона обслуживания:</b> <u>Южный микрорайон</u>\n\n"
            f"✨ <b>Что я умею:</b>\n"
            f"• 📦 Заказать вынос пакетов с мусором\n"
            f"• 📅 Выбрать удобную дату и время\n"
            f"• 💰 Рассчитать стоимость сразу\n"
            f"• 📋 Посмотреть историю заказов\n"
            f"• 💬 Связаться с поддержкой\n\n"
            f"<b>Ну что, избавимся от мусора без хлопот?</b>"
        )
    
    # Проверка на блокировку
    if user.id in admin_data.get('blocked_users', []):
        await update.message.reply_text("⛔ Вы заблокированы в этом боте.")
        return ConversationHandler.END
    
    # Inline-кнопки для ответа на приветствие
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, давай!", callback_data='welcome_yes'),
            InlineKeyboardButton("🚶 Сам вынесу", callback_data='welcome_no')
        ]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return WELCOME

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rules - показывает правила пользования ботом"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"📋 Пользователь {user_id} запросил правила через команду /rules")
    
    # Проверка на блокировку
    if user_id in admin_data.get('blocked_users', []):
        await update.message.reply_text("⛔ Вы заблокированы в этом боте.")
        return
    
    rules_text = (
        "📋 <b>Правила и условия:</b>\n\n"
        "📍 <b>Зона обслуживания:</b>\n"
        "Мы работаем ТОЛЬКО в Южном микрорайоне Твери на следующих улицах:\n"
        "• Октябрьский проспект\n"
        "• Улица Можайского\n"
        "• Улица Королева\n"
        "• Улица Левитана\n"
        "• Бульвар Гусева\n"
        "• Улица Псковская\n"
        "• Улица С.Я. Лемешева\n\n"
        "1️⃣ <b>Вес:</b> Общий вес всех пакетов не более 15 кг.\n"
        "2️⃣ <b>Отмена:</b> Вы можете отменить заказ за 4 часа до прихода курьера.\n"
        "3️⃣ <b>Время работы:</b> Заявки принимаются с 10:00 до 22:00.\n"
        "4️⃣ <b>Отказ:</b> При превышении веса или адресе вне зоны обслуживания курьер вправе отказаться от выноса.\n"
        "5️⃣ <b>Что можно выносить:</b> Обычные бытовые отходы. Строительный мусор и опасные отходы не принимаются.\n"
        "6️⃣ <b>Как это работает:</b> Курьер забирает пакеты прямо от вашей двери и самостоятельно утилизирует их в ближайшем баке."
    )
    
    from keyboards.client_keyboards import get_main_keyboard
    is_admin = user_id in admin_data['admins']
    keyboard = get_main_keyboard(is_admin)
    
    await update.message.reply_text(
        rules_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def text_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения как команды (русские аналоги)"""
    user_id = update.effective_user.id
    text = update.message.text.lower().strip()
    
    # 👇 ВАЖНО: Проверяем, не находится ли пользователь в процессе заказа
    from config import user_data
    if user_id in user_data and user_data[user_id].get('in_order_process', False):
        # Пользователь в процессе заказа - не мешаем, пропускаем сообщение
        # Оно будет обработано ConversationHandler'ом
        return
    
    # Проверка на блокировку
    if db.is_user_blacklisted(user_id):
        await update.message.reply_text("⛔ Вы заблокированы в этом боте за нарушение правил.")
        return
    
    # Проверка на спам (НЕ ДЛЯ АДМИНОВ)
    from config import admin_data
    
    # Админов не проверяем
    if user_id not in admin_data['admins']:
        is_spam, reason, wait_time = antiflood.is_spam(user_id)
        
        if is_spam:
            if reason == "BANNED":
                await update.message.reply_text(
                    "🚫 Вы автоматически заблокированы за флуд.\n"
                    "Свяжитесь с администратором для разблокировки."
                )
            elif reason == "FLOOD":
                minutes = wait_time // 60
                await update.message.reply_text(
                    f"⚠️ <b>Слишком много сообщений!</b>\n\n"
                    f"Пожалуйста, подождите {minutes} минут перед отправкой следующего сообщения.\n"
                    f"Это защита от спама.",
                    parse_mode='HTML'
                )
            return
    else:
        print(f"👑 Админ {user_id} пишет без ограничений")
    
    # Обработка текстовых "команд"
    if text in ["старт", "меню", "начать", "/старт"]:
        await start(update, context)
    elif text in ["правила", "помощь", "help", "/правила"]:
        await rules_command(update, context)
    elif text in ["админ", "админка", "/админ"]:
        from handlers.admin_access import admin_command_start
        await admin_command_start(update, context)
    elif text in ["курьер", "/курьер"]:
        from handlers.courier_auth import courier_command_start
        await courier_command_start(update, context)
    # else:
    #     # Если сообщение не похоже на команду - показываем меню
    #     from keyboards.client_keyboards import get_main_keyboard
    #     is_admin = user_id in admin_data['admins']
    #     await update.message.reply_text(
    #         "Используйте кнопки внизу экрана для навигации 👇",
    #         reply_markup=get_main_keyboard(is_admin)
    #     )

async def welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на приветствие"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    keyboard = get_main_keyboard(user_id in admin_data['admins'])
    
    if query.data == 'welcome_yes':
        text = "Отлично! 🎉 Давайте начнём. Выберите действие в меню:"
    else:
        text = "Хорошо, если передумаете — я здесь! 😉\n\nВыберите действие в меню:"
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню с показом REPLY-кнопок"""
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    keyboard = get_main_keyboard(query.from_user.id in admin_data['admins'])
    await query.edit_message_text(
        "👋 Главное меню:",
        reply_markup=keyboard
    )
    
    from keyboards.reply_keyboards import get_main_reply_keyboard
    is_admin = query.from_user.id in admin_data['admins']
    await query.message.reply_text(
        "Меню быстрого доступа 👇",
        reply_markup=get_main_reply_keyboard(is_admin)
    )
    return ConversationHandler.END

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать правила"""
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    rules_text = (
        "📋 <b>Правила и условия:</b>\n\n"
        "1️⃣ <b>Вес:</b> Общий вес всех пакетов не более 15 кг.\n"
        "2️⃣ <b>Отмена:</b> Вы можете отменить заказ за 4 часа до прихода курьера.\n"
        "3️⃣ <b>Время работы:</b> Заявки принимаются с 10:00 до 22:00.\n"
        "4️⃣ <b>Отказ:</b> При превышении веса курьер вправе отказаться от выноса.\n"
        "5️⃣ <b>Что можно выносить:</b> Обычные бытовые отходы. Строительный мусор и опасные отходы не принимаются.\n"
        "6️⃣ <b>Как это работает:</b> Курьер забирает пакеты прямо от вашей двери и самостоятельно утилизирует их в ближайшем баке."
    )
    
    keyboard = get_main_keyboard(query.from_user.id in admin_data['admins'])
    
    await query.edit_message_text(
        rules_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расценки"""
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    price_text = (
        "💰 <b>Наши расценки:</b>\n\n"
        f"• 🟢 <b>1 пакет</b> — {admin_data['prices']['1']} ₽\n"
        f"  <i>(курьер заберёт и утилизирует один пакет)</i>\n\n"
        f"• 🟡 <b>2 пакета</b> — {admin_data['prices']['2']} ₽\n"
        f"  <i>(за два пакета, включая вынос)</i>\n\n"
        f"• 🔴 <b>3 и более пакетов</b> — {int(admin_data['prices']['3+'])} ₽\n"
        f"  <i>(фиксированная цена за весь объём)</i>\n\n"
        "⚠️ <b>Важно:</b> Общий вес всех пакетов не должен превышать 15 кг!\n\n"
        "📍 <b>Зона обслуживания:</b> Южный микрорайон (список улиц в разделе Правила)\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• 💵 Наличные курьеру\n"
        "• 💳 Перевод на карту курьера\n"
        "• 💻 Онлайн-оплата — <i>в разработке</i> 🔧"
    )
    
    keyboard = get_main_keyboard(query.from_user.id in admin_data['admins'])
    
    await query.edit_message_text(
        price_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def show_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать контакты"""
    if 'mock_callback_query' in context.bot_data:
        query = context.bot_data['mock_callback_query']
        del context.bot_data['mock_callback_query']
    else:
        query = update.callback_query
    
    await query.answer()
    
    contact_text = (
        "📞 <b>Связаться с нами:</b>\n\n"
        "Выберите способ связи:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать админу", callback_data='support_write')],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
    ]
    
    await query.edit_message_text(
        contact_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик добавления бота в чат или группу"""
    if not update.message.new_chat_members:
        return
    
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat = update.effective_chat
            user = update.effective_user
            
            if user:
                adder_name = user.first_name
                if chat.type == 'private':
                    welcome_text = (
                        f"👋 <b>Привет, {adder_name}!</b>\n\n"
                        f"🚶‍♂️ Я бот для выноса мусора <b>ЧистоBOT</b>\n\n"
                        f"📝 <b>Нажмите /start для запуска бота</b>\n"
                        f"Или просто отправьте команду /start в чат"
                    )
                else:
                    welcome_text = (
                        f"👋 <b>Всем привет!</b>\n\n"
                        f"🚶‍♂️ Я бот для выноса мусора <b>ЧистоBOT</b>\n"
                        f"Меня добавил(а) {adder_name}\n\n"
                        f"📝 <b>Нажмите /start для запуска бота</b>\n"
                        f"Или просто отправьте команду /start в чат"
                    )
            else:
                welcome_text = (
                    f"👋 <b>Всем привет!</b>\n\n"
                    f"🚶‍♂️ Я бот для выноса мусора <b>ЧистоBOT</b>\n\n"
                    f"📝 <b>Нажмите /start для запуска бота</b>"
                )
            
            await update.message.reply_text(welcome_text, parse_mode='HTML')
            
            if user:
                db.add_user(user.id, user.username, user.first_name, user.last_name)
                print(f"✅ Пользователь {user.id} добавлен в базу через добавление бота")
            
            break

# =============== REPLY-ВЕРСИИ ФУНКЦИЙ ===============

async def show_prices_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия show_prices для reply-кнопок"""
    price_text = (
        "💰 <b>Наши расценки:</b>\n\n"
        f"• 🟢 <b>1 пакет</b> — {admin_data['prices']['1']} ₽\n"
        f"  <i>(курьер заберёт и утилизирует один пакет)</i>\n\n"
        f"• 🟡 <b>2 пакета</b> — {admin_data['prices']['2']} ₽\n"
        f"  <i>(за два пакета, включая вынос)</i>\n\n"
        f"• 🔴 <b>3 и более пакетов</b> — {admin_data['prices']['3+']} ₽\n"
        f"  <i>(фиксированная цена за весь объём)</i>\n\n"
        "⚠️ <b>Важно:</b> Общий вес всех пакетов не должен превышать 15 кг!\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• 💵 Наличные курьеру\n"
        "• 💳 Перевод на карту курьера\n"
        "• 💻 Онлайн-оплата — <i>в разработке</i> 🔧"
    )
    
    keyboard = get_main_keyboard(update.effective_user.id in admin_data['admins'])
    await update.message.reply_text(price_text, parse_mode='HTML', reply_markup=keyboard)

async def show_rules_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия show_rules для reply-кнопок"""
    rules_text = (
        "📋 <b>Правила и условия:</b>\n\n"
        "1️⃣ <b>Вес:</b> Общий вес всех пакетов не более 15 кг.\n"
        "2️⃣ <b>Отмена:</b> Вы можете отменить заказ за 4 часа до прихода курьера.\n"
        "3️⃣ <b>Время работы:</b> Заявки принимаются с 10:00 до 22:00.\n"
        "4️⃣ <b>Отказ:</b> При превышении веса курьер вправе отказаться от выноса.\n"
        "5️⃣ <b>Что можно выносить:</b> Обычные бытовые отходы. Строительный мусор и опасные отходы не принимаются.\n"
        "6️⃣ <b>Как это работает:</b> Курьер забирает пакеты прямо от вашей двери и самостоятельно утилизирует их в ближайшем баке."
    )
    
    keyboard = get_main_keyboard(update.effective_user.id in admin_data['admins'])
    await update.message.reply_text(rules_text, parse_mode='HTML', reply_markup=keyboard)

async def show_contact_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия show_contact для reply-кнопок"""
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
        reply_markup=InlineKeyboardMarkup(keyboard)
    )