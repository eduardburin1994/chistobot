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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    user = update.effective_user
    args = context.args
    
    print(f"🚀 START от пользователя {user.id} (@{user.username})")
    print(f"📎 Аргументы команды: {args}")
    print(f"📎 Тип args: {type(args)}")
    print(f"📎 Длина args: {len(args) if args else 0}")
    
    # Проверяем, есть ли реферальный код в аргументах
    if args and len(args) > 0:
        print(f"🎯 Получен аргумент: {args[0]}")
        
        # Реферальные коды начинаются с CHISTO
        if args[0].startswith('CHISTO'):
            referral_code = args[0]
            print(f"🎯 Найден реферальный код: {referral_code}")
            
            import database as db
            # Сохраняем код в context.user_data для последующего использования
            context.user_data['referral_code'] = referral_code
            print(f"💾 Реферальный код сохранён в context.user_data")
            
            # Пытаемся сразу зарегистрировать реферала
            try:
                referrer_id = db.register_referral(referral_code, user.id)
                if referrer_id:
                    print(f"✅ Пользователь {user.id} пришёл по реферальному коду от {referrer_id}")
                    
                    # Получаем информацию о пригласившем
                    conn = db.get_connection()
                    cur = conn.cursor()
                    cur.execute('SELECT first_name, username FROM users WHERE user_id = %s', (referrer_id,))
                    referrer_info = cur.fetchone()
                    cur.close()
                    conn.close()
                    
                    if referrer_info:
                        referrer_name = referrer_info[0] or referrer_info[1] or f"пользователя {referrer_id}"
                        await update.message.reply_text(
                            f"🎁 Вы перешли по приглашению от <b>{referrer_name}</b>!\n"
                            f"После первого заказа {referrer_name} получит 100 бонусных баллов.",
                            parse_mode='HTML'
                        )
                else:
                    print(f"❌ Не удалось зарегистрировать реферала")
                    if referral_code == context.user_data.get('referral_code'):
                        print(f"⚠️ Возможно, код принадлежит самому пользователю или уже использован")
            except Exception as e:
                print(f"❌ Ошибка при регистрации реферала: {e}")
        else:
            print(f"ℹ️ Аргумент не является реферальным кодом: {args[0]}")
    
    # Добавляем пользователя в базу данных
    import database as db
    try:
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Если есть username, обновляем его
        if user.username:
            db.update_user_username(user.id, user.username)
            
        print(f"✅ Пользователь {user.id} обработан")
    except Exception as e:
        print(f"❌ Ошибка при добавлении пользователя: {e}")
    
    # Получаем информацию о пользователе для проверки статуса
    user_info = db.get_user_by_id(user.id)
    
    # Проверяем, не заблокирован ли пользователь
    if db.is_user_blacklisted(user.id):
        await update.message.reply_text(
            "⛔ Вы заблокированы в этом боте.\n"
            "Если вы считаете, что это ошибка, свяжитесь с поддержкой."
        )
        return ConversationHandler.END
    
    # Приветственное сообщение
    from config import admin_data
    is_admin = user.id in admin_data['admins']
    
    # Проверяем, есть ли у пользователя сохранённые данные
    has_saved_data = user_info and user_info[4]  # есть телефон
    
    if has_saved_data:
        welcome_text = (
            f"👋 С возвращением, {user.first_name}!\n\n"
            f"Я помогу вам быстро и удобно заказать вывоз мусора.\n"
            f"Хотите оформить заказ?"
        )
    else:
        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я бот для заказа вывоза мусора. Работаем в Южном микрорайоне.\n"
            f"Хотите оформить заказ?"
        )
    
    # Клавиатура с вариантами
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, давай!", callback_data='welcome_yes'),
            InlineKeyboardButton("❌ Нет, спасибо", callback_data='welcome_no')
        ]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
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

async def test_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовый хендлер для проверки рефералов"""
    user = update.effective_user
    args = context.args
    
    print(f"🧪 ТЕСТОВЫЙ START от {user.id}")
    print(f"🧪 Аргументы: {args}")
    print(f"🧪 Тип args: {type(args)}")
    print(f"🧪 Длина: {len(args) if args else 0}")
    
    if args:
        for i, arg in enumerate(args):
            print(f"🧪 arg[{i}]: '{arg}' (тип: {type(arg)})")
    
    await update.message.reply_text(f"Тест: получены аргументы: {args}")

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
    