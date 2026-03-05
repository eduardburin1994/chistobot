# handlers/referral/core.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
import datetime

async def referral_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущий баланс баллов"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT referral_balance FROM users WHERE user_id = %s', (user_id,))
        balance = cur.fetchone()[0]
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        balance = 0
    finally:
        cur.close()
        conn.close()
    
    text = (
        f"💰 <b>Ваш бонусный баланс</b>\n\n"
        f"🎁 У вас <b>{balance} баллов</b>\n"
        f"1 балл = 1 рубль скидки\n\n"
        f"💡 Баллы можно использовать при оформлении заказа!"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='referral_info')]]
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает реферальную информацию пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    print(f"🎁 referral_info для пользователя {user_id}")
    
    import database as db
    
    # ПРИНУДИТЕЛЬНО создаём или получаем реферальный код
    print(f"🔑 Получаем/создаём реферальный код для {user_id}")
    referral_code = db.get_or_create_referral_code(user_id)
    
    if not referral_code:
        print(f"❌ Не удалось создать реферальный код для {user_id}")
        await query.edit_message_text(
            "❌ Не удалось создать реферальный код. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')
            ]])
        )
        return
    
    print(f"✅ Реферальный код: {referral_code}")
    
    # Получаем статистику
    print(f"📊 Получаем статистику для {user_id}")
    stats = db.get_referral_stats(user_id)
    
    if not stats:
        print(f"📊 Статистика не найдена, создаём базовую")
        stats = {
            'code': referral_code,
            'balance': 0,
            'total_earned': 0,
            'level1': 0,
            'level2': 0,
            'recent': [],
            'earnings': []
        }
    else:
        print(f"📊 Статистика получена: баланс={stats['balance']}, level1={stats['level1']}")
    
    # Формируем реферальную ссылку
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    print(f"🔗 Ссылка: {referral_link}")
    
    # Текст сообщения
    text = (
        "🎁 <b>Реферальная программа</b>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"💰 <b>Ваш баланс:</b> {stats['balance']} баллов\n"
        f"📊 <b>Всего заработано:</b> {stats['total_earned']} баллов\n"
        f"👥 <b>Приглашено друзей:</b> {stats['level1']}\n"
        f"👥 <b>Рефералы 2 уровня:</b> {stats['level2']}\n\n"
        f"❓ <b>Как это работает?</b>\n"
        f"• За друга (1 уровень) — 100 баллов\n"
        f"• За друга друга (2 уровень) — 30 баллов\n"
        f"• 300 баллов = бесплатный вывоз\n"
        f"• Баллы можно использовать как скидку"
    )
    
    # Добавляем информацию о последних рефералах, если есть
    if stats.get('recent') and len(stats['recent']) > 0:
        text += "\n\n📋 <b>Последние приглашённые:</b>\n"
        for ref in stats['recent'][:3]:
            name = ref[0] or f"@{ref[1]}" if ref[1] else "Пользователь"
            date = ref[2].strftime("%d.%m.%Y") if ref[2] else "недавно"
            rewarded = "✅" if ref[3] else "⏳"
            text += f"{rewarded} {name} — {date}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📊 История", callback_data='referral_history'),
            InlineKeyboardButton("🏆 Топ", callback_data='referral_top')
        ],
        [InlineKeyboardButton("❓ Подробнее", callback_data='referral_help')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        print(f"✅ Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")
        await query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def referral_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю рефералов и начислений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    stats = db.get_referral_stats(user_id)
    
    if not stats:
        await query.edit_message_text(
            "❌ Не удалось загрузить статистику",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data='referral_info')
            ]])
        )
        return
    
    text = "📋 <b>ИСТОРИЯ РЕФЕРАЛОВ</b>\n\n"
    
    if stats['recent']:
        text += "<b>Последние приглашённые:</b>\n"
        for ref in stats['recent']:
            name = ref[0] or ref[1] or "Пользователь"
            date = ref[2].strftime("%d.%m.%Y") if ref[2] else "неизвестно"
            status = "✅ Активирован" if ref[3] else "⏳ Ожидает заказа"
            text += f"• {name} — {date} — {status}\n"
        text += "\n"
    
    if stats['earnings']:
        text += "<b>Последние начисления:</b>\n"
        for earn in stats['earnings'][:5]:
            amount = earn[0]
            source = "за реферала 1 ур." if earn[1] == 'level1' else "за реферала 2 ур." if earn[1] == 'level2' else earn[1]
            date = earn[2].strftime("%d.%m.%Y") if earn[2] else ""
            text += f"• +{amount} баллов — {source} — {date}\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data='referral_info')]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
