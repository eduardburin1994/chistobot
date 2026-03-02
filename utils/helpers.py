# utils/helpers.py
from config import admin_data

def calculate_price(bags):
    """Расчет цены по количеству мешков"""
    if bags == 1:
        return admin_data['prices']['1']  # 100 ₽ за 1 мешок
    elif bags == 2:
        return admin_data['prices']['2']  # 140 ₽ за 2 мешка (всего)
    else:
        # Для 3 и более мешков - фиксированная цена 150 ₽ за все
        return admin_data['prices']['3+']  # 150 ₽ за 3+ мешка (всего)
