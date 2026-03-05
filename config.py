# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен бота - теперь читается из .env
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8730099509:AAF83M1EjAqwB7FErvaRXJUPKaP-1kREv8I')
import os
import logging
from telegram.warnings import PTBUserWarning
import warnings
import database as db

# Токен бота - читаем из переменной окружения (ВАЖНО: имя должно совпадать с Render!)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8730099509:AAF83M1EjAqwB7FErvaRXJUPKaP-1kREv8I')

# Пароль для курьеров (можно вынести в переменные окружения)
COURIER_PASSWORD = os.environ.get('COURIER_PASSWORD', 'courier123')

# ID главного администратора
MAIN_ADMIN_ID = 954653245

# Настройки ЮKassa (потом настроим)
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', '')
YOOKASSA_RETURN_URL = 'https://t.me/ваш_бот'

# Данные администраторов
admin_data = {
    'prices': db.load_prices(),  # ← загружаем из БД
    'admins': [MAIN_ADMIN_ID],
    'blacklist': [],
    'blocked_users': [],
    'action_log': [],
    'test_mode': False
}

# Время работы бота (можно менять через админку)
WORK_HOURS = {
    'start': 10,  # 10:00
    'end': 22     # 22:00
}

# Временное хранение данных заявки
user_data = {}

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Отключаем предупреждения
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=PTBUserWarning)
logging.getLogger("httpx").setLevel(logging.WARNING)
