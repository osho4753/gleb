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
            
            # Форматируем данные для добавления
            row = [
                date_str,                                                    # Дата/Время
                type_ru,                                                     # Тип операции
                transaction_data.get("from_asset", ""),                     # Принял
                float(transaction_data.get("amount_from", 0)),              # Количество
                transaction_data.get("to_asset", ""),                       # Выдал
                float(transaction_data.get("amount_to_final", 0)) if transaction_data.get("amount_to_final") else float(transaction_data.get("amount_to", 0)),  # Количество
                float(transaction_data.get("rate_used", 0)) if transaction_data.get("rate_used") else "",  # Курс
                float(transaction_data.get("fee_percent", 0)) if transaction_data.get("fee_percent") else "",  # Комиссия %
                float(transaction_data.get("realized_profit", 0)) if transaction_data.get("realized_profit") else "",  # Прибыль
                transaction_data.get("realized_profit_currency", ""),       # Валюта прибыли
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
                
                # Обновляем данные
                row = [
                    date_str,                                                    # Дата/Время
                    type_ru,                                                     # Тип операции
                    transaction_data.get("from_asset", ""),                     # Принял
                    float(transaction_data.get("amount_from", 0)),              # Количество
                    transaction_data.get("to_asset", ""),                       # Выдал
                    float(transaction_data.get("amount_to_final", 0)) if transaction_data.get("amount_to_final") else float(transaction_data.get("amount_to", 0)),  # Количество
                    float(transaction_data.get("rate_used", 0)) if transaction_data.get("rate_used") else "",  # Курс
                    float(transaction_data.get("fee_percent", 0)) if transaction_data.get("fee_percent") else "",  # Комиссия %
                    float(transaction_data.get("realized_profit", 0)) if transaction_data.get("realized_profit") else "",  # Прибыль
                    transaction_data.get("realized_profit_currency", ""),       # Валюта прибыли
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


# Глобальный экземпляр
sheets_manager = GoogleSheetsManager()
