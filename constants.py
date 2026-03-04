# constants.py
# Состояния для разговора
(WELCOME, NAME, PHONE, ADDRESS, ENTRANCE, FLOOR, APARTMENT, INTERCOM, 
 DATE, TIME, BAGS, PAYMENT_METHOD, CONFIRM_CANCEL, EDIT_PRICE, ADD_ADMIN, STATS_CUSTOM, 
 BLACKLIST_ADD, MY_ORDERS, SUPPORT_MESSAGE, CHECK_ADDRESS, NEW_ADDRESS, 
 NEW_ENTRANCE, NEW_FLOOR, NEW_APARTMENT, NEW_INTERCOM, FAVORITE_NAME,
 SELECT_FAVORITE, ORDER_DETAIL, MANAGE_FAVORITES, EDIT_FAVORITE_NAME,
 SELECT_ADDRESS, BROADCAST_MESSAGE, TEST_MODE, EDIT_WORKING_HOURS_START, 
 EDIT_WORKING_HOURS_END, SEND_MESSAGE_TO_USER, ENTER_USER_ID_FOR_MESSAGE,
 BLACKLIST_REMOVE, CONFIRM_ORDER, DIALOG_VIEW, DIALOG_REPLY, SEARCH_MESSAGES) = range(42)

# Интервалы времени (2-часовые слоты с 10:00 до 22:00)
TIME_SLOTS = [
    "10:00-12:00",
    "12:00-14:00",
    "14:00-16:00",
    "16:00-18:00",
    "18:00-20:00",
    "20:00-22:00"
]

# Способы оплаты
PAYMENT_METHODS = {
    'cash': '💵 Наличные курьеру',
    'card': '💳 Перевод на карту курьера',
    'yookassa': '💰 Онлайн-оплата (ЮKassa)'
}

# Константы для пагинации заказов
ORDERS_PER_PAGE = 5
ORDER_FILTER_ALL = 'all'
ORDER_FILTER_NEW = 'new'
ORDER_FILTER_CONFIRMED = 'confirmed'
ORDER_FILTER_COMPLETED = 'completed'
ORDER_FILTER_CANCELLED = 'cancelled'

# Названия фильтров для отображения
FILTER_NAMES = {
    ORDER_FILTER_ALL: '📋 Все заказы',
    ORDER_FILTER_NEW: '🆕 Новые',
    ORDER_FILTER_CONFIRMED: '✅ Подтверждённые',
    ORDER_FILTER_COMPLETED: '✅ Выполненные',
    ORDER_FILTER_CANCELLED: '❌ Отменённые'
}

# Эмодзи для статусов заказов
STATUS_EMOJI = {
    'new': '🆕',
    'confirmed': '✅',
    'completed': '✅',
    'cancelled': '❌'
}

# Русские названия статусов
STATUS_NAMES = {
    'new': 'Новый',
    'confirmed': 'Подтверждён',
    'completed': 'Выполнен',
    'cancelled': 'Отменён'
}
