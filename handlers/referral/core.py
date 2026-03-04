# handlers/referral/core.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from config import admin_data
import datetime

async def referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает реферальную информацию пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Получаем или создаём реферальный код
    code = db.get_or_create_referral_code(user_id)
    
    # Получаем статистику
    stats = db.get_referral_stats(user_id)
    
    # Создаём ссылку
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{code}"
    
    # Формируем текст
    text = (
        "🎁 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА</b>\n\n"
        "Приглашай друзей и получай баллы!\n\n"
        "📊 <b>Твоя статистика:</b>\n"
        f"• 👥 Рефералов 1 уровня: {stats['level1'] if stats else 0}\n"
        f"• 👥 Рефералов 2 уровня: {stats['level2'] if stats else 0}\n"
        f"• 💰 Текущий баланс: <b>{stats['balance'] if stats else 0} баллов</b>\n"
        f"• 🏆 Всего заработано: {stats['total_earned'] if stats else 0} баллов\n\n"
        "🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        "📋 <b>Как это работает:</b>\n"
        "1️⃣ Друг переходит по ссылке и регистрируется\n"
        "2️⃣ Когда друг делает первый заказ — ты получаешь <b>100 баллов</b>\n"
        "3️⃣ Если друг тоже приглашает кого-то — ты получаешь <b>30 баллов</b> за реферала 2 уровня\n"
        "4️⃣ 300 баллов = <b>бесплатный вывоз</b>!\n"
        "5️⃣ Баллы можно использовать как скидку (1 балл = 1 рубль)\n\n"
        "👇 <b>Нажми на ссылку, чтобы скопировать</b>"
    )
    
    # Клавиатура
    from handlers.referral.keyboard import get_referral_keyboard
    keyboard = get_referral_keyboard()
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

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
