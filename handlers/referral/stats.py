# handlers/referral/stats.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

async def referral_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ пригласивших"""
    query = update.callback_query
    await query.answer()
    
    conn = db.get_connection()
    cur = conn.cursor()
    
    try:
        # Топ за всё время
        cur.execute('''
            SELECT 
                u.first_name,
                u.username,
                u.total_earned,
                u.level1_count
            FROM users u
            WHERE u.total_earned > 0
            ORDER BY u.total_earned DESC
            LIMIT 10
        ''')
        
        top_all = cur.fetchall()
        
        # Топ за месяц
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        cur.execute('''
            SELECT 
                u.first_name,
                u.username,
                SUM(e.amount) as month_earned
            FROM referral_earnings e
            JOIN users u ON e.user_id = u.user_id
            WHERE e.created_at > %s
            GROUP BY u.user_id, u.first_name, u.username
            ORDER BY month_earned DESC
            LIMIT 10
        ''', (month_ago,))
        
        top_month = cur.fetchall()
        
        text = "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n\n"
        
        text += "<b>🏅 За всё время:</b>\n"
        for i, user in enumerate(top_all, 1):
            name = user[0] or f"@{user[1]}" if user[1] else f"ID {user[0]}"
            text += f"{i}. {name} — {user[2]} баллов ({user[3]} реф.)\n"
        
        text += "\n<b>📅 За месяц:</b>\n"
        for i, user in enumerate(top_month, 1):
            name = user[0] or f"@{user[1]}" if user[1] else f"ID {user[0]}"
            text += f"{i}. {name} — {user[2]} баллов\n"
        
    except Exception as e:
        text = "❌ Ошибка загрузки топа"
        print(f"Ошибка: {e}")
    finally:
        cur.close()
        conn.close()
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='referral_info')]]
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
