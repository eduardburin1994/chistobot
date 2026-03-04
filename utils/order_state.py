import database as db
import datetime
import json

class OrderStateManager:
    """Менеджер состояний заказов (сохраняет в БД)"""
    
    @staticmethod
    def save_state(user_id, state, data):
        """Сохраняет состояние заказа в БД"""
        conn = db.get_connection()
        if not conn:
            return
        
        cur = conn.cursor()
        try:
            # Создаём таблицу, если её нет
            cur.execute('''
                CREATE TABLE IF NOT EXISTS order_states (
                    user_id BIGINT PRIMARY KEY,
                    state INTEGER,
                    data TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Сохраняем данные в JSON
            data_json = json.dumps(data, ensure_ascii=False, default=str)
            now = datetime.datetime.now() + datetime.timedelta(hours=3)
            
            cur.execute('''
                INSERT INTO order_states (user_id, state, data, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET state = EXCLUDED.state,
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at
            ''', (user_id, state, data_json, now))
            
            conn.commit()
            print(f"💾 Состояние заказа пользователя {user_id} сохранено (шаг {state})")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения состояния: {e}")
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def load_state(user_id):
        """Загружает состояние заказа из БД"""
        conn = db.get_connection()
        if not conn:
            return None, {}
        
        cur = conn.cursor()
        try:
            cur.execute('''
                SELECT state, data FROM order_states
                WHERE user_id = %s
            ''', (user_id,))
            
            result = cur.fetchone()
            if result:
                state = result[0]
                data = json.loads(result[1])
                print(f"📂 Загружено состояние пользователя {user_id} (шаг {state})")
                return state, data
            return None, {}
            
        except Exception as e:
            print(f"❌ Ошибка загрузки состояния: {e}")
            return None, {}
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def clear_state(user_id):
        """Очищает состояние после завершения заказа"""
        conn = db.get_connection()
        if not conn:
            return
        
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM order_states WHERE user_id = %s', (user_id,))
            conn.commit()
            print(f"🗑️ Состояние пользователя {user_id} очищено")
        except Exception as e:
            print(f"❌ Ошибка очистки состояния: {e}")
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def is_state_expired(user_id, hours=24):
        """Проверяет, не устарело ли состояние (больше 24 часов)"""
        conn = db.get_connection()
        if not conn:
            return True
        
        cur = conn.cursor()
        try:
            cur.execute('''
                SELECT updated_at FROM order_states
                WHERE user_id = %s
            ''', (user_id,))
            
            result = cur.fetchone()
            if not result:
                return True
            
            now = datetime.datetime.now() + datetime.timedelta(hours=3)
            age = (now - result[0]).total_seconds() / 3600
            return age > hours
            
        except Exception:
            return True
        finally:
            cur.close()
            conn.close()

# Создаём глобальный экземпляр
order_state = OrderStateManager()