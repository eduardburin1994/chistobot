# database.py
import os
import datetime
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

# =============== РЕФЕРАЛЬНАЯ СИСТЕМА ===============

import random
import string

def init_referral_tables():
    """Создаёт таблицы для реферальной системы"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Добавляем поля в таблицу users
        cur.execute('''
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS referral_code TEXT UNIQUE,
            ADD COLUMN IF NOT EXISTS referred_by BIGINT,
            ADD COLUMN IF NOT EXISTS referral_balance INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_earned INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS level1_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS level2_count INTEGER DEFAULT 0
        ''')
        
        # Таблица реферальных связей
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id SERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT UNIQUE,
                level INTEGER DEFAULT 1,
                created_at TIMESTAMP,
                first_order_id INTEGER,
                rewarded BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id),
                FOREIGN KEY (first_order_id) REFERENCES orders (order_id)
            )
        ''')
        
        # Таблица начислений баллов
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referral_earnings (
                earning_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                source TEXT, -- 'level1', 'level2', 'bonus'
                source_id INTEGER, -- ID реферала или заказа
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица использования баллов
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referral_spendings (
                spending_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                order_id INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (order_id) REFERENCES orders (order_id)
            )
        ''')
        
        conn.commit()
        print("✅ Таблицы реферальной системы созданы")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц рефералки: {e}")
    finally:
        cur.close()
        conn.close()

def generate_referral_code(user_id):
    """Генерирует уникальный реферальный код"""
    # Формат: CHISTO + первые 4 буквы имени + случайные цифры
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Получаем имя пользователя
        cur.execute('SELECT first_name FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        name_part = user[0][:4].upper() if user and user[0] else "USER"
        
        # Генерируем уникальный код
        while True:
            random_part = ''.join(random.choices(string.digits, k=4))
            code = f"CHISTO{name_part}{random_part}"
            
            # Проверяем уникальность
            cur.execute('SELECT user_id FROM users WHERE referral_code = %s', (code,))
            if not cur.fetchone():
                return code
    except Exception as e:
        print(f"❌ Ошибка генерации кода: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_or_create_referral_code(user_id):
    """Получает существующий или создаёт новый реферальный код"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Проверяем, есть ли уже код
        cur.execute('SELECT referral_code FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result and result[0]:
            return result[0]
        
        # Создаём новый код
        code = generate_referral_code(user_id)
        if code:
            cur.execute(
                'UPDATE users SET referral_code = %s WHERE user_id = %s',
                (code, user_id)
            )
            conn.commit()
            return code
        return None
    except Exception as e:
        print(f"❌ Ошибка получения кода: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def register_referral(referral_code, new_user_id):
    """Регистрирует нового пользователя по реферальному коду"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Находим, кто пригласил
        cur.execute(
            'SELECT user_id FROM users WHERE referral_code = %s',
            (referral_code,)
        )
        referrer = cur.fetchone()
        
        if not referrer:
            return None
        
        referrer_id = referrer[0]
        
        # Не даём регистрировать самого себя
        if referrer_id == new_user_id:
            return None
        
        # Проверяем, не зарегистрирован ли уже этот пользователь
        cur.execute(
            'SELECT * FROM referrals WHERE referred_id = %s',
            (new_user_id,)
        )
        if cur.fetchone():
            return None
        
        # Регистрируем реферала 1 уровня
        cur.execute('''
            INSERT INTO referrals (referrer_id, referred_id, level, created_at)
            VALUES (%s, %s, 1, %s)
            RETURNING referral_id
        ''', (referrer_id, new_user_id, datetime.datetime.now()))
        
        referral_id = cur.fetchone()[0]
        
        # Обновляем счётчик у пригласившего
        cur.execute('''
            UPDATE users 
            SET level1_count = level1_count + 1 
            WHERE user_id = %s
        ''', (referrer_id,))
        
        # Записываем, кто пригласил нового пользователя
        cur.execute(
            'UPDATE users SET referred_by = %s WHERE user_id = %s',
            (referrer_id, new_user_id)
        )
        
        conn.commit()
        print(f"✅ Пользователь {new_user_id} пришёл по реферальному коду от {referrer_id}")
        return referrer_id
        
    except Exception as e:
        print(f"❌ Ошибка регистрации реферала: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def process_referral_reward(referrer_id, friend_id, order_id):
    """Начисляет баллы за успешный заказ друга"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Проверяем, не начисляли ли уже баллы за этого друга
        cur.execute('''
            SELECT * FROM referrals 
            WHERE referred_id = %s AND rewarded = TRUE
        ''', (friend_id,))
        
        if cur.fetchone():
            return
        
        # Начисляем баллы за реферала 1 уровня
        cur.execute('''
            UPDATE users 
            SET referral_balance = referral_balance + 100,
                total_earned = total_earned + 100
            WHERE user_id = %s
            RETURNING referral_balance
        ''', (referrer_id,))
        
        new_balance = cur.fetchone()[0]
        
        # Записываем в историю начислений
        cur.execute('''
            INSERT INTO referral_earnings (user_id, amount, source, source_id, created_at)
            VALUES (%s, 100, 'level1', %s, %s)
        ''', (referrer_id, friend_id, datetime.datetime.now()))
        
        # Отмечаем реферала как награждённого
        cur.execute('''
            UPDATE referrals 
            SET rewarded = TRUE, first_order_id = %s 
            WHERE referred_id = %s
        ''', (order_id, friend_id))
        
        # Проверяем, не был ли пригласивший сам чьим-то рефералом (level 2)
        cur.execute('SELECT referred_by FROM users WHERE user_id = %s', (referrer_id,))
        level2_referrer = cur.fetchone()
        
        if level2_referrer and level2_referrer[0]:
            level2_id = level2_referrer[0]
            
            # Начисляем баллы за реферала 2 уровня
            cur.execute('''
                UPDATE users 
                SET referral_balance = referral_balance + 30,
                    total_earned = total_earned + 30,
                    level2_count = level2_count + 1
                WHERE user_id = %s
            ''', (level2_id,))
            
            # Записываем в историю
            cur.execute('''
                INSERT INTO referral_earnings (user_id, amount, source, source_id, created_at)
                VALUES (%s, 30, 'level2', %s, %s)
            ''', (level2_id, friend_id, datetime.datetime.now()))
            
            print(f"✅ Пользователь {level2_id} получил 30 баллов за реферала 2 уровня")
        
        conn.commit()
        print(f"✅ Пользователь {referrer_id} получил 100 баллов за реферала {friend_id}")
        print(f"💰 Новый баланс: {new_balance} баллов")
        
    except Exception as e:
        print(f"❌ Ошибка начисления баллов: {e}")
    finally:
        cur.close()
        conn.close()

def get_referral_stats(user_id):
    """Получает статистику реферальной программы для пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT 
                referral_code,
                referral_balance,
                total_earned,
                level1_count,
                level2_count
            FROM users WHERE user_id = %s
        ''', (user_id,))
        
        user_stats = cur.fetchone()
        if not user_stats:
            return None
        
        # Получаем последних 5 рефералов
        cur.execute('''
            SELECT 
                u.first_name,
                u.username,
                r.created_at,
                r.rewarded
            FROM referrals r
            JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = %s
            ORDER BY r.created_at DESC
            LIMIT 5
        ''', (user_id,))
        
        recent = cur.fetchall()
        
        # Получаем историю начислений
        cur.execute('''
            SELECT amount, source, created_at
            FROM referral_earnings
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        ''', (user_id,))
        
        earnings = cur.fetchall()
        
        return {
            'code': user_stats[0],
            'balance': user_stats[1],
            'total_earned': user_stats[2],
            'level1': user_stats[3],
            'level2': user_stats[4],
            'recent': recent,
            'earnings': earnings
        }
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def use_balance_for_order(user_id, order_id, amount):
    """Списывает баллы при оплате заказа"""
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        # Проверяем баланс
        cur.execute('SELECT referral_balance FROM users WHERE user_id = %s', (user_id,))
        balance = cur.fetchone()[0]
        
        if balance < amount:
            return False
        
        # Списываем баллы
        cur.execute('''
            UPDATE users 
            SET referral_balance = referral_balance - %s 
            WHERE user_id = %s
        ''', (amount, user_id))
        
        # Записываем трату
        cur.execute('''
            INSERT INTO referral_spendings (user_id, amount, order_id, created_at)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, amount, order_id, datetime.datetime.now()))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка списания баллов: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# Получаем строку подключения из переменной окружения
DATABASE_URL = os.environ.get('DATABASE_URL')

def save_prices(prices):
    """Сохраняет цены в БД"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Создаём таблицу для цен, если её нет
        cur.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY DEFAULT 1,
                price_1 INTEGER,
                price_2 INTEGER,
                price_3 TEXT
            )
        ''')
        
        # Вставляем или обновляем цены
        cur.execute('''
            INSERT INTO prices (id, price_1, price_2, price_3)
            VALUES (1, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE 
            SET price_1 = EXCLUDED.price_1,
                price_2 = EXCLUDED.price_2,
                price_3 = EXCLUDED.price_3
        ''', (prices['1'], prices['2'], prices['3+']))
        
        conn.commit()
        print("✅ Цены сохранены в БД")
    except Exception as e:
        print(f"❌ Ошибка сохранения цен: {e}")
    finally:
        cur.close()
        conn.close()

def load_prices():
    """Загружает цены из БД"""
    conn = get_connection()
    if not conn:
        return {'1': 100, '2': 140, '3+': 150}
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT price_1, price_2, price_3 FROM prices WHERE id = 1')
        result = cur.fetchone()
        
        if result:
            return {
                '1': result[0],
                '2': result[1],
                '3+': result[2]  # ← ПРОВЕРЬ ЭТО ЗНАЧЕНИЕ
            }
        else:
            return {'1': 100, '2': 140, '3+': 150}
    except Exception as e:
        print(f"❌ Ошибка загрузки цен: {e}")
        return {'1': 100, '2': 140, '3+': 150}
    finally:
        cur.close()
        conn.close()


def delete_all_user_messages(user_id):
    """Помечает все сообщения пользователя как удалённые"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE messages SET status = 'deleted' WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()
        print(f"✅ Все сообщения пользователя {user_id} помечены как удалённые")
    except Exception as e:
        print(f"❌ Ошибка удаления сообщений: {e}")
    finally:
        cur.close()
        conn.close()

def check_messages_exists(user_id):
    """Проверяет, есть ли сообщения для пользователя"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Проверяем все сообщения без условий
        cur.execute("SELECT COUNT(*) FROM messages WHERE user_id = %s", (user_id,))
        count = cur.fetchone()[0]
        print(f"🔍 Всего сообщений для user {user_id}: {count}")
        
        if count > 0:
            # Покажем первые несколько
            cur.execute("SELECT * FROM messages WHERE user_id = %s LIMIT 3", (user_id,))
            rows = cur.fetchall()
            for row in rows:
                print(f"🔍 Сообщение: {row}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        cur.close()
        conn.close()

def debug_messages_table():
    """Выводит структуру таблицы messages"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Получаем список колонок
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'messages' ORDER BY ordinal_position")
        columns = cur.fetchall()
        print("📋 СТРУКТУРА ТАБЛИЦЫ messages:")
        for i, col in enumerate(columns):
            print(f"   {i}: {col[0]} ({col[1]})")
        
        # Проверяем, есть ли данные
        cur.execute("SELECT COUNT(*) FROM messages")
        count = cur.fetchone()[0]
        print(f"📊 Всего записей: {count}")
        
        if count > 0:
            cur.execute("SELECT * FROM messages LIMIT 1")
            sample = cur.fetchone()
            print(f"🔍 Пример записи: {sample}")
            print(f"🔍 Длина кортежа: {len(sample)}")
    except Exception as e:
        print(f"❌ Ошибка при отладке: {e}")
    finally:
        cur.close()
        conn.close()

def reset_messages_table():
    """Удаляет и пересоздаёт таблицу messages"""
    conn = get_connection()
    if not conn:
        print("❌ Нет подключения к БД")
        return
    
    cur = conn.cursor()
    try:
        # Удаляем существующую таблицу
        cur.execute('DROP TABLE IF EXISTS messages CASCADE')
        print("✅ Таблица messages удалена")
        
        # Создаём новую с правильной структурой
        cur.execute('''
            CREATE TABLE messages (
                message_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                user_message TEXT,
                admin_reply TEXT,
                status TEXT DEFAULT 'new',
                is_important BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP,
                replied_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        print("✅ Таблица messages создана заново")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка при сбросе таблицы: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def check_database_integrity():
    """Проверка целостности базы данных"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        # Проверяем все текстовые поля на наличие битых символов
        tables = ['users', 'orders', 'messages', 'favorite_addresses']
        for table in tables:
            cur.execute(f"SELECT * FROM {table} LIMIT 1")
            print(f"✅ Таблица {table} доступна")
    except Exception as e:
        print(f"❌ Ошибка при проверке таблицы {table}: {e}")
    finally:
        cur.close()
        conn.close()
        
def get_connection():
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден!")
        return None
    try:
        # Добавьте таймаут и обработку ошибок
        conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None
        
def delete_order(order_id):
    """Удаление заказа из базы данных"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        cur.execute('DELETE FROM orders WHERE order_id = %s', (order_id,))
        conn.commit()
        print(f"✅ Заказ #{order_id} удалён из базы данных")
    except Exception as e:
        print(f"❌ Ошибка удаления заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def init_db():
    """Создание таблиц в базе данных PostgreSQL"""
    conn = get_connection()
    if not conn:
        print("❌ Не удалось подключиться к БД для инициализации")
        return
    
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            street_address TEXT,
            entrance TEXT,
            floor TEXT,
            apartment TEXT,
            intercom TEXT,
            registered_date TIMESTAMP
        )
    ''')
    
    # Таблица сообщений
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id SERIAL PRIMARY KEY,
            user_id BIGINT,
            user_message TEXT,
            admin_reply TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            replied_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица заказов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id SERIAL PRIMARY KEY,
            user_id BIGINT,
            client_name TEXT,
            phone TEXT,
            street_address TEXT,
            entrance TEXT,
            floor TEXT,
            apartment TEXT,
            intercom TEXT,
            order_date TEXT,
            order_time TEXT,
            bags_count INTEGER,
            price INTEGER,
            payment_method TEXT DEFAULT 'cash',
            payment_status TEXT DEFAULT 'pending',
            payment_id TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица занятых слотов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS busy_slots (
            slot_id SERIAL PRIMARY KEY,
            slot_date TEXT,
            slot_time TEXT,
            order_id INTEGER UNIQUE,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    ''')
    
    # Таблица черного списка
    cur.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id BIGINT PRIMARY KEY,
            reason TEXT,
            added_date TIMESTAMP,
            added_by BIGINT
        )
    ''')
    
    # Таблица рассылок
    cur.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            broadcast_id SERIAL PRIMARY KEY,
            admin_id BIGINT,
            message_text TEXT,
            sent_date TIMESTAMP,
            recipients_count INTEGER
        )
    ''')
    
    # Таблица избранных адресов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS favorite_addresses (
            address_id SERIAL PRIMARY KEY,
            user_id BIGINT,
            address_name TEXT,
            street_address TEXT,
            entrance TEXT,
            floor TEXT,
            apartment TEXT,
            intercom TEXT,
            created_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Индекс для быстрого поиска по дате и времени
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_busy_slots_datetime 
        ON busy_slots (slot_date, slot_time)
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Таблицы PostgreSQL созданы или уже существуют")

# =============== ФУНКЦИИ ДЛЯ РАБОТЫ СО СЛОТАМИ И ВРЕМЕНЕМ ===============

def parse_time_slot(slot_time):
    """Парсит временной слот и возвращает время начала и конца"""
    start_str, end_str = slot_time.split('-')
    start_hour, start_minute = map(int, start_str.split(':'))
    end_hour, end_minute = map(int, end_str.split(':'))
    return (start_hour, start_minute), (end_hour, end_minute)

def is_within_working_hours(slot_time):
    """Проверяет, находится ли слот в рабочем времени"""
    from config import WORK_HOURS
    
    try:
        # Берём начало слота
        start_time_str = slot_time.split('-')[0]
        start_hour = int(start_time_str.split(':')[0])
        
        # Проверяем, что час начала в пределах рабочего времени
        return WORK_HOURS['start'] <= start_hour < WORK_HOURS['end']
    except Exception as e:
        print(f"❌ Ошибка проверки рабочего времени: {e}")
        return False

def is_slot_expired(slot_date, slot_time):
    """
    Проверяет, истёк ли слот.
    Слот считается истекшим, если текущее время > начало слота + 1 час 15 минут
    """
    try:
        now = datetime.datetime.now()
        
        # Парсим дату слота
        day, month, year = map(int, slot_date.split('.'))
        slot_datetime = datetime.datetime(year, month, day)
        
        # Парсим время начала слота
        start_time_str = slot_time.split('-')[0]
        start_hour, start_minute = map(int, start_time_str.split(':'))
        
        # Устанавливаем время начала слота
        slot_start = slot_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        
        # Добавляем 1 час 15 минут к началу слота
        expiry_time = slot_start + datetime.timedelta(hours=1, minutes=15)
        
        # Если текущее время больше expiry_time, слот истёк
        return now > expiry_time
    except Exception as e:
        print(f"❌ Ошибка при проверке истечения слота: {e}")
        return True  # В случае ошибки считаем слот истёкшим для безопасности

def get_available_slots(date):
    """
    Возвращает список доступных слотов для указанной даты
    с учётом истекших слотов и рабочего времени
    """
    from constants import TIME_SLOTS
    
    conn = get_connection()
    if not conn:
        return [], {}
    
    cur = conn.cursor()
    available_slots = []
    slot_info = {}
    
    try:
        for slot in TIME_SLOTS:
            # Проверяем рабочие часы
            if not is_within_working_hours(slot):
                continue
            
            # Проверяем, истёк ли слот
            if is_slot_expired(date, slot):
                continue  # Пропускаем истекшие слоты
            
            # Получаем количество занятых мест
            cur.execute(
                'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
                (date, slot)
            )
            count = cur.fetchone()[0]
            free_places = 3 - count
            
            if free_places > 0:
                available_slots.append(slot)
                slot_info[slot] = free_places
        
        return available_slots, slot_info
    except Exception as e:
        print(f"❌ Ошибка получения доступных слотов: {e}")
        return [], {}
    finally:
        cur.close()
        conn.close()

def is_time_slot_free(date, time_slot):
    """Проверка, свободен ли временной слот (максимум 3 заказа)"""
    # Сначала проверяем рабочие часы
    if not is_within_working_hours(time_slot):
        return False
    
    # Проверяем, не истёк ли слот
    if is_slot_expired(date, time_slot):
        return False
    
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        cur.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
            (date, time_slot)
        )
        count = cur.fetchone()[0]
        return count < 3
    except Exception as e:
        print(f"❌ Ошибка проверки слота: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_slot_availability(date, time_slot):
    """Получить количество свободных мест на конкретное время"""
    # Если слот вне рабочего времени или истёк, возвращаем 0
    if not is_within_working_hours(time_slot) or is_slot_expired(date, time_slot):
        return 0
    
    conn = get_connection()
    if not conn:
        return 0
    
    cur = conn.cursor()
    try:
        cur.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
            (date, time_slot)
        )
        count = cur.fetchone()[0]
        return 3 - count
    except Exception as e:
        print(f"❌ Ошибка получения доступности слота: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===============

def get_user_by_id(user_id):
    """Получение информации о пользователе по ID"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT user_id, username, first_name, last_name, phone, street_address, 
                   entrance, floor, apartment, intercom, registered_date 
            FROM users WHERE user_id = %s
        ''', (user_id,))
        user = cur.fetchone()
        return user
    except Exception as e:
        print(f"❌ Ошибка получения пользователя {user_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def add_user(user_id, username, first_name, last_name):
    """Добавление нового пользователя"""
    conn = get_connection()
    if not conn:
        print(f"❌ Не удалось подключиться к БД для добавления пользователя {user_id}")
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, registered_date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, username, first_name, last_name, datetime.datetime.now()))
        conn.commit()
        print(f"✅ Пользователь {user_id} добавлен в БД")
    except Exception as e:
        print(f"❌ Ошибка добавления пользователя {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

def update_user_username(user_id, username):
    """Обновление username пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET username = %s WHERE user_id = %s', (username, user_id))
        conn.commit()
        print(f"✅ Username пользователя {user_id} обновлён на @{username}")
    except Exception as e:
        print(f"❌ Ошибка обновления username {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

def update_user_phone(user_id, phone):
    """Обновление телефона пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET phone = %s WHERE user_id = %s', (phone, user_id))
        conn.commit()
        print(f"✅ Телефон пользователя {user_id} обновлён")
    except Exception as e:
        print(f"❌ Ошибка обновления телефона {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

def save_user_details(user_id, phone, street_address, entrance, floor, apartment, intercom):
    """Сохранение всех данных пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE users 
            SET phone = %s, street_address = %s, entrance = %s, floor = %s, apartment = %s, intercom = %s
            WHERE user_id = %s
        ''', (phone, street_address, entrance, floor, apartment, intercom, user_id))
        conn.commit()
        print(f"✅ Данные пользователя {user_id} сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения данных {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

def update_user_address(user_id, street_address, entrance, floor, apartment, intercom):
    """Обновление адреса пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE users 
            SET street_address = %s, entrance = %s, floor = %s, apartment = %s, intercom = %s
            WHERE user_id = %s
        ''', (street_address, entrance, floor, apartment, intercom, user_id))
        conn.commit()
        print(f"✅ Адрес пользователя {user_id} обновлён")
    except Exception as e:
        print(f"❌ Ошибка обновления адреса {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

def get_username_by_id(user_id):
    """Получение username по ID"""
    conn = get_connection()
    if not conn:
        return "неизвестно"
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT username FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        return result[0] if result else "неизвестно"
    except Exception as e:
        print(f"❌ Ошибка получения username {user_id}: {e}")
        return "неизвестно"
    finally:
        cur.close()
        conn.close()

def get_all_users():
    """Получение всех пользователей"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT user_id, username, first_name, last_name, phone, street_address, 
                   entrance, floor, apartment, intercom, registered_date 
            FROM users ORDER BY registered_date DESC
        ''')
        users = cur.fetchall()
        return users
    except Exception as e:
        print(f"❌ Ошибка получения всех пользователей: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ ИЗБРАННЫХ АДРЕСОВ ===============

def get_user_favorite_addresses(user_id):
    """Получение всех избранных адресов пользователя"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT address_id, address_name, street_address, entrance, floor, apartment, intercom, created_date
            FROM favorite_addresses WHERE user_id = %s ORDER BY created_date DESC
        ''', (user_id,))
        addresses = cur.fetchall()
        return addresses
    except Exception as e:
        print(f"❌ Ошибка получения избранных адресов {user_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_favorite_address(address_id):
    """Получение конкретного избранного адреса"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT address_id, user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date
            FROM favorite_addresses WHERE address_id = %s
        ''', (address_id,))
        address = cur.fetchone()
        return address
    except Exception as e:
        print(f"❌ Ошибка получения адреса {address_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def save_favorite_address(user_id, address_name, street_address, entrance, floor, apartment, intercom):
    """Сохранение избранного адреса"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO favorite_addresses 
            (user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING address_id
        ''', (user_id, address_name, street_address, entrance, floor, apartment, intercom, datetime.datetime.now()))
        address_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Избранный адрес #{address_id} сохранён для пользователя {user_id}")
        return address_id
    except Exception as e:
        print(f"❌ Ошибка сохранения избранного адреса: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def delete_favorite_address(address_id):
    """Удаление избранного адреса"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM favorite_addresses WHERE address_id = %s', (address_id,))
        conn.commit()
        print(f"✅ Избранный адрес #{address_id} удалён")
    except Exception as e:
        print(f"❌ Ошибка удаления адреса {address_id}: {e}")
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ ЗАКАЗОВ ===============

def get_user_orders(user_id):
    """Получение заказов пользователя"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT order_id, user_id, client_name, phone, street_address, 
                   entrance, floor, apartment, intercom, order_date, order_time, 
                   bags_count, price, status, created_at 
            FROM orders WHERE user_id = %s ORDER BY created_at DESC
        ''', (user_id,))
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения заказов {user_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_order_by_id(order_id):
    """Получение заказа по ID"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT order_id, user_id, client_name, phone, street_address, 
                   entrance, floor, apartment, intercom, order_date, order_time, 
                   bags_count, price, status, created_at 
            FROM orders WHERE order_id = %s
        ''', (order_id,))
        order = cur.fetchone()
        return order
    except Exception as e:
        print(f"❌ Ошибка получения заказа {order_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_all_orders():
    """Получение всех заказов"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT order_id, user_id, client_name, phone, street_address, 
                   entrance, floor, apartment, intercom, order_date, order_time, 
                   bags_count, price, status, created_at 
            FROM orders ORDER BY created_at DESC
        ''')
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения всех заказов: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def create_order(user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
                 order_date, order_time, bags_count, price, payment_method='cash'):
    """Создание нового заказа"""
    # Проверяем рабочее время
    if not is_within_working_hours(order_time):
        return False, "Это время находится вне рабочего времени бота (10:00-22:00)."
    
    # Проверяем, не истёк ли слот
    if is_slot_expired(order_date, order_time):
        return False, "Это время уже недоступно для заказа (прошло более 1 часа 15 минут с начала слота)."
    
    conn = get_connection()
    if not conn:
        return False, "Ошибка подключения к БД"
    
    cur = conn.cursor()
    try:
        # Проверяем, свободен ли слот
        cur.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
            (order_date, order_time)
        )
        count = cur.fetchone()[0]
        
        if count >= 3:
            return False, "На это время уже 3 заказа. Пожалуйста, выберите другое время."
        
        # Создаём заказ
        cur.execute('''
            INSERT INTO orders 
            (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
             order_date, order_time, bags_count, price, payment_method, payment_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
        ''', (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
              order_date, order_time, bags_count, price, payment_method, 'pending', datetime.datetime.now()))
        
        order_id = cur.fetchone()[0]
        
        # Занимаем слот
        cur.execute('''
            INSERT INTO busy_slots (slot_date, slot_time, order_id)
            VALUES (%s, %s, %s)
        ''', (order_date, order_time, order_id))
        
        conn.commit()
        print(f"✅ Заказ #{order_id} успешно создан для пользователя {user_id}")
        return order_id, "Успешно"
        
    except Exception as e:
        print(f"❌ Ошибка при создании заказа: {e}")
        conn.rollback()
        return False, "Произошла ошибка. Пожалуйста, попробуйте ещё раз."
    finally:
        cur.close()
        conn.close()

def confirm_order(order_id):
    """Подтверждение заказа - меняет статус на confirmed, слот остаётся занятым"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Обновляем статус заказа на confirmed
        cur.execute('UPDATE orders SET status = %s WHERE order_id = %s', ('confirmed', order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} подтверждён")
    except Exception as e:
        print(f"❌ Ошибка подтверждения заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def update_order_status(order_id, new_status):
    """Обновление статуса заказа"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('UPDATE orders SET status = %s WHERE order_id = %s', (new_status, order_id))
        conn.commit()
        print(f"✅ Статус заказа #{order_id} изменён на {new_status}")
    except Exception as e:
        print(f"❌ Ошибка обновления статуса заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def cancel_order(order_id):
    """Отмена заказа - освобождаем место"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Удаляем слот
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        # Обновляем статус заказа
        cur.execute('UPDATE orders SET status = %s WHERE order_id = %s', ('cancelled', order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} отменён")
    except Exception as e:
        print(f"❌ Ошибка отмены заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def complete_order(order_id):
    """Выполнение заказа - освобождаем место"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        # Удаляем слот (освобождаем место)
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        # Обновляем статус заказа
        cur.execute('UPDATE orders SET status = %s WHERE order_id = %s', ('completed', order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} выполнен и слот освобождён")
    except Exception as e:
        print(f"❌ Ошибка выполнения заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ СООБЩЕНИЙ ===============

def save_message(user_id, message_text):
    """Сохранение сообщения от пользователя"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO messages (user_id, user_message, created_at, status)
            VALUES (%s, %s, %s, 'new')
            RETURNING message_id
        ''', (user_id, message_text, datetime.datetime.now()))
        message_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Сообщение #{message_id} сохранено от пользователя {user_id}")
        return message_id
    except Exception as e:
        print(f"❌ Ошибка сохранения сообщения: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_all_messages():
    """Получение всех сообщений"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT m.message_id, m.user_id, u.username, u.first_name, u.phone, 
                   m.user_message, m.admin_reply, m.status, m.created_at
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            ORDER BY m.created_at DESC
        ''')
        messages = cur.fetchall()
        return messages
    except Exception as e:
        print(f"❌ Ошибка получения сообщений: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def reply_to_message(message_id, reply_text):
    """Ответ администратора на сообщение"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE messages 
            SET admin_reply = %s, status = 'replied', replied_at = %s
            WHERE message_id = %s
        ''', (reply_text, datetime.datetime.now(), message_id))
        conn.commit()
        print(f"✅ Ответ на сообщение #{message_id} сохранён")
    except Exception as e:
        print(f"❌ Ошибка сохранения ответа: {e}")
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ ЧЁРНОГО СПИСКА ===============

def add_to_blacklist(user_id, reason=""):
    """Добавить пользователя в чёрный список"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO blacklist (user_id, reason, added_date, added_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET reason = EXCLUDED.reason, added_date = EXCLUDED.added_date
        ''', (user_id, reason, datetime.datetime.now(), 0))
        conn.commit()
        print(f"✅ Пользователь {user_id} добавлен в чёрный список")
    except Exception as e:
        print(f"❌ Ошибка добавления в чёрный список: {e}")
    finally:
        cur.close()
        conn.close()

def remove_from_blacklist(user_id):
    """Удалить пользователя из чёрного списка"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM blacklist WHERE user_id = %s', (user_id,))
        conn.commit()
        print(f"✅ Пользователь {user_id} удалён из чёрного списка")
    except Exception as e:
        print(f"❌ Ошибка удаления из чёрного списка: {e}")
    finally:
        cur.close()
        conn.close()

def get_blacklist():
    """Получить весь чёрный список"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT b.user_id, b.reason, b.added_date, u.username, u.first_name, u.phone
            FROM blacklist b
            LEFT JOIN users u ON b.user_id = u.user_id
            ORDER BY b.added_date DESC
        ''')
        blacklist = cur.fetchall()
        return blacklist
    except Exception as e:
        print(f"❌ Ошибка получения чёрного списка: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def is_user_blacklisted(user_id):
    """Проверить, есть ли пользователь в чёрном списке"""
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM blacklist WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        return result is not None
    except Exception as e:
        print(f"❌ Ошибка проверки чёрного списка: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# =============== ФУНКЦИИ ДЛЯ РАССЫЛОК ===============

def save_broadcast(admin_id, message_text):
    """Сохранить рассылку в историю"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
            VALUES (%s, %s, %s, %s)
            RETURNING broadcast_id
        ''', (admin_id, message_text, datetime.datetime.now(), 0))
        broadcast_id = cur.fetchone()[0]
        conn.commit()
        return broadcast_id
    except Exception as e:
        print(f"❌ Ошибка сохранения рассылки: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_broadcast_count(broadcast_id, count):
    """Обновить количество получателей"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('UPDATE broadcasts SET recipients_count = %s WHERE broadcast_id = %s', (count, broadcast_id))
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка обновления счётчика рассылки: {e}")
    finally:
        cur.close()
        conn.close()

def get_all_broadcasts():
    """Получить историю рассылок"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT broadcast_id, admin_id, message_text, sent_date, recipients_count
            FROM broadcasts ORDER BY sent_date DESC
        ''')
        broadcasts = cur.fetchall()
        return broadcasts
    except Exception as e:
        print(f"❌ Ошибка получения истории рассылок: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# Инициализация базы данных при импорте модуля
if __name__ != '__main__':
    init_db()
    print("✅ База данных инициализирована при импорте")
# =============== НОВЫЕ ФУНКЦИИ ДЛЯ МИНИ-МЕССЕНДЖЕРА ===============

def get_dialogs(filter_type='all'):
    """
    Получает список диалогов с последними сообщениями
    filter_type: 'all', 'new', 'important', 'outbox'
    """
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        # Получаем все диалоги с последним сообщением и количеством непрочитанных
        query = '''
            SELECT DISTINCT ON (m.user_id) 
                m.user_id,
                u.first_name,
                u.username,
                m.user_message as last_message,
                m.created_at as last_time,
                (SELECT COUNT(*) FROM messages WHERE user_id = m.user_id AND status = 'new') as unread_count,
                CASE WHEN b.user_id IS NOT NULL THEN TRUE ELSE FALSE END as is_blocked
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            LEFT JOIN blacklist b ON m.user_id = b.user_id
            WHERE m.status != 'deleted'
        '''
        
        if filter_type == 'new':
            query += ' AND (SELECT COUNT(*) FROM messages WHERE user_id = m.user_id AND status = \'new\') > 0'
        elif filter_type == 'important':
            query += ' AND m.is_important = TRUE'
        elif filter_type == 'outbox':
            query += " AND m.user_message LIKE '[ОТ АДМИНА]%'"
        
        query += ' ORDER BY m.user_id, m.created_at DESC'
        
        cur.execute(query)
        dialogs = cur.fetchall()
        return dialogs
    except Exception as e:
        print(f"❌ Ошибка получения диалогов: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_dialog_messages(user_id, limit=20):
    """Получает историю сообщений с пользователем"""
    print(f"🔍 ВХОД В get_dialog_messages для user {user_id}")
    
    conn = get_connection()
    if not conn:
        print("❌ Нет подключения к БД")
        return []
    
    cur = conn.cursor()
    try:
        print(f"🔍 Выполняем запрос для user {user_id}")
        
        # Запрос под вашу структуру таблицы
        cur.execute('''
            SELECT 
                message_id,
                user_id,
                user_message,
                admin_reply,
                status,
                is_important,
                created_at,
                replied_at
            FROM messages 
            WHERE user_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        
        messages = cur.fetchall()
        print(f"🔍 Найдено сообщений: {len(messages)}")
        
        # Преобразуем в удобный формат
        result = []
        for msg in messages:
            # msg: (message_id, user_id, user_message, admin_reply, status, is_important, created_at, replied_at)
            is_from_admin = msg[2] and msg[2].startswith('[ОТ АДМИНА]') if msg[2] else False
            is_read = (msg[4] == 'replied')
            
            # Текст сообщения (если от админа, убираем префикс)
            text = msg[2]
            if is_from_admin and text:
                text = text.replace('[ОТ АДМИНА] ', '', 1)
            
            result.append({
                'id': msg[0],
                'user_id': msg[1],
                'from_admin': is_from_admin,
                'text': text,
                'admin_reply': msg[3],
                'status': msg[4],
                'is_important': msg[5],
                'time': msg[6],
                'replied_at': msg[7],
                'is_read': is_read
            })
        
        if result:
            print(f"🔍 Первое сообщение после обработки: {result[0]}")
        
        return result
        
    except Exception as e:
        print(f"❌ ОШИБКА в get_dialog_messages: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        cur.close()
        conn.close()

def mark_dialog_as_read(user_id):
    """Отмечает все сообщения пользователя как прочитанные"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE messages 
            SET status = 'replied' 
            WHERE user_id = %s AND status = 'new'
        ''', (user_id,))
        conn.commit()
        print(f"✅ Диалог с {user_id} отмечен как прочитанный")
    except Exception as e:
        print(f"❌ Ошибка отметки диалога: {e}")
    finally:
        cur.close()
        conn.close()

def mark_message_as_read(message_id):
    """Отмечает конкретное сообщение как прочитанное"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute("UPDATE messages SET status = 'replied' WHERE message_id = %s", (message_id,))
        conn.commit()
        print(f"✅ Сообщение #{message_id} отмечено как прочитанное")
    except Exception as e:
        print(f"❌ Ошибка отметки сообщения: {e}")
    finally:
        cur.close()
        conn.close()

def delete_message(message_id, permanent=False):
    """Удаляет сообщение (в корзину или навсегда)"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        if permanent:
            cur.execute('DELETE FROM messages WHERE message_id = %s', (message_id,))
        else:
            cur.execute("UPDATE messages SET status = 'deleted' WHERE message_id = %s", (message_id,))  # ← ИСПРАВЛЕНО
        conn.commit()
        print(f"✅ Сообщение #{message_id} удалено")
    except Exception as e:
        print(f"❌ Ошибка удаления сообщения: {e}")
    finally:
        cur.close()
        conn.close()

def restore_message(message_id):
    """Восстанавливает сообщение из корзины"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute("UPDATE messages SET status = 'new' WHERE message_id = %s", (message_id,))  # ← ИСПРАВЛЕНО
        conn.commit()
        print(f"✅ Сообщение #{message_id} восстановлено")
    except Exception as e:
        print(f"❌ Ошибка восстановления сообщения: {e}")
    finally:
        cur.close()
        conn.close()

def get_deleted_messages():
    """Получает сообщения в корзине"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT 
                m.message_id,
                m.user_id,
                u.first_name,
                m.user_message,
                m.created_at
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.status = 'deleted'
            ORDER BY m.created_at DESC
            LIMIT 20
        ''')
        messages = cur.fetchall()
        return messages
    except Exception as e:
        print(f"❌ Ошибка получения корзины: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def save_admin_message(user_id, message_text):
    """Сохраняет ответ администратора"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO messages (user_id, user_message, status, created_at)
            VALUES (%s, %s, 'replied', %s)
            RETURNING message_id
        ''', (user_id, f"[ОТ АДМИНА] {message_text}", datetime.datetime.now()))
        message_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Ответ администратора #{message_id} сохранён")
        return message_id
    except Exception as e:
        print(f"❌ Ошибка сохранения ответа: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_total_unread_messages():
    """Получает общее количество непрочитанных сообщений (не удалённых)"""
    conn = get_connection()
    if not conn:
        return 0
    
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM messages WHERE status = 'new' AND status != 'deleted'")
        count = cur.fetchone()[0]
        return count
    except Exception as e:
        print(f"❌ Ошибка подсчёта непрочитанных: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_dialogs_count():
    """Получает количество диалогов (только с не удалёнными сообщениями)"""
    conn = get_connection()
    if not conn:
        return 0
    
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE status != 'deleted'")
        count = cur.fetchone()[0]
        return count
    except Exception as e:
        print(f"❌ Ошибка подсчёта диалогов: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def search_messages(search_text):
    """Поиск сообщений по тексту"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT 
                m.message_id,
                m.user_id,
                COALESCE(u.first_name, u.username, 'Пользователь') as user_name,
                m.user_message,
                m.created_at
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.user_message ILIKE %s AND m.status != 'deleted'
            ORDER BY m.created_at DESC
            LIMIT 20
        ''', (f'%{search_text}%',))
        messages = cur.fetchall()
        return messages
    except Exception as e:
        print(f"❌ Ошибка поиска сообщений: {e}")
        return []
    finally:
        cur.close()
        conn.close()
