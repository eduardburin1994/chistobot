import time
from collections import defaultdict
from datetime import datetime, timedelta
import database as db

class AntiFlood:
    """Защита от спама"""
    
    def __init__(self):
        # Храним историю сообщений пользователей
        self.user_messages = defaultdict(list)
        self.warnings = defaultdict(int)
        
        # Настройки
        self.MESSAGE_LIMIT = 5  # макс сообщений за период
        self.TIME_WINDOW = 60   # период в секундах (1 минута)
        self.COOLDOWN = 1800    # время блокировки (30 минут)
        self.MAX_WARNINGS = 3    # предупреждений до бана
    
    def is_spam(self, user_id):
        """
        Проверяет, является ли сообщение спамом
        Возвращает: (True/False, причина, время ожидания)
        """
        now = time.time()
        
        # Очищаем старые сообщения (старше TIME_WINDOW)
        self.user_messages[user_id] = [
            msg_time for msg_time in self.user_messages[user_id]
            if now - msg_time < self.TIME_WINDOW
        ]
        
        # Добавляем новое сообщение
        self.user_messages[user_id].append(now)
        
        # Проверяем количество за последний период
        msg_count = len(self.user_messages[user_id])
        
        if msg_count > self.MESSAGE_LIMIT:
            # Превышение лимита
            self.warnings[user_id] += 1
            
            # Если предупреждений слишком много - в бан
            if self.warnings[user_id] >= self.MAX_WARNINGS:
                db.add_to_blacklist(user_id, "Автоматический бан за флуд")
                return True, "BANNED", 0
            
            # Иначе просто блокируем на время
            return True, "FLOOD", self.COOLDOWN
        
        return False, "OK", 0
    
    def get_wait_time(self, user_id):
        """Сколько осталось ждать до следующего сообщения"""
        if not self.user_messages[user_id]:
            return 0
        
        now = time.time()
        oldest = min(self.user_messages[user_id])
        time_passed = now - oldest
        
        if time_passed < self.TIME_WINDOW:
            return int(self.TIME_WINDOW - time_passed)
        return 0

class RateLimiter:
    """Ограничитель частоты действий"""
    
    def __init__(self, limit=1, period=1800):  # 1 действие в 30 минут
        self.limit = limit
        self.period = period
        self.user_actions = defaultdict(list)
    
    def can_do_action(self, user_id, action_type):
        """
        Проверяет, может ли пользователь выполнить действие
        action_type: 'order', 'message', 'referral' и т.д.
        """
        key = f"{user_id}:{action_type}"
        now = datetime.now()
        
        # Очищаем старые действия
        self.user_actions[key] = [
            dt for dt in self.user_actions[key]
            if now - dt < timedelta(seconds=self.period)
        ]
        
        # Проверяем лимит
        if len(self.user_actions[key]) >= self.limit:
            oldest = min(self.user_actions[key])
            wait_seconds = (oldest + timedelta(seconds=self.period) - now).total_seconds()
            return False, round(wait_seconds)
        
        # Разрешаем действие
        self.user_actions[key].append(now)
        return True, 0

# Создаём глобальные экземпляры
antiflood = AntiFlood()
rate_limiter = RateLimiter(limit=1, period=1800)  # 1 действие в 30 минут