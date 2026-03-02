# database.py
import os
import datetime
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

# Получаем строку подключения из переменной окружения
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    """Возвращает подключение к PostgreSQL"""
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден в переменных окружения!")
        return None
    
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

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

def get_user_by_id(user_id):
    """Получение информации о пользователе по ID"""
    conn = get_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    cur.execute('''
        SELECT user_id, username, first_name, last_name, phone, street_address, 
               entrance, floor, apartment, intercom, registered_date 
        FROM users WHERE user_id = %s
    ''', (user_id,))
    
    # Для PostgreSQL используем %s вместо ?
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user
# Добавь в requirements.txt: psycopg2-binary==2.9.9

# Остальные функции (add_user, create_order и т.д.) нужно будет тоже адаптировать,
# но для начала база уже создаст таблицы
