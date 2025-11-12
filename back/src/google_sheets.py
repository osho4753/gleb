"""
Google Sheets Integration
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional
import os
from .constants import (
    GOOGLE_SHEETS_ENABLED,
    GOOGLE_SHEETS_CREDENTIALS_PATH,
    GOOGLE_SHEETS_SPREADSHEET_ID
)

class GoogleSheetsManager:
    """Менеджер для работы с Google Sheets"""
    
    def __init__(self):
        self.enabled = GOOGLE_SHEETS_ENABLED
        self.client = None
        self.spreadsheet = None
        
        if self.enabled:
            try:
                self._init_client()
            except Exception as e:
                print(f"⚠️ Google Sheets initialization failed: {e}")
                self.enabled = False
    
    def _init_client(self):
        """Инициализация Google Sheets клиента"""
        if not GOOGLE_SHEETS_SPREADSHEET_ID:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID not set in environment")
        
        # Настройка credentials
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Проверяем наличие JSON в переменной окружения (для Render/production)
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        
        if credentials_json:
            # Используем JSON из переменной окружения
            import json
            creds_dict = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            # Используем файл (для локальной разработки)
            if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_PATH):
                raise FileNotFoundError(f"Credentials file not found: {GOOGLE_SHEETS_CREDENTIALS_PATH}")
            creds = Credentials.from_service_account_file(
                GOOGLE_SHEETS_CREDENTIALS_PATH,
                scopes=scopes
            )
        
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
        
        print(f"✅ Google Sheets connected: {self.spreadsheet.title}")
    
    def add_transaction(self, transaction_data: dict):
        """
        Добавляет транзакцию в Google Sheets
        
        Args:
            transaction_data: Данные транзакции из MongoDB
        """
        if not self.enabled:
            return
        
        try:
            # Получаем первый лист (или создаем если нет)
            try:
                worksheet = self.spreadsheet.get_worksheet(0)
            except:
                worksheet = self.spreadsheet.add_worksheet(title="Transactions", rows=1000, cols=15)
            
            # Проверяем есть ли заголовки
            if worksheet.row_count == 0 or not worksheet.row_values(1):
                headers = [
                    "Дата/Время",
                    "Тип операции",
                    "Принял",
                    "Количество",
                    "Выдал",
                    "Количество",
                    "Курс",
                    "Комиссия %",
                    "Прибыль",
                    "Валюта прибыли",
                    "Примечание",
                    "ID"  # Скрытая колонка для поиска
                ]
                worksheet.append_row(headers)
                # Скрываем колонку L (ID)
                try:
                    worksheet.hide_columns(12, 12)
                except:
                    pass
            
            # Форматируем дату/время в читаемый формат
            created_at = transaction_data.get("created_at")
            if isinstance(created_at, datetime):
                date_str = created_at.strftime("%d.%m.%Y %H:%M:%S")
            else:
                date_str = str(created_at) if created_at else ""
            
            # Определяем тип операции на русском
            tx_type = transaction_data.get("type", "")
            type_map = {
                "fiat_to_crypto": "Фиат → Крипта",
                "crypto_to_fiat": "Крипта → Фиат",
                "fiat_to_fiat": "Фиат → Фиат",
                "deposit": "Пополнение",
                "withdrawal": "Снятие"
            }
            type_ru = type_map.get(tx_type, tx_type)
            
            # Для fiat_to_fiat меняем местами "Принял" и "Выдал"
            # Логика: клиент приносит from_asset, мы выдаём to_asset
            if tx_type == "fiat_to_fiat":
                received_asset = transaction_data.get("to_asset", "")
                received_amount = float(transaction_data.get("amount_to_final", 0))
                given_asset = transaction_data.get("from_asset", "")
                given_amount = float(transaction_data.get("amount_from", 0)) if transaction_data.get("amount_from") else float(transaction_data.get("amount_to", 0))
            else:
                # Для остальных типов оставляем как есть
                received_asset = transaction_data.get("from_asset", "")
                received_amount = float(transaction_data.get("amount_from", 0))
                given_asset = transaction_data.get("to_asset", "")
                given_amount = float(transaction_data.get("amount_to_final", 0)) if transaction_data.get("amount_to_final") else float(transaction_data.get("amount_to", 0))
            
            # Форматируем данные для добавления
            row = [
                date_str,                                                    # Дата/Время
                type_ru,                                                     # Тип операции
                received_asset,                                              # Принял
                received_amount,                                             # Количество
                given_asset,                                                 # Выдал
                given_amount,                                                # Количество
                float(transaction_data.get("rate_used", 0)) if transaction_data.get("rate_used") else "",  # Курс
                float(transaction_data.get("fee_percent", 0)) if transaction_data.get("fee_percent") else "",  # Комиссия %
                float(transaction_data.get("realized_profit", 0)) if transaction_data.get("realized_profit") else "",  # Прибыль
                transaction_data.get("profit_currency", ""),                # Валюта прибыли
                transaction_data.get("note", ""),                           # Примечание
                str(transaction_data.get("_id", ""))                        # ID (скрытая колонка)
            ]
            
            # Добавляем строку
            worksheet.append_row(row)
            print(f"✅ Transaction added to Google Sheets: {transaction_data.get('_id')}")
            
        except Exception as e:
            print(f"❌ Failed to add transaction to Google Sheets: {e}")
    
    def update_transaction(self, transaction_id: str, transaction_data: dict):
        """
        Обновляет транзакцию в Google Sheets
        
        Args:
            transaction_id: ID транзакции
            transaction_data: Обновленные данные
        """
        if not self.enabled:
            return
        
        try:
            worksheet = self.spreadsheet.get_worksheet(0)
            
            # Ищем строку с этим ID
            cell = worksheet.find(str(transaction_id))
            if cell:
                row_number = cell.row
                
                # Форматируем дату/время в читаемый формат
                created_at = transaction_data.get("created_at")
                if isinstance(created_at, datetime):
                    date_str = created_at.strftime("%d.%m.%Y %H:%M:%S")
                else:
                    date_str = str(created_at) if created_at else ""
                
                # Определяем тип операции на русском
                tx_type = transaction_data.get("type", "")
                type_map = {
                    "fiat_to_crypto": "Фиат → Крипта",
                    "crypto_to_fiat": "Крипта → Фиат",
                    "fiat_to_fiat": "Фиат → Фиат",
                    "deposit": "Пополнение",
                    "withdrawal": "Снятие"
                }
                type_ru = type_map.get(tx_type, tx_type)
                
                # Для fiat_to_fiat меняем местами "Принял" и "Выдал"
                # Логика: клиент приносит from_asset, мы выдаём to_asset
                if tx_type == "fiat_to_fiat":
                    received_asset = transaction_data.get("from_asset", "")
                    received_amount = float(transaction_data.get("amount_from", 0))
                    given_asset = transaction_data.get("to_asset", "")
                    given_amount = float(transaction_data.get("amount_to_final", 0)) if transaction_data.get("amount_to_final") else float(transaction_data.get("amount_to", 0))
                else:
                    # Для остальных типов оставляем как есть
                    received_asset = transaction_data.get("from_asset", "")
                    received_amount = float(transaction_data.get("amount_from", 0))
                    given_asset = transaction_data.get("to_asset", "")
                    given_amount = float(transaction_data.get("amount_to_final", 0)) if transaction_data.get("amount_to_final") else float(transaction_data.get("amount_to", 0))
                
                # Обновляем данные
                row = [
                    date_str,                                                    # Дата/Время
                    type_ru,                                                     # Тип операции
                    received_asset,                                              # Принял
                    received_amount,                                             # Количество
                    given_asset,                                                 # Выдал
                    given_amount,                                                # Количество
                    float(transaction_data.get("rate_used", 0)) if transaction_data.get("rate_used") else "",  # Курс
                    float(transaction_data.get("fee_percent", 0)) if transaction_data.get("fee_percent") else "",  # Комиссия %
                    float(transaction_data.get("realized_profit", 0)) if transaction_data.get("realized_profit") else "",  # Прибыль
                    transaction_data.get("profit_currency", ""),                # Валюта прибыли
                    transaction_data.get("note", ""),                           # Примечание
                    str(transaction_id)                                         # ID (скрытая колонка)
                ]
                
                worksheet.delete_rows(row_number)
                worksheet.insert_row(row, row_number)
                print(f"✅ Transaction updated in Google Sheets: {transaction_id}")
                
        except Exception as e:
            print(f"❌ Failed to update transaction in Google Sheets: {e}")
    
    def delete_transaction(self, transaction_id: str):
        """
        Удаляет транзакцию из Google Sheets
        
        Args:
            transaction_id: ID транзакции
        """
        if not self.enabled:
            return
        
        try:
            worksheet = self.spreadsheet.get_worksheet(0)
            
            # Ищем строку с этим ID
            cell = worksheet.find(str(transaction_id))
            if cell:
                worksheet.delete_rows(cell.row)
                print(f"✅ Transaction deleted from Google Sheets: {transaction_id}")
                
        except Exception as e:
            print(f"❌ Failed to delete transaction from Google Sheets: {e}")
    
    def clear_all_transactions(self):
        """
        Удаляет все строки транзакций из Google Sheets (оставляет только заголовок)
        """
        if not self.enabled:
            return
        
        try:
            worksheet = self.spreadsheet.get_worksheet(0)
            
            # Получаем количество строк
            row_count = worksheet.row_count
            
            # Если есть строки кроме заголовка, удаляем их
            if row_count > 1:
                worksheet.delete_rows(2, row_count)
                print(f"✅ Cleared {row_count - 1} transaction rows from Google Sheets")
            else:
                print("✅ Google Sheets already empty (only headers)")
                
        except Exception as e:
            print(f"❌ Failed to clear transactions from Google Sheets: {e}")
    
    def update_summary_sheet(self, cash_status: dict, realized_profits: dict):
        """
        Обновляет лист "Касса и Прибыль" с текущим состоянием
        
        Args:
            cash_status: Словарь {валюта: баланс}
            realized_profits: Словарь {валюта: прибыль}
        """
        if not self.enabled:
            return
        
        try:
            # Получаем или создаем лист "Касса и Прибыль"
            try:
                summary_sheet = self.spreadsheet.worksheet("Касса и Прибыль")
            except:
                summary_sheet = self.spreadsheet.add_worksheet(title="Касса и Прибыль", rows=50, cols=10)
            
            # Очищаем лист
            summary_sheet.clear()
            
            # Текущая дата/время обновления
            update_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            # Заголовок
            summary_sheet.update('A1', [[f'Последнее обновление: {update_time}']])
            
            # --- Секция КАССА ---
            summary_sheet.update('A3', [['СОСТОЯНИЕ КАССЫ']])
            summary_sheet.update('A4:B4', [['Валюта', 'Баланс']])
            
            # Данные кассы
            cash_rows = []
            for currency, balance in sorted(cash_status.items()):
                cash_rows.append([currency, float(balance)])
            
            if cash_rows:
                summary_sheet.update(f'A5:B{4 + len(cash_rows)}', cash_rows)
            
            # --- Секция ПРИБЫЛЬ ---
            profit_start_row = 5 + len(cash_rows) + 2
            summary_sheet.update(f'A{profit_start_row}', [['РЕАЛИЗОВАННАЯ ПРИБЫЛЬ']])
            summary_sheet.update(f'A{profit_start_row + 1}:B{profit_start_row + 1}', [['Валюта', 'Прибыль']])
            
            # Данные прибыли
            profit_rows = []
            for currency, profit in sorted(realized_profits.items()):
                if currency:  # Исключаем пустые валюты
                    profit_rows.append([currency, float(profit)])
            
            if profit_rows:
                summary_sheet.update(f'A{profit_start_row + 2}:B{profit_start_row + 1 + len(profit_rows)}', profit_rows)
            
            # Форматирование
            # Жирный шрифт для заголовков
            summary_sheet.format('A1', {'textFormat': {'bold': True, 'fontSize': 12}})
            summary_sheet.format('A3', {'textFormat': {'bold': True, 'fontSize': 11}})
            summary_sheet.format(f'A{profit_start_row}', {'textFormat': {'bold': True, 'fontSize': 11}})
            summary_sheet.format('A4:B4', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}})
            summary_sheet.format(f'A{profit_start_row + 1}:B{profit_start_row + 1}', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}})
            
            # Попытка установить ширину колонок (опционально)
            try:
                summary_sheet.columns_auto_resize(0, 2)  # Автоматический размер для колонок A и B
            except:
                pass  # Игнорируем, если метод не поддерживается
            
            print(f"✅ Summary sheet updated successfully")
            
        except Exception as e:
            print(f"❌ Failed to update summary sheet: {e}")


# Глобальный экземпляр
sheets_manager = GoogleSheetsManager()
