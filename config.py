# config.py
import os
import logging
from telegram.warnings import PTBUserWarning
import warnings

# Токен бота - читаем из переменной окружения
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8730099509:AAFkz3l80CSk44xHpAarc-jq1hTEouHBuvg')

# ID главного администратора
MAIN_ADMIN_ID = 954653245

# Настройки ЮKassa (потом настроим)
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', '')
YOOKASSA_RETURN_URL = 'https://t.me/ваш_бот'

# Данные администраторов
admin_data = {
    'prices': {'1': 100, '2': 140, '3+': 150},
    'admins': [MAIN_ADMIN_ID],
    'blacklist': [],
    'blocked_users': [],
    'action_log': [],
    'test_mode': False
}

# Временное хранение данных заявки
user_data = {}

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Отключаем предупреждения
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=PTBUserWarning)
logging.getLogger("httpx").setLevel(logging.WARNING)
