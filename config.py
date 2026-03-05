# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (В САМОМ НАЧАЛЕ!)
load_dotenv()

# Токен бота - читаем из .env через os.getenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Пароль для курьеров
COURIER_PASSWORD = os.getenv('COURIER_PASSWORD', 'courier123')

# ID главного администратора
MAIN_ADMIN_ID = 954653245

# Настройки ЮKassa
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')
YOOKASSA_RETURN_URL = 'https://t.me/ваш_бот'

import logging
import warnings
from telegram.warnings import PTBUserWarning

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Отключаем предупреждения
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=PTBUserWarning)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Импортируем базу данных ПОСЛЕ загрузки переменных
import database as db

# Данные администраторов
admin_data = {
    'prices': db.load_prices(),
    'admins': [MAIN_ADMIN_ID],
    'blacklist': [],
    'blocked_users': [],
    'action_log': [],
    'test_mode': False
}

# Время работы бота
WORK_HOURS = {
    'start': 10,
    'end': 22
}

# Временное хранение данных заявки
user_data = {}