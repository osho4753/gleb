import os
from dotenv import load_dotenv
load_dotenv()
import httpx
from typing import Optional

class TelegramManager:
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            print("⚠️ TELEGRAM_BOT_TOKEN не установлен. Уведомления отключены.")
            self.enabled = False
        else:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
            self.enabled = True
    
    async def send_message_async(self, chat_id: str, message: str):
        """
        Асинхронно отправляет сообщение в Telegram, не блокируя основной поток.
        """
        if not self.enabled or not chat_id:
            return

        url = f"{self.api_url}/sendMessage"
        params = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown' # Используем Markdown для форматирования
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=params, timeout=5.0)
                
            if response.status_code == 200:
                print(f"✅ Telegram: Сообщение отправлено в чат {chat_id}")
            else:
                print(f"❌ Telegram: Ошибка {response.status_code}. {response.text}")
        except Exception as e:
            print(f"❌ Telegram: КРИТИЧЕСКАЯ ОШИБКА отправки: {e}")
    
    def format_transaction_message(self, cash_desk_name: str, tx_data: dict, balances: dict = None) -> str:
        """
        Форматирует красивое сообщение о транзакции.
        """
        tx_type = tx_data.get("type", "")
        
        # Словарь для типов операций
        type_map = {
            "fiat_to_crypto": "Обмен (Фиат -> Крипта)",
            "crypto_to_fiat": "Обмен (Крипта -> Фиат)", 
            "fiat_to_fiat": "Обмен (Фиат -> Фиат)",
            "deposit": "Пополнение кассы",
            "withdrawal": "Снятие из кассы"
        }
        type_ru = type_map.get(tx_type, tx_type)
        
        icon = "🔄"
        if tx_type == "deposit": icon = "✅"
        if tx_type == "withdrawal": icon = "📤"

        message = f"*{icon} {type_ru} ({cash_desk_name})*\n\n"
        
        if tx_type in ["deposit", "withdrawal"]:
            amount = abs(tx_data.get("amount_from", 0))
            asset = tx_data.get("from_asset", "")
            message += f"Сумма: *{amount:.2f} {asset}*\n"
            if balances and asset in balances:
                message += f"Баланс {asset}: *{balances[asset]:.2f}*\n"
        else: # Обмен
            message += f"Принял: *{tx_data.get('amount_from', 0):.2f} {tx_data.get('from_asset', '')}*\n"
            message += f"Выдал: *{tx_data.get('amount_to_final', 0):.2f} {tx_data.get('to_asset', '')}*\n"
            message += f"Курс: `{tx_data.get('rate_used', 0)}`\n"
            
            profit = tx_data.get('profit', 0)
            if profit:
                profit_currency = tx_data.get('profit_currency', '')
                profit_icon = "📈" if profit > 0 else "📉"
                message += f"Прибыль: *{profit:.2f} {profit_currency}* {profit_icon}\n"

        note = tx_data.get("note")
        if note:
            message += f"\n_Примечание: {note}_"
            
        return message

    def format_undo_message(self, cash_desk_name: str, snapshot_desc: str) -> str:
        """Форматирует сообщение об отмене."""
        return f"*{'❌'} Отмена операции ({cash_desk_name})*\n\n" \
               f"Восстановлено состояние до:\n_{snapshot_desc}_"

    def format_sync_message(self, cash_desk_name: str) -> str:
        """Форматирует сообщение о ручной синхронизации."""
        return f"*{'🔄'} Ручная синхронизация*\n\n" \
               f"Данные для филиала *{cash_desk_name}* были полностью синхронизированы с Google Sheets."

# Создаем глобальный экземпляр
telegram_manager = TelegramManager()