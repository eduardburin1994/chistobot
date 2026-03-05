# database.py
import os
import sys
from pathlib import Path
import sqlite3
import time
import datetime
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
import random
import string
from pathlib import Path

def get_database_url():
    """Возвращает DATABASE_URL из окружения, с поддержкой принудительной установки"""
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']
    return os.getenv('DATABASE_URL')

# Временно устанавливаем DATABASE_URL как None
DATABASE_URL = None

print("🔍 Проверка файла .env:")
env_file = Path('.') / '.env'
print(f"   Полный путь: {env_file.absolute()}")
print(f"   Файл существует: {env_file.exists()}")
if env_file.exists():
    print(f"   Содержимое (первые 50 символов):")
    with open(env_file, 'r') as f:
        print(f"   {f.read(50)}...")
print("🔍 Загружаем DATABASE_URL из os.getenv():", os.getenv('DATABASE_URL'))
print("🔍 Загружаем DATABASE_URL из os.environ.get():", os.environ.get('DATABASE_URL'))

# =============== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ МОСКОВСКОГО ВРЕМЕНИ ===============
def moscow_now():
    """Возвращает текущее московское время (UTC+3)"""
    return datetime.datetime.now() + datetime.timedelta(hours=3)

# =============== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ===============

def get_connection():
    """Возвращает подключение к PostgreSQL с улучшенными настройками keepalive"""
    db_url = get_database_url()
    if not db_url:
        print("❌ DATABASE_URL не найден в переменных окружения!")
        return None
    
    try:
        # Проверяем, локальное ли подключение
        if 'localhost' in db_url or '127.0.0.1' in db_url:
            # Для локального подключения без SSL
            conn = psycopg2.connect(
                db_url, 
                connect_timeout=30,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                options='-c statement_timeout=30000'
            )
        else:
            # Для удаленного подключения (Render) с SSL
            conn = psycopg2.connect(
                db_url, 
                sslmode='require', 
                connect_timeout=30,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                options='-c statement_timeout=30000'
            )
        
        # Проверяем соединение
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

def get_connection_with_retry(max_retries=10, delay=5):
    """Пытается подключиться к БД несколько раз с увеличенными интервалами."""
    print(f"🔄 Попытка подключения к БД (макс. {max_retries} попыток)...")
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            if conn:
                print(f"✅ Подключение к БД успешно (попытка {attempt + 1})")
                return conn
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
            if attempt < max_retries - 1:
                wait_time = delay * (attempt + 1)
                print(f"   Повтор через {wait_time} секунд...")
                time.sleep(wait_time)
            else:
                print("❌ Не удалось подключиться к БД после всех попыток.")
    return None

# =============== SQLite ФУНКЦИИ ===============

def init_sqlite_db():
    """Создаёт таблицы в SQLite, если их нет"""
    db_url = get_database_url()
    if not db_url or not db_url.startswith('sqlite'):
        return
    
    conn = get_connection()
    if not conn:
        print("❌ Не удалось подключиться к SQLite для создания таблиц")
        return
    
    cur = conn.cursor()
    
    # Таблица users
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            street_address TEXT,
            entrance TEXT,
            floor TEXT,
            apartment TEXT,
            intercom TEXT,
            registered_date TIMESTAMP,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            referral_balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            level1_count INTEGER DEFAULT 0,
            level2_count INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица orders
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
            status TEXT DEFAULT 'new',
            courier_id INTEGER,
            created_at TIMESTAMP,
            confirmed_by INTEGER,
            confirmed_by_type TEXT,
            confirmed_at TIMESTAMP,
            completed_by INTEGER,
            completed_by_type TEXT,
            completed_at TIMESTAMP,
            cancelled_by INTEGER,
            cancelled_at TIMESTAMP,
            cancel_reason TEXT,
            payment_method TEXT,
            payment_status TEXT,
            taken_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица busy_slots
    cur.execute('''
        CREATE TABLE IF NOT EXISTS busy_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_date TEXT,
            slot_time TEXT,
            order_id INTEGER UNIQUE,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
    ''')
    
    # Таблица favorite_addresses
    cur.execute('''
        CREATE TABLE IF NOT EXISTS favorite_addresses (
            address_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
    
    # Таблица messages
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_message TEXT,
            admin_reply TEXT,
            status TEXT DEFAULT 'new',
            is_important BOOLEAN DEFAULT 0,
            created_at TIMESTAMP,
            replied_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица blacklist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            reason TEXT,
            added_date TIMESTAMP,
            added_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица broadcasts
    cur.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            message_text TEXT,
            sent_date TIMESTAMP,
            recipients_count INTEGER
        )
    ''')
    
    # Таблица referrals
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            level INTEGER DEFAULT 1,
            created_at TIMESTAMP,
            first_order_id INTEGER,
            rewarded BOOLEAN DEFAULT 0,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id),
            FOREIGN KEY (first_order_id) REFERENCES orders (order_id)
        )
    ''')
    
    # Таблица referral_earnings
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referral_earnings (
            earning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            source TEXT,
            source_id INTEGER,
            created_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица referral_spendings
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referral_spendings (
            spending_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            order_id INTEGER,
            created_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
    ''')
    
    # Таблица prices
    cur.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY DEFAULT 1,
            price_1 INTEGER,
            price_2 INTEGER,
            price_3 TEXT
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Таблицы SQLite созданы/проверены")

# =============== РЕФЕРАЛЬНАЯ СИСТЕМА ===============

def init_referral_tables():
    """Создаёт таблицы для реферальной системы"""
    db_url = get_database_url()
    
    # Для SQLite таблицы уже созданы в init_sqlite_db(), пропускаем
    if db_url and db_url.startswith('sqlite'):
        print("✅ SQLite: таблицы реферальной системы уже созданы")
        return
    
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute('''
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS referral_code TEXT UNIQUE,
            ADD COLUMN IF NOT EXISTS referred_by BIGINT,
            ADD COLUMN IF NOT EXISTS referral_balance INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_earned INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS level1_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS level2_count INTEGER DEFAULT 0
        ''')
        
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
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referral_earnings (
                earning_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                source TEXT,
                source_id INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
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
    print(f"🔑 Генерация кода для пользователя {user_id}")
    
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT first_name FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        # Берём первые 4 буквы имени или используем USER
        if user and user[0]:
            name_part = ''.join(c for c in user[0][:4] if c.isalpha()).upper()
        else:
            name_part = "USER"
        
        # Если имя короткое или нет букв, используем USER
        if len(name_part) < 2:
            name_part = "USER"
        
        print(f"📝 Name part: {name_part}")
        
        while True:
            # ТОЛЬКО цифры, никаких точек!
            random_part = ''.join(random.choices(string.digits, k=6))
            code = f"CHISTO{name_part}{random_part}"
            print(f"🔄 Пробуем код: {code}")
            
            cur.execute('SELECT user_id FROM users WHERE referral_code = %s', (code,))
            if not cur.fetchone():
                print(f"✅ Уникальный код найден: {code}")
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
        cur.execute('SELECT referral_code FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result and result[0]:
            return result[0]
        
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
    print(f"📝 register_referral: код={referral_code}, новый пользователь={new_user_id}")
    
    conn = get_connection()
    if not conn:
        print("❌ Нет подключения к БД")
        return None
    
    cur = conn.cursor()
    try:
        # Ищем владельца кода
        print(f"🔍 Ищем пользователя с кодом {referral_code}")
        cur.execute(
            'SELECT user_id FROM users WHERE referral_code = %s',
            (referral_code,)
        )
        referrer = cur.fetchone()
        
        if not referrer:
            print(f"❌ Код {referral_code} не найден в базе")
            return None
        
        referrer_id = referrer[0]
        print(f"👤 Владелец кода: {referrer_id}")
        
        # Проверяем, не пытается ли пользователь пригласить сам себя
        if referrer_id == new_user_id:
            print(f"⚠️ Пользователь {new_user_id} пытается использовать свой код")
            return None
        
        # Проверяем, не регистрировался ли уже этот пользователь
        cur.execute(
            'SELECT * FROM referrals WHERE referred_id = %s',
            (new_user_id,)
        )
        if cur.fetchone():
            print(f"⚠️ Пользователь {new_user_id} уже был рефералом")
            return None
        
        # Регистрируем реферала
        now_moscow = moscow_now()
        print(f"📅 Создаём запись в referrals: referrer={referrer_id}, referred={new_user_id}")
        
        cur.execute('''
            INSERT INTO referrals (referrer_id, referred_id, level, created_at)
            VALUES (%s, %s, 1, %s)
            RETURNING referral_id
        ''', (referrer_id, new_user_id, now_moscow))
        
        referral_id = cur.fetchone()[0]
        print(f"✅ Создана запись реферала #{referral_id}")
        
        # Увеличиваем счётчик level1 у пригласившего
        cur.execute('''
            UPDATE users 
            SET level1_count = level1_count + 1 
            WHERE user_id = %s
        ''', (referrer_id,))
        print(f"✅ Увеличен level1_count у {referrer_id}")
        
        # Сохраняем, кто пригласил нового пользователя
        cur.execute(
            'UPDATE users SET referred_by = %s WHERE user_id = %s',
            (referrer_id, new_user_id)
        )
        print(f"✅ Установлен referred_by={referrer_id} для пользователя {new_user_id}")
        
        conn.commit()
        print(f"✅ Реферал {new_user_id} успешно зарегистрирован для {referrer_id}")
        return referrer_id
        
    except Exception as e:
        print(f"❌ Ошибка регистрации реферала: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def process_referral_reward(referrer_id, friend_id, order_id, context=None):
    """Начисляет баллы за успешный заказ друга"""
    print(f"💰 process_referral_reward: referrer={referrer_id}, friend={friend_id}, order={order_id}")
    
    conn = get_connection()
    if not conn:
        print("❌ Нет подключения к БД")
        return
    
    cur = conn.cursor()
    try:
        # Проверяем, не начисляли ли уже баллы за этого друга
        cur.execute('''
            SELECT * FROM referrals 
            WHERE referred_id = %s AND rewarded = TRUE
        ''', (friend_id,))
        
        if cur.fetchone():
            print(f"⚠️ Заказ друга {friend_id} уже был вознаграждён")
            return
        
        # Начисляем 100 баллов пригласившему
        cur.execute('''
            UPDATE users 
            SET referral_balance = referral_balance + 100,
                total_earned = total_earned + 100
            WHERE user_id = %s
            RETURNING referral_balance
        ''', (referrer_id,))
        
        new_balance = cur.fetchone()
        print(f"✅ Начислено 100 баллов пользователю {referrer_id}. Новый баланс: {new_balance[0] if new_balance else '?'}")
        
        # Записываем начисление
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO referral_earnings (user_id, amount, source, source_id, created_at)
            VALUES (%s, 100, 'level1', %s, %s)
        ''', (referrer_id, friend_id, now_moscow))
        
        # Отмечаем, что реферал получил награду
        cur.execute('''
            UPDATE referrals 
            SET rewarded = TRUE, first_order_id = %s 
            WHERE referred_id = %s
        ''', (order_id, friend_id))
        
        conn.commit()
        print(f"✅ Пользователь {referrer_id} получил 100 баллов за реферала {friend_id}")
        
        # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ, если есть context
        if context:
            text = (
                f"🎁 <b>Вам начислено 100 бонусных баллов!</b>\n\n"
                f"Ваш друг сделал первый заказ. Спасибо, что приглашаете друзей!\n"
                f"💰 <b>Текущий баланс:</b> {new_balance[0]} баллов\n\n"
                f"300 баллов = бесплатный вывоз"
            )
            try:
                context.bot.send_message(
                    chat_id=referrer_id,
                    text=text,
                    parse_mode='HTML'
                )
                print(f"✅ Уведомление отправлено пользователю {referrer_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки уведомления: {e}")
        
        # Проверяем, есть ли у реферера свой реферер (для 2 уровня)
        cur.execute('SELECT referred_by FROM users WHERE user_id = %s', (referrer_id,))
        level2_referrer = cur.fetchone()
        
        if level2_referrer and level2_referrer[0]:
            level2_id = level2_referrer[0]
            print(f"👥 Найден реферер 2 уровня: {level2_id}")
            
            cur.execute('''
                UPDATE users 
                SET referral_balance = referral_balance + 30,
                    total_earned = total_earned + 30,
                    level2_count = level2_count + 1
                WHERE user_id = %s
                RETURNING referral_balance
            ''', (level2_id,))
            
            level2_new_balance = cur.fetchone()
            
            cur.execute('''
                INSERT INTO referral_earnings (user_id, amount, source, source_id, created_at)
                VALUES (%s, 30, 'level2', %s, %s)
            ''', (level2_id, friend_id, now_moscow))
            
            print(f"✅ Пользователь {level2_id} получил 30 баллов за реферала 2 уровня")
            
            # УВЕДОМЛЕНИЕ для реферала 2 уровня
            if context:
                text = (
                    f"🎁 <b>Вам начислено 30 бонусных баллов!</b>\n\n"
                    f"Друг вашего друга сделал заказ. Бонусы за рефералов 2 уровня!\n"
                    f"💰 <b>Текущий баланс:</b> {level2_new_balance[0]} баллов\n\n"
                    f"300 баллов = бесплатный вывоз"
                )
                try:
                    context.bot.send_message(
                        chat_id=level2_id,
                        text=text,
                        parse_mode='HTML'
                    )
                    print(f"✅ Уведомление отправлено пользователю {level2_id}")
                except Exception as e:
                    print(f"❌ Ошибка отправки уведомления: {e}")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Ошибка начисления баллов: {e}")
        conn.rollback()
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
        cur.execute('SELECT referral_balance FROM users WHERE user_id = %s', (user_id,))
        balance = cur.fetchone()[0]
        
        if balance < amount:
            return False
        
        cur.execute('''
            UPDATE users 
            SET referral_balance = referral_balance - %s 
            WHERE user_id = %s
        ''', (amount, user_id))
        
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO referral_spendings (user_id, amount, order_id, created_at)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, amount, order_id, now_moscow))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка списания баллов: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# =============== ОСНОВНЫЕ ФУНКЦИИ БД ===============

def execute_with_retry(cursor_func, *args, **kwargs):
    """
    Выполняет функцию с курсором, автоматически переподключаясь при ошибке
    """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            return cursor_func(*args, **kwargs)
        except (psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            print(f"⚠️ Ошибка выполнения запроса (попытка {attempt + 1}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)
                # Переподключаемся
                globals()['conn'] = get_connection_with_retry()
                if 'conn' in globals() and globals()['conn']:
                    continue
            raise

def save_prices(prices):
    """Сохраняет цены в БД"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY DEFAULT 1,
                price_1 INTEGER,
                price_2 INTEGER,
                price_3 TEXT
            )
        ''')
        
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
    db_url = get_database_url()
    
    if db_url and db_url.startswith('sqlite'):
        # Проверим, существует ли таблица prices
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'")
            if not cur.fetchone():
                conn.close()
                return {'1': 100, '2': 140, '3+': 150}
            conn.close()
    
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
                '3+': result[2]
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
        cur.execute("SELECT COUNT(*) FROM messages WHERE user_id = %s", (user_id,))
        count = cur.fetchone()[0]
        print(f"🔍 Всего сообщений для user {user_id}: {count}")
        
        if count > 0:
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
    db_url = get_database_url()
    
    if db_url and db_url.startswith('sqlite'):
        print("📋 SQLite: информация о таблицах недоступна")
        return
    
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'messages' ORDER BY ordinal_position")
        columns = cur.fetchall()
        print("📋 СТРУКТУРА ТАБЛИЦЫ messages:")
        for i, col in enumerate(columns):
            print(f"   {i}: {col[0]} ({col[1]})")
        
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

def check_database_integrity():
    """Проверка целостности базы данных"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    try:
        tables = ['users', 'orders', 'messages', 'favorite_addresses']
        for table in tables:
            cur.execute(f"SELECT * FROM {table} LIMIT 1")
            print(f"✅ Таблица {table} доступна")
    except Exception as e:
        print(f"❌ Ошибка при проверке таблицы {table}: {e}")
    finally:
        cur.close()
        conn.close()

def init_db():
    """Инициализация базы данных"""
    db_url = get_database_url()
    
    # Для SQLite создаём таблицы при первом запуске
    if db_url and db_url.startswith('sqlite'):
        init_sqlite_db()
        return
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_connection_with_retry()
            if not conn:
                print("❌ Не удалось подключиться к БД для инициализации")
                return
            
            cur = conn.cursor()
            
            # Просто проверяем, что таблицы существуют, выполняя простой запрос
            try:
                cur.execute("SELECT 1 FROM users LIMIT 1")
                print("✅ Таблицы уже существуют, пропускаем создание")
            except Exception:
                # Если таблиц нет, создаём их (но мы уже создали всё вручную)
                print("⚠️ Таблицы не найдены, но мы создали их через psql")
                print("✅ Продолжаем работу...")
            
            cur.close()
            conn.close()
            return
            
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1} проверки таблиц не удалась: {e}")
            if attempt < max_retries - 1:
                print(f"   Повтор через 3 секунд...")
                time.sleep(3)
            else:
                print("❌ Не удалось проверить таблицы после всех попыток")
                raise

# =============== ФУНКЦИИ ДЛЯ РАБОТЫ СО СЛОТАМИ ===============

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
        start_time_str = slot_time.split('-')[0]
        start_hour = int(start_time_str.split(':')[0])
        
        return WORK_HOURS['start'] <= start_hour < WORK_HOURS['end']
    except Exception as e:
        print(f"❌ Ошибка проверки рабочего времени: {e}")
        return False

def is_slot_expired(slot_date, slot_time):
    """
    Проверяет, истёк ли слот.
    Слот считается истекшим, если:
    - Это сегодня И текущее время > время начала слота + 1 час 15 минут
    - ИЛИ это сегодня И текущее время > время окончания слота
    - ИЛИ это прошедшая дата (вчера и раньше)
    """
    try:
        # Используем московское время
        now = moscow_now()
        today = now.strftime("%d.%m.%Y")
        
        # Парсим дату слота
        day, month, year = map(int, slot_date.split('.'))
        slot_datetime = datetime.datetime(year, month, day)
        
        # Если слот на прошедшую дату - сразу истёк
        if slot_datetime.date() < now.date():
            print(f"📅 Слот на прошедшую дату {slot_date} исключён")
            return True
        
        # Если слот на завтра или позже - доступен
        if slot_date != today:
            return False
        
        # Парсим время начала и окончания слота
        start_time_str, end_time_str = slot_time.split('-')
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        # Время начала и окончания слота сегодня
        slot_start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        slot_end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        # Проверка 1: прошло ли время окончания
        if now > slot_end:
            print(f"⏰ Слот {slot_time} закончился в {slot_end.strftime('%H:%M')}")
            return True
        
        # Проверка 2: прошло ли 1 час 15 минут с начала
        expiry_time = slot_start + datetime.timedelta(hours=1, minutes=15)
        if now > expiry_time:
            print(f"⏰ Слот {slot_time} истёк в {expiry_time.strftime('%H:%M')} (прошло >1ч15м с начала)")
            return True
        
        # Слот ещё доступен
        return False
        
    except Exception as e:
        print(f"❌ Ошибка при проверке истечения слота: {e}")
        return True

def get_available_slots(date):
    """
    Возвращает список доступных слотов для указанной даты
    Учитывает:
    - Максимум 4 заказа на слот
    - Истечение времени (1ч15м или конец слота)
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
            
            # ПРОВЕРКА ВРЕМЕНИ: истёк ли слот
            if is_slot_expired(date, slot):
                print(f"⏰ Слот {slot} на дату {date} исключён (истёк по времени)")
                continue
            
            # Получаем количество занятых мест
            cur.execute(
                'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
                (date, slot)
            )
            count = cur.fetchone()[0]
            
            # 4 - максимум заказов
            free_places = 4 - count
            
            if free_places > 0:
                available_slots.append(slot)
                slot_info[slot] = free_places
                print(f"✅ Слот {slot} доступен ({free_places} мест)")
        
        return available_slots, slot_info
    except Exception as e:
        print(f"❌ Ошибка получения доступных слотов: {e}")
        return [], {}
    finally:
        cur.close()
        conn.close()

def is_time_slot_free(date, time_slot):
    """Проверка, свободен ли временной слот"""
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
        return count < 4
    except Exception as e:
        print(f"❌ Ошибка проверки слота: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_slot_availability(date, time_slot):
    """Получить количество свободных мест на конкретное время"""
    # Сначала проверяем рабочие часы
    if not is_within_working_hours(time_slot):
        return 0
    
    # Проверяем, не истёк ли слот
    if is_slot_expired(date, time_slot):
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
        return 4 - count
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, registered_date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, username, first_name, last_name, now_moscow))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO favorite_addresses 
            (user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING address_id
        ''', (user_id, address_name, street_address, entrance, floor, apartment, intercom, now_moscow))
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
                   bags_count, price, status, courier_id, created_at,
                   confirmed_by, confirmed_by_type, confirmed_at,
                   completed_by, completed_by_type, completed_at,
                   cancelled_by, cancelled_at, cancel_reason
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
                   bags_count, price, status, courier_id, created_at 
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
    
    # ПРОВЕРКА ВРЕМЕНИ: не истёк ли слот
    if is_slot_expired(order_date, order_time):
        return False, "Это время уже недоступно для заказа (прошло более 1 часа 15 минут с начала слота или слот закончился)."
    
    conn = get_connection()
    if not conn:
        return False, "Ошибка подключения к БД"
    
    cur = conn.cursor()
    try:
        # Проверяем, свободен ли слот (максимум 4 заказа)
        cur.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
            (order_date, order_time)
        )
        count = cur.fetchone()[0]
        
        if count >= 4:
            return False, "На это время уже 4 заказа. Пожалуйста, выберите другое время."
        
        now_moscow = moscow_now()
        # Создаём заказ
        cur.execute('''
            INSERT INTO orders 
            (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
             order_date, order_time, bags_count, price, payment_method, payment_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
        ''', (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
              order_date, order_time, bags_count, price, payment_method, 'pending', now_moscow))
        
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

def confirm_order(order_id, confirmed_by=None):
    """Подтверждение заказа - меняет статус на confirmed"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'confirmed', 
                confirmed_at = %s,
                confirmed_by = %s,
                confirmed_by_type = 'admin'
            WHERE order_id = %s AND status = 'new'
        ''', (now_moscow, confirmed_by, order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} подтверждён администратором {confirmed_by}")
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

def cancel_order(order_id, cancelled_by=None, reason='admin_cancelled'):
    """Отмена заказа - освобождаем место"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'cancelled',
                cancelled_at = %s,
                cancelled_by = %s,
                cancel_reason = %s
            WHERE order_id = %s
        ''', (now_moscow, cancelled_by, reason, order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} отменён администратором {cancelled_by}")
    except Exception as e:
        print(f"❌ Ошибка отмены заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def complete_order(order_id, completed_by=None, completed_by_type='admin'):
    """Отметить заказ как выполненный"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT status, courier_id FROM orders WHERE order_id = %s', (order_id,))
        order = cur.fetchone()
        
        if not order:
            print(f"❌ Заказ #{order_id} не найден")
            return False
        
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'completed', 
                completed_at = %s,
                completed_by = %s,
                completed_by_type = %s
            WHERE order_id = %s
        ''', (now_moscow, completed_by, completed_by_type, order_id))
        
        conn.commit()
        print(f"✅ Заказ #{order_id} выполнен. Кем: {completed_by_type} (ID: {completed_by})")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка выполнения заказа {order_id}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

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

# =============== ФУНКЦИИ ДЛЯ КУРЬЕРОВ ===============

def get_courier_active_orders():
    """Получает активные заказы (new и confirmed) на сегодня и завтра"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        now_moscow = moscow_now()
        today = now_moscow.strftime("%d.%m.%Y")
        tomorrow = (now_moscow + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
        
        cur.execute('''
            SELECT order_id, user_id, client_name, phone, street_address, 
                   entrance, floor, apartment, intercom, order_date, order_time, 
                   bags_count, price, status, courier_id
            FROM orders
            WHERE status IN ('new', 'confirmed') 
              AND order_date IN (%s, %s)
            ORDER BY order_date, order_time
        ''', (today, tomorrow))
        
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения активных заказов: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def assign_courier_to_order(order_id, courier_id):
    """Назначает курьера на заказ и меняет статус на confirmed"""
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT status FROM orders WHERE order_id = %s', (order_id,))
        status = cur.fetchone()
        
        if not status or status[0] != 'new':
            print(f"❌ Заказ #{order_id} нельзя взять (статус: {status[0] if status else 'unknown'})")
            return False
        
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'confirmed', 
                courier_id = %s, 
                taken_at = %s,
                confirmed_by = %s,
                confirmed_by_type = 'courier',
                confirmed_at = %s
            WHERE order_id = %s AND status = 'new'
        ''', (courier_id, now_moscow, courier_id, now_moscow, order_id))
        
        conn.commit()
        print(f"✅ Курьер {courier_id} назначен на заказ #{order_id}")
        return True
    except Exception as e:
        print(f"❌ Ошибка назначения курьера: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_courier_completed_orders(courier_id, limit=10):
    """Получает историю выполненных заказов курьера"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT order_id, order_date, order_time, bags_count, price
            FROM orders
            WHERE status = 'completed' AND courier_id = %s
            ORDER BY completed_at DESC
            LIMIT %s
        ''', (courier_id, limit))
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения истории: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_courier_stats(courier_id):
    """Общая статистика курьера"""
    conn = get_connection()
    if not conn:
        return {'total': 0, 'bags': 0, 'earned': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' AND courier_id = %s
        ''', (courier_id,))
        total, bags, earned = cur.fetchone()
        return {'total': total or 0, 'bags': bags or 0, 'earned': earned or 0}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {'total': 0, 'bags': 0, 'earned': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_daily_stats(courier_id, date):
    """Статистика курьера за конкретный день"""
    conn = get_connection()
    if not conn:
        return {'completed': 0, 'bags': 0, 'earned': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND order_date = %s
        ''', (courier_id, date))
        completed, bags, earned = cur.fetchone()
        return {'completed': completed or 0, 'bags': bags or 0, 'earned': earned or 0}
    except Exception as e:
        print(f"❌ Ошибка получения дневной статистики: {e}")
        return {'completed': 0, 'bags': 0, 'earned': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_stats_period(courier_id, start_date, end_date):
    """Статистика за период"""
    conn = get_connection()
    if not conn:
        return {'total': 0, 'bags': 0, 'earned': 0, 'avg': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND order_date BETWEEN %s AND %s
        ''', (courier_id, start_date, end_date))
        total, bags, earned = cur.fetchone()
        total = total or 0
        earned = earned or 0
        avg = earned // total if total > 0 else 0
        return {'total': total, 'bags': bags or 0, 'earned': earned, 'avg': avg}
    except Exception as e:
        print(f"❌ Ошибка получения статистики за период: {e}")
        return {'total': 0, 'bags': 0, 'earned': 0, 'avg': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_hourly_stats(courier_id):
    """Статистика по часам (в какое время чаще берут заказы)"""
    conn = get_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT EXTRACT(HOUR FROM taken_at) as hour, COUNT(*)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND taken_at IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        ''', (courier_id,))
        
        hourly = {}
        for row in cur.fetchall():
            hour = int(row[0])
            count = row[1]
            hourly[hour] = count
        return hourly
    except Exception as e:
        print(f"❌ Ошибка получения почасовой статистики: {e}")
        return {}
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO messages (user_id, user_message, created_at, status)
            VALUES (%s, %s, %s, 'new')
            RETURNING message_id
        ''', (user_id, message_text, now_moscow))
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
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE messages 
            SET admin_reply = %s, status = 'replied', replied_at = %s
            WHERE message_id = %s
        ''', (reply_text, now_moscow, message_id))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO blacklist (user_id, reason, added_date, added_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET reason = EXCLUDED.reason, added_date = EXCLUDED.added_date
        ''', (user_id, reason, now_moscow, 0))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
            VALUES (%s, %s, %s, %s)
            RETURNING broadcast_id
        ''', (admin_id, message_text, now_moscow, 0))
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

# =============== ФУНКЦИИ ДЛЯ МИНИ-МЕССЕНДЖЕРА ===============

def get_dialogs(filter_type='all'):
    """Получает список диалогов с последними сообщениями"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
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
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
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
        result = []
        for msg in messages:
            is_from_admin = msg[2] and msg[2].startswith('[ОТ АДМИНА]') if msg[2] else False
            is_read = (msg[4] == 'replied')
            
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
        
        return result
        
    except Exception as e:
        print(f"❌ Ошибка в get_dialog_messages: {e}")
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
            cur.execute("UPDATE messages SET status = 'deleted' WHERE message_id = %s", (message_id,))
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
        cur.execute("UPDATE messages SET status = 'new' WHERE message_id = %s", (message_id,))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO messages (user_id, user_message, status, created_at)
            VALUES (%s, %s, 'replied', %s)
            RETURNING message_id
        ''', (user_id, f"[ОТ АДМИНА] {message_text}", now_moscow))
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
    """Получает общее количество непрочитанных сообщений"""
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
    """Получает количество диалогов"""
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

# =============== ФУНКЦИИ ДЛЯ ПОЛНОГО УДАЛЕНИЯ КЛИЕНТА ===============

def get_user_stats_for_deletion(user_id):
    """
    Возвращает статистику пользователя перед удалением
    """
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        stats = {}
        
        # Информация о пользователе
        cur.execute('SELECT first_name, username, phone FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        if user:
            stats['name'] = user[0] or 'Не указано'
            stats['username'] = user[1] or 'нет'
            stats['phone'] = user[2] or 'нет'
        else:
            stats['name'] = 'Не найден'
            stats['username'] = 'нет'
            stats['phone'] = 'нет'
        
        # Количество заказов
        cur.execute('SELECT COUNT(*) FROM orders WHERE user_id = %s', (user_id,))
        stats['orders'] = cur.fetchone()[0]
        
        # Количество сообщений
        cur.execute('SELECT COUNT(*) FROM messages WHERE user_id = %s', (user_id,))
        stats['messages'] = cur.fetchone()[0]
        
        # Количество избранных адресов
        cur.execute('SELECT COUNT(*) FROM favorite_addresses WHERE user_id = %s', (user_id,))
        stats['favorites'] = cur.fetchone()[0]
        
        # Реферальные связи
        cur.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = %s', (user_id,))
        stats['referrals_sent'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM referrals WHERE referred_id = %s', (user_id,))
        stats['referrals_received'] = cur.fetchone()[0]
        
        return stats
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def delete_user_completely(user_id):
    """
    Полностью удаляет пользователя из базы данных
    """
    conn = get_connection()
    if not conn:
        print(f"❌ Не удалось подключиться к БД для удаления пользователя {user_id}")
        return False
    
    cur = conn.cursor()
    try:
        print(f"🗑️ Начинаем полное удаление пользователя {user_id}...")
        
        # 1. Удаляем избранные адреса
        cur.execute('DELETE FROM favorite_addresses WHERE user_id = %s', (user_id,))
        
        # 2. Удаляем сообщения
        cur.execute('DELETE FROM messages WHERE user_id = %s', (user_id,))
        
        # 3. Получаем ID заказов пользователя для удаления слотов
        cur.execute('SELECT order_id FROM orders WHERE user_id = %s', (user_id,))
        orders = cur.fetchall()
        
        # 4. Удаляем занятые слоты для каждого заказа
        for order in orders:
            cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order[0],))
        
        # 5. Удаляем заказы
        cur.execute('DELETE FROM orders WHERE user_id = %s', (user_id,))
        
        # 6. Удаляем реферальные связи
        cur.execute('DELETE FROM referrals WHERE referrer_id = %s', (user_id,))
        cur.execute('DELETE FROM referrals WHERE referred_id = %s', (user_id,))
        
        # 7. Удаляем начисления и траты баллов
        cur.execute('DELETE FROM referral_earnings WHERE user_id = %s', (user_id,))
        cur.execute('DELETE FROM referral_spendings WHERE user_id = %s', (user_id,))
        
        # 8. Удаляем самого пользователя
        cur.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
        user_deleted = cur.rowcount
        
        if user_deleted > 0:
            conn.commit()
            print(f"✅ ПОЛНОЕ УДАЛЕНИЕ пользователя {user_id} завершено")
            return True
        else:
            conn.rollback()
            print(f"❌ Пользователь {user_id} не найден")
            return False
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при удалении пользователя {user_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# Удаляем дубликат функции delete_user_completely (второй вариант)

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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO favorite_addresses 
            (user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING address_id
        ''', (user_id, address_name, street_address, entrance, floor, apartment, intercom, now_moscow))
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
                   bags_count, price, status, courier_id, created_at,
                   confirmed_by, confirmed_by_type, confirmed_at,
                   completed_by, completed_by_type, completed_at,
                   cancelled_by, cancelled_at, cancel_reason
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
                   bags_count, price, status, courier_id, created_at 
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
    
    # ПРОВЕРКА ВРЕМЕНИ: не истёк ли слот
    if is_slot_expired(order_date, order_time):
        return False, "Это время уже недоступно для заказа (прошло более 1 часа 15 минут с начала слота или слот закончился)."
    
    conn = get_connection()
    if not conn:
        return False, "Ошибка подключения к БД"
    
    cur = conn.cursor()
    try:
        # Проверяем, свободен ли слот (максимум 4 заказа)
        cur.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = %s AND slot_time = %s', 
            (order_date, order_time)
        )
        count = cur.fetchone()[0]
        
        if count >= 4:
            return False, "На это время уже 4 заказа. Пожалуйста, выберите другое время."
        
        now_moscow = moscow_now()
        # Создаём заказ
        cur.execute('''
            INSERT INTO orders 
            (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
             order_date, order_time, bags_count, price, payment_method, payment_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
        ''', (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
              order_date, order_time, bags_count, price, payment_method, 'pending', now_moscow))
        
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

def confirm_order(order_id, confirmed_by=None):
    """Подтверждение заказа - меняет статус на confirmed"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'confirmed', 
                confirmed_at = %s,
                confirmed_by = %s,
                confirmed_by_type = 'admin'
            WHERE order_id = %s AND status = 'new'
        ''', (now_moscow, confirmed_by, order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} подтверждён администратором {confirmed_by}")
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

def cancel_order(order_id, cancelled_by=None, reason='admin_cancelled'):
    """Отмена заказа - освобождаем место"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'cancelled',
                cancelled_at = %s,
                cancelled_by = %s,
                cancel_reason = %s
            WHERE order_id = %s
        ''', (now_moscow, cancelled_by, reason, order_id))
        conn.commit()
        print(f"✅ Заказ #{order_id} отменён администратором {cancelled_by}")
    except Exception as e:
        print(f"❌ Ошибка отмены заказа {order_id}: {e}")
    finally:
        cur.close()
        conn.close()

def complete_order(order_id, completed_by=None, completed_by_type='admin'):
    """Отметить заказ как выполненный"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT status, courier_id FROM orders WHERE order_id = %s', (order_id,))
        order = cur.fetchone()
        
        if not order:
            print(f"❌ Заказ #{order_id} не найден")
            return False
        
        cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order_id,))
        
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'completed', 
                completed_at = %s,
                completed_by = %s,
                completed_by_type = %s
            WHERE order_id = %s
        ''', (now_moscow, completed_by, completed_by_type, order_id))
        
        conn.commit()
        print(f"✅ Заказ #{order_id} выполнен. Кем: {completed_by_type} (ID: {completed_by})")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка выполнения заказа {order_id}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

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

# =============== ФУНКЦИИ ДЛЯ КУРЬЕРОВ ===============

def get_courier_active_orders():
    """Получает активные заказы (new и confirmed) на сегодня и завтра"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        now_moscow = moscow_now()
        today = now_moscow.strftime("%d.%m.%Y")
        tomorrow = (now_moscow + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
        
        cur.execute('''
            SELECT order_id, user_id, client_name, phone, street_address, 
                   entrance, floor, apartment, intercom, order_date, order_time, 
                   bags_count, price, status, courier_id
            FROM orders
            WHERE status IN ('new', 'confirmed') 
              AND order_date IN (%s, %s)
            ORDER BY order_date, order_time
        ''', (today, tomorrow))
        
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения активных заказов: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def assign_courier_to_order(order_id, courier_id):
    """Назначает курьера на заказ и меняет статус на confirmed"""
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT status FROM orders WHERE order_id = %s', (order_id,))
        status = cur.fetchone()
        
        if not status or status[0] != 'new':
            print(f"❌ Заказ #{order_id} нельзя взять (статус: {status[0] if status else 'unknown'})")
            return False
        
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE orders 
            SET status = 'confirmed', 
                courier_id = %s, 
                taken_at = %s,
                confirmed_by = %s,
                confirmed_by_type = 'courier',
                confirmed_at = %s
            WHERE order_id = %s AND status = 'new'
        ''', (courier_id, now_moscow, courier_id, now_moscow, order_id))
        
        conn.commit()
        print(f"✅ Курьер {courier_id} назначен на заказ #{order_id}")
        return True
    except Exception as e:
        print(f"❌ Ошибка назначения курьера: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_courier_completed_orders(courier_id, limit=10):
    """Получает историю выполненных заказов курьера"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT order_id, order_date, order_time, bags_count, price
            FROM orders
            WHERE status = 'completed' AND courier_id = %s
            ORDER BY completed_at DESC
            LIMIT %s
        ''', (courier_id, limit))
        orders = cur.fetchall()
        return orders
    except Exception as e:
        print(f"❌ Ошибка получения истории: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_courier_stats(courier_id):
    """Общая статистика курьера"""
    conn = get_connection()
    if not conn:
        return {'total': 0, 'bags': 0, 'earned': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' AND courier_id = %s
        ''', (courier_id,))
        total, bags, earned = cur.fetchone()
        return {'total': total or 0, 'bags': bags or 0, 'earned': earned or 0}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {'total': 0, 'bags': 0, 'earned': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_daily_stats(courier_id, date):
    """Статистика курьера за конкретный день"""
    conn = get_connection()
    if not conn:
        return {'completed': 0, 'bags': 0, 'earned': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND order_date = %s
        ''', (courier_id, date))
        completed, bags, earned = cur.fetchone()
        return {'completed': completed or 0, 'bags': bags or 0, 'earned': earned or 0}
    except Exception as e:
        print(f"❌ Ошибка получения дневной статистики: {e}")
        return {'completed': 0, 'bags': 0, 'earned': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_stats_period(courier_id, start_date, end_date):
    """Статистика за период"""
    conn = get_connection()
    if not conn:
        return {'total': 0, 'bags': 0, 'earned': 0, 'avg': 0}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(bags_count), 0), COALESCE(SUM(price), 0)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND order_date BETWEEN %s AND %s
        ''', (courier_id, start_date, end_date))
        total, bags, earned = cur.fetchone()
        total = total or 0
        earned = earned or 0
        avg = earned // total if total > 0 else 0
        return {'total': total, 'bags': bags or 0, 'earned': earned, 'avg': avg}
    except Exception as e:
        print(f"❌ Ошибка получения статистики за период: {e}")
        return {'total': 0, 'bags': 0, 'earned': 0, 'avg': 0}
    finally:
        cur.close()
        conn.close()

def get_courier_hourly_stats(courier_id):
    """Статистика по часам (в какое время чаще берут заказы)"""
    conn = get_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT EXTRACT(HOUR FROM taken_at) as hour, COUNT(*)
            FROM orders
            WHERE status = 'completed' 
              AND courier_id = %s 
              AND taken_at IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        ''', (courier_id,))
        
        hourly = {}
        for row in cur.fetchall():
            hour = int(row[0])
            count = row[1]
            hourly[hour] = count
        return hourly
    except Exception as e:
        print(f"❌ Ошибка получения почасовой статистики: {e}")
        return {}
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO messages (user_id, user_message, created_at, status)
            VALUES (%s, %s, %s, 'new')
            RETURNING message_id
        ''', (user_id, message_text, now_moscow))
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
        now_moscow = moscow_now()
        cur.execute('''
            UPDATE messages 
            SET admin_reply = %s, status = 'replied', replied_at = %s
            WHERE message_id = %s
        ''', (reply_text, now_moscow, message_id))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO blacklist (user_id, reason, added_date, added_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET reason = EXCLUDED.reason, added_date = EXCLUDED.added_date
        ''', (user_id, reason, now_moscow, 0))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
            VALUES (%s, %s, %s, %s)
            RETURNING broadcast_id
        ''', (admin_id, message_text, now_moscow, 0))
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

# =============== ФУНКЦИИ ДЛЯ МИНИ-МЕССЕНДЖЕРА ===============

def get_dialogs(filter_type='all'):
    """Получает список диалогов с последними сообщениями"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
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
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
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
        result = []
        for msg in messages:
            is_from_admin = msg[2] and msg[2].startswith('[ОТ АДМИНА]') if msg[2] else False
            is_read = (msg[4] == 'replied')
            
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
        
        return result
        
    except Exception as e:
        print(f"❌ Ошибка в get_dialog_messages: {e}")
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
            cur.execute("UPDATE messages SET status = 'deleted' WHERE message_id = %s", (message_id,))
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
        cur.execute("UPDATE messages SET status = 'new' WHERE message_id = %s", (message_id,))
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
        now_moscow = moscow_now()
        cur.execute('''
            INSERT INTO messages (user_id, user_message, status, created_at)
            VALUES (%s, %s, 'replied', %s)
            RETURNING message_id
        ''', (user_id, f"[ОТ АДМИНА] {message_text}", now_moscow))
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
    """Получает общее количество непрочитанных сообщений"""
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
    """Получает количество диалогов"""
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

# Инициализация базы данных при импорте модуля
# if __name__ != '__main__':
#    init_db()
#    print("✅ База данных инициализирована при импорте")

    # =============== ФУНКЦИИ ДЛЯ ПОЛНОГО УДАЛЕНИЯ КЛИЕНТА ===============

def get_user_stats_for_deletion(user_id):
    """
    Возвращает статистику пользователя перед удалением
    """
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    try:
        stats = {}
        
        # Информация о пользователе
        cur.execute('SELECT first_name, username, phone FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        if user:
            stats['name'] = user[0] or 'Не указано'
            stats['username'] = user[1] or 'нет'
            stats['phone'] = user[2] or 'нет'
        else:
            stats['name'] = 'Не найден'
            stats['username'] = 'нет'
            stats['phone'] = 'нет'
        
        # Количество заказов
        cur.execute('SELECT COUNT(*) FROM orders WHERE user_id = %s', (user_id,))
        stats['orders'] = cur.fetchone()[0]
        
        # Количество сообщений
        cur.execute('SELECT COUNT(*) FROM messages WHERE user_id = %s', (user_id,))
        stats['messages'] = cur.fetchone()[0]
        
        # Количество избранных адресов
        cur.execute('SELECT COUNT(*) FROM favorite_addresses WHERE user_id = %s', (user_id,))
        stats['favorites'] = cur.fetchone()[0]
        
        # Реферальные связи
        cur.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = %s', (user_id,))
        stats['referrals_sent'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM referrals WHERE referred_id = %s', (user_id,))
        stats['referrals_received'] = cur.fetchone()[0]
        
        return stats
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def delete_user_completely(user_id):
    """
    Полностью удаляет пользователя из базы данных
    """
    conn = get_connection()
    if not conn:
        print(f"❌ Не удалось подключиться к БД для удаления пользователя {user_id}")
        return False
    
    cur = conn.cursor()
    try:
        print(f"🗑️ Начинаем полное удаление пользователя {user_id}...")
        
        # 1. Удаляем избранные адреса
        cur.execute('DELETE FROM favorite_addresses WHERE user_id = %s', (user_id,))
        
        # 2. Удаляем сообщения
        cur.execute('DELETE FROM messages WHERE user_id = %s', (user_id,))
        
        # 3. Получаем ID заказов пользователя для удаления слотов
        cur.execute('SELECT order_id FROM orders WHERE user_id = %s', (user_id,))
        orders = cur.fetchall()
        
        # 4. Удаляем занятые слоты для каждого заказа
        for order in orders:
            cur.execute('DELETE FROM busy_slots WHERE order_id = %s', (order[0],))
        
        # 5. Удаляем заказы
        cur.execute('DELETE FROM orders WHERE user_id = %s', (user_id,))
        
        # 6. Удаляем реферальные связи
        cur.execute('DELETE FROM referrals WHERE referrer_id = %s', (user_id,))
        cur.execute('DELETE FROM referrals WHERE referred_id = %s', (user_id,))
        
        # 7. Удаляем начисления и траты баллов
        cur.execute('DELETE FROM referral_earnings WHERE user_id = %s', (user_id,))
        cur.execute('DELETE FROM referral_spendings WHERE user_id = %s', (user_id,))
        
        # 8. Удаляем самого пользователя
        cur.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
        user_deleted = cur.rowcount
        
        if user_deleted > 0:
            conn.commit()
            print(f"✅ ПОЛНОЕ УДАЛЕНИЕ пользователя {user_id} завершено")
            return True
        else:
            conn.rollback()
            print(f"❌ Пользователь {user_id} не найден")
            return False
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при удалении пользователя {user_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


# =============== КОНЕЦ ФУНКЦИЙ ===============

# Алиас для обратной совместимости (НА УРОВНЕ МОДУЛЯ, без отступа)
get_user_favorites = get_user_favorite_addresses