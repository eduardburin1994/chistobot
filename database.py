# database.py
import os
import datetime
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

# Получаем строку подключения из переменной окружения
DATABASE_URL = os.environ.get('DATABASE_URL')

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
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT 
                message_id,
                user_id,
                CASE 
                    WHEN user_message LIKE '[ОТ АДМИНА]%' THEN TRUE 
                    ELSE FALSE 
                END as from_admin,
                user_message,
                created_at,
                status = 'replied' as is_read
            FROM messages 
            WHERE user_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        
        messages = cur.fetchall()
        return messages
    except Exception as e:
        print(f"❌ Ошибка получения диалога: {e}")
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
            cur.execute("UPDATE messages SET status = 'deleted' WHERE message_id = %s', (message_id,))
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
        cur.execute('UPDATE messages SET status = 'new' WHERE message_id = %s', (message_id,))
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
    """Получает общее количество непрочитанных сообщений"""
    conn = get_connection()
    if not conn:
        return 0
    
    cur = conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) FROM messages WHERE status = 'new'')
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
        cur.execute('SELECT COUNT(DISTINCT user_id) FROM messages')
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
