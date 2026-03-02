# database.py (добавь в самое начало, после импортов)
import os
import sqlite3
import datetime

# Определяем путь к БД в зависимости от окружения
if os.environ.get('RENDER'):
    # На Render используем /tmp (временное хранилище)
    DB_PATH = '/tmp/chistobot.db'
else:
    # Локально используем текущую папку
    DB_PATH = 'chistobot.db'

print(f"📁 База данных будет сохранена в: {DB_PATH}")

def get_connection():
    """Возвращает соединение с БД"""
    return sqlite3.connect(DB_PATH)

# И во всех функциях замени sqlite3.connect('chistobot.db') на get_connection()
# Например, в init_db():
def init_db():
    """Создание таблиц в базе данных"""
    conn = get_connection()
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей (с новыми полями)
    cursor.execute('''
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
            registered_date TIMESTAMP
        )
    ''')
    
    # Таблица сообщений между клиентами и админами
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_message TEXT,
            admin_reply TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            replied_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица заявок (обновлённая с payment_method)
    cursor.execute('''
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
            payment_method TEXT DEFAULT 'cash',
            payment_status TEXT DEFAULT 'pending',
            payment_id TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица для занятого времени
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS busy_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_date TEXT,
            slot_time TEXT,
            order_id INTEGER UNIQUE,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    ''')
    
    # Таблица черного списка
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            added_date TIMESTAMP,
            added_by INTEGER
        )
    ''')
    
    # Таблица рассылок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            message_text TEXT,
            sent_date TIMESTAMP,
            recipients_count INTEGER
        )
    ''')
    
    # Таблица избранных адресов
    cursor.execute('''
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
    
    # Создаем индекс для быстрого поиска
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_busy_slots_datetime 
        ON busy_slots (slot_date, slot_time)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована с новыми полями")

def add_user(user_id, username, first_name, last_name):
    """Добавление нового пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registered_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, datetime.datetime.now()))
    conn.commit()
    conn.close()
    print(f"✅ Пользователь {user_id} добавлен в БД")

def update_user_phone(user_id, phone):
    """Обновление телефона пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET phone = ? WHERE user_id = ?', (phone, user_id))
    conn.commit()
    conn.close()
    print(f"✅ Телефон пользователя {user_id} обновлён")

def update_user_username(user_id, username):
    """Обновление username пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
    conn.commit()
    conn.close()
    print(f"✅ Username пользователя {user_id} обновлён на @{username}")

def save_user_details(user_id, phone, street_address, entrance, floor, apartment, intercom):
    """Сохранение всех данных пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    
    # Сначала проверяем, есть ли уже запись
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        # Обновляем существующую запись
        cursor.execute('''
            UPDATE users 
            SET phone = ?, street_address = ?, entrance = ?, floor = ?, apartment = ?, intercom = ?
            WHERE user_id = ?
        ''', (phone, street_address, entrance, floor, apartment, intercom, user_id))
        print(f"✅ Данные пользователя {user_id} обновлены")
    else:
        # Создаем новую запись
        cursor.execute('''
            INSERT INTO users 
            (user_id, phone, street_address, entrance, floor, apartment, intercom, registered_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, phone, street_address, entrance, floor, apartment, intercom, datetime.datetime.now()))
        print(f"✅ Новый пользователь {user_id} сохранён в БД")
    
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    """Получение информации о пользователе по ID"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, last_name, phone, street_address, 
               entrance, floor, apartment, intercom, registered_date 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    """Получение всех пользователей"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, last_name, phone, street_address, 
               entrance, floor, apartment, intercom, registered_date 
        FROM users ORDER BY registered_date DESC
    ''')
    users = cursor.fetchall()
    conn.close()
    return users

def get_username_by_id(user_id):
    """Получение username по ID"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "неизвестно"

def save_message(user_id, message):
    """Сохранение сообщения от клиента"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (user_id, user_message, created_at, status)
        VALUES (?, ?, ?, 'new')
    ''', (user_id, message, datetime.datetime.now()))
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"✅ Сообщение #{message_id} сохранено от пользователя {user_id}")
    return message_id

def get_all_messages():
    """Получение всех сообщений для админки"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.message_id, m.user_id, u.username, u.first_name, u.phone, 
               m.user_message, m.admin_reply, m.status, m.created_at
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.user_id
        ORDER BY m.created_at DESC
    ''')
    messages = cursor.fetchall()
    conn.close()
    return messages

def reply_to_message(message_id, reply_text):
    """Ответ администратора на сообщение"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE messages 
        SET admin_reply = ?, status = 'replied', replied_at = ?
        WHERE message_id = ?
    ''', (reply_text, datetime.datetime.now(), message_id))
    conn.commit()
    conn.close()
    print(f"✅ Ответ на сообщение #{message_id} сохранен")

def get_user_orders(user_id):
    """Получение заказов пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, user_id, client_name, phone, street_address, 
               entrance, floor, apartment, intercom, order_date, order_time, 
               bags_count, price, status, created_at 
        FROM orders WHERE user_id = ? ORDER BY created_at DESC
    ''', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_order_by_id(order_id):
    """Получение заказа по ID"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, user_id, client_name, phone, street_address, 
               entrance, floor, apartment, intercom, order_date, order_time, 
               bags_count, price, status, created_at 
        FROM orders WHERE order_id = ?
    ''', (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order

def is_time_slot_free(date, time_slot):
    """Проверка, свободен ли временной слот (максимум 3 заказа)"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    
    # Считаем количество заказов на это время
    cursor.execute(
        'SELECT COUNT(*) FROM busy_slots WHERE slot_date = ? AND slot_time = ?', 
        (date, time_slot)
    )
    count = cursor.fetchone()[0]
    conn.close()
    
    # Свободно, если меньше 3 заказов
    return count < 3

def get_slot_availability(date, time_slot):
    """Получить количество свободных мест на конкретное время"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) FROM busy_slots WHERE slot_date = ? AND slot_time = ?', 
        (date, time_slot)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return 3 - count  # Возвращаем сколько мест свободно (0, 1, 2 или 3)

def create_order(user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, order_date, order_time, bags_count, price, payment_method='cash'):
    """Создание новой заявки с выбором оплаты"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('BEGIN TRANSACTION')
        
        cursor.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = ? AND slot_time = ?', 
            (order_date, order_time)
        )
        count = cursor.fetchone()[0]
        
        print(f"📊 create_order: на время {order_date} {order_time} уже {count} заказов")
        
        if count >= 3:
            conn.rollback()
            conn.close()
            return False, "На это время уже 3 заказа. Пожалуйста, выберите другое время."
        
        cursor.execute('''
            INSERT INTO orders 
            (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
             order_date, order_time, bags_count, price, payment_method, payment_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, client_name, phone, street_address, entrance, floor, apartment, intercom, 
              order_date, order_time, bags_count, price, payment_method, 'pending', datetime.datetime.now()))
        
        order_id = cursor.lastrowid
        print(f"✅ Заказ #{order_id} создан в таблице orders")
        
        cursor.execute('''
            INSERT INTO busy_slots (slot_date, slot_time, order_id)
            VALUES (?, ?, ?)
        ''', (order_date, order_time, order_id))
        
        conn.commit()
        print(f"✅ Заказ #{order_id} успешно создан для пользователя {user_id}")
        print(f"📊 На время {order_date} {order_time} теперь {count + 1}/3 заказов")
        print(f"💳 Способ оплаты: {payment_method}")
        conn.close()
        return order_id, "Успешно"
        
    except Exception as e:
        print(f"❌ Ошибка при создании заказа: {e}")
        conn.rollback()
        conn.close()
        return False, "Произошла ошибка. Пожалуйста, попробуйте ещё раз."

def get_all_orders():
    """Получение всех заявок"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, user_id, client_name, phone, street_address, 
               entrance, floor, apartment, intercom, order_date, order_time, 
               bags_count, price, status, created_at
        FROM orders ORDER BY created_at DESC
    ''')
    orders = cursor.fetchall()
    conn.close()
    return orders

def update_order_status(order_id, new_status):
    """Обновление статуса заявки"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (new_status, order_id))
    conn.commit()
    conn.close()
    print(f"✅ Статус заказа #{order_id} изменён на {new_status}")

def cancel_order(order_id):
    """Отмена заявки - освобождаем место"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    
    # Получаем информацию о слоте перед удалением
    cursor.execute('SELECT slot_date, slot_time FROM busy_slots WHERE order_id = ?', (order_id,))
    slot_info = cursor.fetchone()
    
    cursor.execute('DELETE FROM busy_slots WHERE order_id = ?', (order_id,))
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('cancelled', order_id))
    
    conn.commit()
    
    if slot_info:
        # Считаем оставшиеся заказы на это время
        cursor.execute(
            'SELECT COUNT(*) FROM busy_slots WHERE slot_date = ? AND slot_time = ?', 
            (slot_info[0], slot_info[1])
        )
        remaining = cursor.fetchone()[0]
        print(f"✅ Заказ #{order_id} отменён. На время {slot_info[0]} {slot_info[1]} осталось {remaining}/3 мест")
    
    conn.close()
    print(f"❌ Заказ #{order_id} отменён")

def update_user_address(user_id, street_address, entrance, floor, apartment, intercom):
    """Обновление адреса пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET street_address = ?, entrance = ?, floor = ?, apartment = ?, intercom = ?
        WHERE user_id = ?
    ''', (street_address, entrance, floor, apartment, intercom, user_id))
    conn.commit()
    conn.close()
    print(f"✅ Адрес пользователя {user_id} обновлён")

# =============== НОВЫЕ ФУНКЦИИ ===============

# 1. ЧЕРНЫЙ СПИСОК
def add_to_blacklist(user_id, reason=""):
    """Добавить пользователя в черный список"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO blacklist (user_id, reason, added_date, added_by)
        VALUES (?, ?, ?, ?)
    ''', (user_id, reason, datetime.datetime.now(), 0))
    conn.commit()
    conn.close()
    print(f"✅ Пользователь {user_id} добавлен в черный список")

def remove_from_blacklist(user_id):
    """Удалить пользователя из черного списка"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    print(f"✅ Пользователь {user_id} удален из черного списка")

def is_user_blacklisted(user_id):
    """Проверить, есть ли пользователь в черном списке"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM blacklist WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_blacklist():
    """Получить весь черный список"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.user_id, b.reason, b.added_date, u.username, u.first_name, u.phone
        FROM blacklist b
        LEFT JOIN users u ON b.user_id = u.user_id
        ORDER BY b.added_date DESC
    ''')
    blacklist = cursor.fetchall()
    conn.close()
    return blacklist

# 2. РАССЫЛКА
def save_broadcast(admin_id, message_text):
    """Сохранить рассылку в историю"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO broadcasts (admin_id, message_text, sent_date, recipients_count)
        VALUES (?, ?, ?, ?)
    ''', (admin_id, message_text, datetime.datetime.now(), 0))
    broadcast_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return broadcast_id

def update_broadcast_count(broadcast_id, count):
    """Обновить количество получателей"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE broadcasts SET recipients_count = ? WHERE broadcast_id = ?', (count, broadcast_id))
    conn.commit()
    conn.close()

def get_all_broadcasts():
    """Получить историю рассылок"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT broadcast_id, admin_id, message_text, sent_date, recipients_count
        FROM broadcasts ORDER BY sent_date DESC
    ''')
    broadcasts = cursor.fetchall()
    conn.close()
    return broadcasts

# 3. ИЗБРАННЫЙ АДРЕС
def save_favorite_address(user_id, address_name, street_address, entrance, floor, apartment, intercom):
    """Сохранить избранный адрес"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO favorite_addresses 
        (user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, address_name, street_address, entrance, floor, apartment, intercom, datetime.datetime.now()))
    address_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"✅ Избранный адрес #{address_id} сохранен для пользователя {user_id}")
    return address_id

def get_user_favorite_addresses(user_id):
    """Получить все избранные адреса пользователя"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT address_id, address_name, street_address, entrance, floor, apartment, intercom, created_date
        FROM favorite_addresses WHERE user_id = ? ORDER BY created_date DESC
    ''', (user_id,))
    addresses = cursor.fetchall()
    conn.close()
    return addresses

def delete_favorite_address(address_id):
    """Удалить избранный адрес"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorite_addresses WHERE address_id = ?', (address_id,))
    conn.commit()
    conn.close()
    print(f"✅ Избранный адрес #{address_id} удален")

def get_favorite_address(address_id):
    """Получить конкретный избранный адрес"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT address_id, user_id, address_name, street_address, entrance, floor, apartment, intercom, created_date
        FROM favorite_addresses WHERE address_id = ?
    ''', (address_id,))
    address = cursor.fetchone()
    conn.close()
    return address

def update_favorite_address_name(address_id, new_name):
    """Обновить название избранного адреса"""
    conn = sqlite3.connect('chistobot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE favorite_addresses SET address_name = ? WHERE address_id = ?', (new_name, address_id))
    conn.commit()
    conn.close()
    print(f"✅ Название избранного адреса #{address_id} обновлено на '{new_name}'") 

# Инициализация базы данных при запуске
if __name__ != '__main__':
    init_db()
