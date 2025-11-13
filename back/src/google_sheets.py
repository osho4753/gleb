"""
Google Sheets Integration с поддержкой множественных таблиц
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
import json
from .constants import (
    GOOGLE_SHEETS_ENABLED,
    GOOGLE_SHEETS_CREDENTIALS_PATH
)
from .db import db

class GoogleSheetsManager:
    """Менеджер для работы с Google Sheets с поддержкой множественных таблиц"""
    
    def __init__(self):
        self.enabled = GOOGLE_SHEETS_ENABLED
        self.client = None
        
        if self.enabled:
            try:
                self._init_client()
            except Exception as e:
                print(f"⚠️ Google Sheets initialization failed: {e}")
                self.enabled = False
    
    def _init_client(self):
        """Инициализация Google Sheets клиента"""
        # Настройка credentials
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Проверяем наличие JSON в переменной окружения (для Render/production)
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        
        if credentials_json:
            # Используем JSON из переменной окружения
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
        print(f"✅ Google Sheets client initialized")
    
    def get_tenant_settings(self, tenant_id: str) -> Optional[dict]:
        """Получает настройки Google Sheets для конкретного tenant"""
        return db.google_sheets_settings.find_one({"tenant_id": tenant_id})
    
    def is_enabled_for_tenant(self, tenant_id: str) -> bool:
        """Проверяет, включена ли интеграция для конкретного tenant"""
        if not self.enabled:
            return False
        
        settings = self.get_tenant_settings(tenant_id)
        return settings and settings.get("is_enabled", False)
    
    def test_spreadsheet_access(self, spreadsheet_id: str):
        """Проверяет доступ к таблице"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            # Пробуем получить список листов
            worksheets = spreadsheet.worksheets()
            return True
        except Exception as e:
            raise Exception(f"Cannot access spreadsheet: {str(e)}")
    
    def setup_tenant_spreadsheet(self, spreadsheet_id: str, tenant_id: str):
        """Инициализирует таблицу для нового tenant с нужными листами"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Создаем лист транзакций
            transactions_sheet_name = "Транзакции"
            try:
                transactions_sheet = spreadsheet.worksheet(transactions_sheet_name)
            except gspread.WorksheetNotFound:
                transactions_sheet = spreadsheet.add_worksheet(
                    title=transactions_sheet_name, 
                    rows=1000, 
                    cols=20
                )
                # Добавляем заголовки в новом формате плюс время обновления
                headers = [
                    "Дата/Время", "Тип операции", "Принял", "Количество", 
                    "Выдал", "Количество", "Курс", "Комиссия %", 
                    "Прибыль", "Валюта прибыли", "Примечание", "Id",
                    "", "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
                ]
                # Используем update вместо append_row для более надежной записи
                transactions_sheet.update('A1:O1', [headers], value_input_option='RAW')
            
            # Создаем лист кассы и прибыли
            summary_sheet_name = "Касса и Прибыль"
            try:
                summary_sheet = spreadsheet.worksheet(summary_sheet_name)
            except gspread.WorksheetNotFound:
                summary_sheet = spreadsheet.add_worksheet(
                    title=summary_sheet_name, 
                    rows=100, 
                    cols=10
                )
                # Создаем структуру с разделами
                initial_data = [
                    ["СОСТОЯНИЕ КАССЫ", ""],
                    ["Валюта", "Баланс"]
                ]
                summary_sheet.update("A1:B2", initial_data, value_input_option='RAW')
                
                # Добавляем заголовки для прибыли
                profit_headers = [
                    ["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ", ""],
                    ["Валюта", "Прибыль"]
                ]
                summary_sheet.update("A15:B16", profit_headers, value_input_option='RAW')
            
            # Удаляем дефолтный лист "Лист1" / "Sheet1", если он существует и пустой
            try:
                all_worksheets = spreadsheet.worksheets()
                default_sheet_names = ["Лист1", "Sheet1", "Лист 1", "Sheet 1"]
                
                for worksheet in all_worksheets:
                    if worksheet.title in default_sheet_names:
                        # Проверяем что лист пустой (только если у нас есть другие листы)
                        if len(all_worksheets) > 1:
                            try:
                                # Проверяем содержимое листа
                                values = worksheet.get_all_values()
                                # Если лист пустой или содержит только пустые строки
                                if not values or all(not any(cell.strip() for cell in row) for row in values):
                                    spreadsheet.del_worksheet(worksheet)
                                    print(f"✅ Removed empty default sheet: {worksheet.title}")
                            except Exception as e:
                                print(f"⚠️ Could not remove default sheet {worksheet.title}: {e}")
            except Exception as e:
                print(f"⚠️ Error while cleaning up default sheets: {e}")
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to setup spreadsheet: {str(e)}")
    
    def _format_transaction_row(self, transaction_data: dict) -> List[Any]:
        """Форматирует данные транзакции для записи в таблицу в новом формате"""
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
        
        # Новый формат: Дата/Время, Тип операции, Принял, Количество, Выдал, Количество, Курс, Комиссия %, Прибыль, Валюта прибыли, Примечание, Id
        row = [
            date_str,                                        # Дата/Время
            type_ru,                                         # Тип операции
            transaction_data.get("from_asset", ""),          # Принял (валюта)
            transaction_data.get("amount_from", 0),          # Количество (принял)
            transaction_data.get("to_asset", ""),            # Выдал (валюта)
            transaction_data.get("amount_to_final", 0),      # Количество (выдал)
            transaction_data.get("rate_used", 0),            # Курс
            transaction_data.get("fee_percent", 0),          # Комиссия %
            transaction_data.get("profit", 0),               # Прибыль
            transaction_data.get("profit_currency", ""),     # Валюта прибыли
            transaction_data.get("note", ""),                # Примечание
            str(transaction_data.get("_id", ""))             # Id
        ]
        
        # Убеждаемся что все None значения заменены на пустые строки или нули
        return [str(cell) if cell is not None else "" for cell in row]
    
    def sync_all_data(self, spreadsheet_id: str, transactions: List[Dict], cash_status: Dict, realized_profits: Dict, tenant_id: str):
        """Полная синхронизация всех данных с Google Sheets с двумя листами"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # 1. Синхронизируем транзакции
            transactions_sheet = spreadsheet.worksheet("Транзакции")
            
            # Очищаем весь лист
            transactions_sheet.clear()
            
            # Подготавливаем все данные для записи одним запросом
            all_data = []
            
            # Заголовки в новом формате
            headers = [
                "Дата/Время", "Тип операции", "Принял", "Количество", 
                "Выдал", "Количество", "Курс", "Комиссия %", 
                "Прибыль", "Валюта прибыли", "Примечание", "Id",
                "", "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            all_data.append(headers)
            
            # Добавляем все транзакции
            for transaction in transactions:
                row_data = self._format_transaction_row(transaction)
                # Дополняем до 15 колонок (чтобы соответствовать заголовкам)
                while len(row_data) < 15:
                    row_data.append("")
                all_data.append(row_data)
            
            # Записываем все данные одним пакетом
            if all_data:
                # Убеждаемся что все None значения заменены на пустые строки
                clean_data = []
                for row in all_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_data.append(clean_row)
                
                range_name = f"A1:O{len(clean_data)}"
                transactions_sheet.update(range_name, clean_data, value_input_option='RAW')
            
            # 2. Синхронизируем касса и прибыль
            summary_sheet = spreadsheet.worksheet("Касса и Прибыль")
            
            # Очищаем лист
            summary_sheet.clear()
            
            # Подготавливаем данные для сводного листа
            summary_data = []
            
            # Секция кассы
            summary_data.append(["СОСТОЯНИЕ КАССЫ"])
            summary_data.append(["Валюта", "Баланс"])
            
            for currency, balance in cash_status.items():
                summary_data.append([currency, balance])
            
            # Пустая строка
            summary_data.append([""])
            
            # Секция прибыли
            summary_data.append(["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ"])
            summary_data.append(["Валюта", "Прибыль"])
            
            for currency, profit in realized_profits.items():
                summary_data.append([currency, profit])
            
            # Записываем все данные одним пакетом
            if summary_data:
                # Убеждаемся что все None значения заменены на пустые строки
                clean_summary_data = []
                for row in summary_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_summary_data.append(clean_row)
                
                range_name = f"A1:B{len(clean_summary_data)}"
                summary_sheet.update(range_name, clean_summary_data, value_input_option='RAW')
            
            print(f"✅ All data synced for tenant {tenant_id}: {len(transactions)} transactions, {len(cash_status)} cash items, {len(realized_profits)} profit items")
            
        except Exception as e:
            raise Exception(f"Failed to sync all data: {str(e)}")
    
    def add_transaction(self, transaction_data: dict, tenant_id: str = None):
        """
        Добавляет транзакцию в Google Sheets для конкретного tenant
        
        Args:
            transaction_data: Данные транзакции из MongoDB
            tenant_id: ID tenant'а для изоляции данных
        """
        if not tenant_id:
            print(f"⚠️ No tenant_id provided for Google Sheets transaction")
            return
            
        if not self.is_enabled_for_tenant(tenant_id):
            print(f"⚠️ Google Sheets not enabled for tenant {tenant_id}")
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            print(f"⚠️ No Google Sheets settings found for tenant {tenant_id}")
            return
        
        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            worksheet = spreadsheet.worksheet("Транзакции")
            
            row_data = self._format_transaction_row(transaction_data)
            worksheet.append_row(row_data)
            
            # Обновляем время последнего обновления (в колонке O, первая строка)
            try:
                worksheet.update("O1", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S"))
            except Exception as e:
                print(f"Warning: Could not update timestamp: {e}")
            
            print(f"✅ Transaction added to Google Sheets for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to add transaction to Google Sheets for tenant {tenant_id}: {e}")
    
    def update_cash_and_profits(self, cash_status: dict, realized_profits: dict, tenant_id: str = None, spreadsheet_id: str = None):
        """
        Обновляет данные кассы и прибыли на отдельном листе
        
        Args:
            cash_status: Словарь {валюта: баланс}
            realized_profits: Словарь {валюта: прибыль}
            tenant_id: ID tenant'а
            spreadsheet_id: ID таблицы (опционально, если не передан - получаем из настроек)
        """
        if not tenant_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        # Получаем ID таблицы
        if not spreadsheet_id:
            settings = self.get_tenant_settings(tenant_id)
            if not settings or not settings.get("spreadsheet_id"):
                return
            spreadsheet_id = settings["spreadsheet_id"]
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            summary_sheet = spreadsheet.worksheet("Касса и Прибыль")
            
            # Очищаем весь лист
            summary_sheet.clear()
            
            # Подготавливаем данные для записи одним пакетом
            summary_data = []
            
            # Секция кассы
            summary_data.append(["СОСТОЯНИЕ КАССЫ"])
            summary_data.append(["Валюта", "Баланс"])
            
            for currency, balance in cash_status.items():
                summary_data.append([currency, balance])
            
            # Пустая строка
            summary_data.append([""])
            
            # Секция прибыли
            summary_data.append(["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ"])
            summary_data.append(["Валюта", "Прибыль"])
            
            for currency, profit in realized_profits.items():
                summary_data.append([currency, profit])
            
            # Записываем все данные одним пакетом
            if summary_data:
                # Убеждаемся что все None значения заменены на пустые строки
                clean_summary_data = []
                for row in summary_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_summary_data.append(clean_row)
                
                range_name = f"A1:B{len(clean_summary_data)}"
                summary_sheet.update(range_name, clean_summary_data, value_input_option='RAW')
            
            print(f"✅ Cash and profits updated for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to update cash and profits for tenant {tenant_id}: {e}")
    
    def update_transaction(self, transaction_id: str, updated_data: dict, tenant_id: str = None):
        """
        Обновляет существующую транзакцию в Google Sheets для конкретного tenant
        
        Args:
            transaction_id: ID транзакции для поиска
            updated_data: Обновленные данные
            tenant_id: ID tenant'а
        """
        if not tenant_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        
        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            worksheet = spreadsheet.worksheet("Транзакции")
            
            # Найдем строку с нужным ID транзакции (ID в последней колонке)
            all_values = worksheet.get_all_values()
            
            for i, row in enumerate(all_values):
                # ID находится в последней колонке (индекс 11)
                if len(row) > 11 and row[11] == str(transaction_id):
                    # Нашли строку, обновляем её
                    row_number = i + 1
                    
                    updated_row = self._format_transaction_row(updated_data)
                    
                    # Обновляем в таблице
                    range_name = f"A{row_number}:L{row_number}"
                    worksheet.update(range_name, [updated_row])
                    
                    # Обновляем время последнего обновления
                    try:
                        worksheet.update("O1", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S"))
                    except Exception as e:
                        print(f"Warning: Could not update timestamp: {e}")
                    
                    print(f"✅ Transaction {transaction_id} updated in Google Sheets for tenant {tenant_id}")
                    return
            
            print(f"⚠️ Transaction {transaction_id} not found in Google Sheets for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to update transaction in Google Sheets for tenant {tenant_id}: {e}")
    
    def delete_transaction(self, transaction_id: str, tenant_id: str = None):
        """
        Удаляет транзакцию из Google Sheets для конкретного tenant
        
        Args:
            transaction_id: ID транзакции для удаления
            tenant_id: ID tenant'а
        """
        if not tenant_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        
        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            worksheet = spreadsheet.worksheet("Транзакции")
            
            # Найдем строку с нужным ID транзакции (ID в последней колонке)
            all_values = worksheet.get_all_values()
            
            for i, row in enumerate(all_values):
                # ID находится в последней колонке (индекс 11)
                if len(row) > 11 and row[11] == str(transaction_id):
                    # Нашли строку, удаляем её
                    row_number = i + 1
                    worksheet.delete_rows(row_number)
                    
                    # Обновляем время последнего обновления
                    try:
                        worksheet.update("O1", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S"))
                    except Exception as e:
                        print(f"Warning: Could not update timestamp: {e}")
                    
                    print(f"✅ Transaction {transaction_id} deleted from Google Sheets for tenant {tenant_id}")
                    return
            
            print(f"⚠️ Transaction {transaction_id} not found in Google Sheets for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to delete transaction from Google Sheets for tenant {tenant_id}: {e}")


# Создаем глобальный экземпляр
sheets_manager = GoogleSheetsManager()