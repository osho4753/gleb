"""
Google Sheets Integration с поддержкой множественных таблиц
"""
from bson import ObjectId
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
                    "Касса", "Дата/Время", "Тип операции", "Принял", "Количество", 
                    "Выдал", "Количество", "Курс", "Комиссия %", 
                    "Прибыль", "Валюта прибыли", "Примечание", "Id",
                    "", "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
                ]
                # Используем update вместо append_row для более надежной записи
                transactions_sheet.update('A1:P1', [headers], value_input_option='RAW')
            
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
    
    def _format_transaction_row(self, transaction_data: dict, cash_desk_name: str = None) -> List[Any]:
        """Форматирует данные транзакции для записи в таблицу в плоском формате"""
        # Получаем имя кассы
        if not cash_desk_name:
            # Если cash_desk_name не передан, пытаемся получить из данных транзакции
            cash_desk_id = transaction_data.get("cash_desk_id")
            if cash_desk_id:
                from .db import db
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id})
                cash_desk_name = cash_desk["name"] if cash_desk else "Неизвестная касса"
            else:
                cash_desk_name = "Общая касса"
        
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
        
        # Плоский формат: Касса, Дата/Время, Тип операции, Принял, Количество, Выдал, Количество, Курс, Комиссия %, Прибыль, Валюта прибыли, Примечание, Id
        row = [
            cash_desk_name,                                  # Касса (НОВОЕ!)
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

    def _sync_transactions_sheet(self, sheet, transactions: List[Dict], cash_desk_name: str):
        """Синхронизация листа транзакций для конкретной кассы"""
        # Очищаем лист
        sheet.clear()
        
        # Подготавливаем все данные для записи одним запросом
        all_data = []
        
        # Заголовки с указанием кассы
        headers = [
            f"ТРАНЗАКЦИИ - {cash_desk_name.upper()}", "", "", "", "", "", "", "", "", "", "", "", "",
            "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
        ]
        all_data.append(headers)
        
        # Пустая строка
        all_data.append([""] * 16)
        
        # Заголовки колонок
        column_headers = [
            "Дата/Время", "Тип операции", "Принял", "Количество", 
            "Выдал", "Количество", "Курс", "Комиссия %", 
            "Прибыль", "Валюта прибыли", "Примечание", "Id"
        ]
        all_data.append(column_headers)
        
        # Добавляем все транзакции
        for tx in transactions:
            created_at = tx.get("created_at", datetime.utcnow())
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    created_at = datetime.utcnow()
            
            row = [
                created_at.strftime("%d.%m.%Y %H:%M:%S"),
                self._get_transaction_type_ru(tx.get("type", "")),
                tx.get("from_asset", ""),
                tx.get("amount_from", 0),
                tx.get("to_asset", ""),
                tx.get("amount_to_final", 0),
                tx.get("rate_used", 0),
                f"{tx.get('fee_percent', 0)}%",
                tx.get("profit", 0),
                tx.get("profit_currency", ""),
                tx.get("note", ""),
                str(tx.get("_id", ""))
            ]
            all_data.append(self._clean_row_data(row))
        
        # Записываем все данные одним запросом
        if all_data:
            sheet.update(f'A1:P{len(all_data)}', all_data, value_input_option='RAW')
    
    def _sync_cash_sheet(self, sheet, cash_status: Dict, realized_profits: Dict, cash_desk_name: str):
        """Синхронизация листа кассы для конкретной кассы"""
        # Очищаем лист
        sheet.clear()
        
        all_data = []
        
        # Заголовок с названием кассы
        headers = [
            f"КАССА - {cash_desk_name.upper()}", "", "", "", "", "",
            "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
        ]
        all_data.append(headers)
        
        # Пустая строка
        all_data.append([""] * 8)
        
        # Балансы кассы
        all_data.append(["БАЛАНСЫ КАССЫ", "", "", "", "", "", "", ""])
        all_data.append(["Валюта", "Баланс", "", "", "", "", "", ""])
        
        for asset, balance in cash_status.items():
            all_data.append([asset, balance, "", "", "", "", "", ""])
        
        # Пустые строки
        all_data.append([""] * 8)
        all_data.append([""] * 8)
        
        # Реализованная прибыль
        all_data.append(["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ", "", "", "", "", "", "", ""])
        all_data.append(["Валюта", "Прибыль", "", "", "", "", "", ""])
        
        for currency, profit in realized_profits.items():
            if profit != 0:  # Показываем только ненулевые значения
                all_data.append([currency, profit, "", "", "", "", "", ""])
        
        # Записываем все данные одним запросом
        if all_data:
            sheet.update(f'A1:H{len(all_data)}', all_data, value_input_option='RAW')

    def sync_aggregate_report(self, spreadsheet_id: str, all_cash_desks_data: List[Dict], tenant_id: str):
        """Создание агрегированного отчета по всем кассам"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Получаем или создаем лист общего отчета
            aggregate_sheet_name = "Общий_Отчет"
            try:
                aggregate_sheet = spreadsheet.worksheet(aggregate_sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                aggregate_sheet = spreadsheet.add_worksheet(
                    title=aggregate_sheet_name, 
                    rows=2000, 
                    cols=20
                )
            
            # Очищаем лист
            aggregate_sheet.clear()
            
            all_data = []
            
            # Заголовок
            headers = [
                "ОБЩИЙ ОТЧЕТ ПО ВСЕМ КАССАМ", "", "", "", "", "", "", "", "", "", "", "", "",
                "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            all_data.append(headers)
            all_data.append([""] * 15)
            
            # Сводная информация по кассам
            all_data.append(["СВОДКА ПО КАССАМ", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
            all_data.append(["Касса", "USD", "EUR", "CZK", "USDT", "Общая прибыль USD", "Общая прибыль EUR", "", "", "", "", "", "", "", ""])
            
            total_balances = {"USD": 0, "EUR": 0, "CZK": 0, "USDT": 0}
            total_profits = {"USD": 0, "EUR": 0}
            
            for desk_data in all_cash_desks_data:
                cash_desk_name = desk_data.get("cash_desk_name", "Неизвестно")
                cash_status = desk_data.get("cash_status", {})
                realized_profits = desk_data.get("realized_profits", {})
                
                row = [
                    cash_desk_name,
                    cash_status.get("USD", 0),
                    cash_status.get("EUR", 0), 
                    cash_status.get("CZK", 0),
                    cash_status.get("USDT", 0),
                    realized_profits.get("USD", 0),
                    realized_profits.get("EUR", 0),
                    "", "", "", "", "", "", "", ""
                ]
                all_data.append(self._clean_row_data(row))
                
                # Суммируем для итогов
                for currency in total_balances:
                    total_balances[currency] += cash_status.get(currency, 0)
                for currency in total_profits:
                    total_profits[currency] += realized_profits.get(currency, 0)
            
            # Итоговая строка
            all_data.append([""] * 15)
            total_row = [
                "ИТОГО:",
                total_balances["USD"],
                total_balances["EUR"],
                total_balances["CZK"], 
                total_balances["USDT"],
                total_profits["USD"],
                total_profits["EUR"],
                "", "", "", "", "", "", "", ""
            ]
            all_data.append(self._clean_row_data(total_row))
            
            # Пустые строки
            all_data.append([""] * 15)
            all_data.append([""] * 15)
            
            # Все транзакции с указанием кассы
            all_data.append(["ВСЕ ТРАНЗАКЦИИ", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
            column_headers = [
                "Касса", "Дата/Время", "Тип операции", "Принял", "Количество", 
                "Выдал", "Количество", "Курс", "Комиссия %", 
                "Прибыль", "Валюта прибыли", "Примечание", "Id"
            ]
            all_data.append(column_headers)
            
            # Добавляем все транзакции от всех касс
            for desk_data in all_cash_desks_data:
                cash_desk_name = desk_data.get("cash_desk_name", "Неизвестно")
                transactions = desk_data.get("transactions", [])
                
                for tx in transactions:
                    created_at = tx.get("created_at", datetime.utcnow())
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        except:
                            created_at = datetime.utcnow()
                    
                    row = [
                        cash_desk_name,  # Добавляем название кассы
                        created_at.strftime("%d.%m.%Y %H:%M:%S"),
                        self._get_transaction_type_ru(tx.get("type", "")),
                        tx.get("from_asset", ""),
                        tx.get("amount_from", 0),
                        tx.get("to_asset", ""),
                        tx.get("amount_to_final", 0),
                        tx.get("rate_used", 0),
                        f"{tx.get('fee_percent', 0)}%",
                        tx.get("profit", 0),
                        tx.get("profit_currency", ""),
                        tx.get("note", ""),
                        str(tx.get("_id", ""))
                    ]
                    all_data.append(self._clean_row_data(row))
            
            # Записываем все данные одним запросом
            if all_data:
                aggregate_sheet.update(f'A1:M{len(all_data)}', all_data, value_input_option='RAW')
            
            print(f"✅ Агрегированный отчет синхронизирован с Google Sheets")
        
        except Exception as e:
            print(f"❌ Ошибка синхронизации агрегированного отчета: {e}")
            raise e
    
    def sync_cash_desk_data(self, spreadsheet_id: str, cash_desk_name: str, transactions: List[Dict], cash_status: Dict, realized_profits: Dict, tenant_id: str):
        """Синхронизация данных конкретной кассы с Google Sheets"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Создаем листы для кассы если их нет
            transactions_sheet_name = f"Транзакции_{cash_desk_name}"
            cash_sheet_name = f"Касса_{cash_desk_name}"
            
            # Получаем или создаем лист транзакций
            try:
                transactions_sheet = spreadsheet.worksheet(transactions_sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                transactions_sheet = spreadsheet.add_worksheet(
                    title=transactions_sheet_name, 
                    rows=1000, 
                    cols=15
                )
            
            # Получаем или создаем лист кассы
            try:
                cash_sheet = spreadsheet.worksheet(cash_sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                cash_sheet = spreadsheet.add_worksheet(
                    title=cash_sheet_name, 
                    rows=100, 
                    cols=10
                )
            
            # Синхронизируем данные
            self._sync_transactions_sheet(transactions_sheet, transactions, cash_desk_name)
            self._sync_cash_sheet(cash_sheet, cash_status, realized_profits, cash_desk_name)
            
            print(f"✅ Данные кассы '{cash_desk_name}' синхронизированы с Google Sheets")
        
        except Exception as e:
            print(f"❌ Ошибка синхронизации кассы '{cash_desk_name}': {e}")
            raise e

    def sync_all_data(self, spreadsheet_id: str, transactions: List[Dict], cash_status: Dict, realized_profits: Dict, tenant_id: str):
        """Полная синхронизация всех данных с Google Sheets - обновлено для мультикассовой системы"""
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Получаем уникальные кассы из транзакций
            cash_desks = set()
            for transaction in transactions:
                if "cash_desk_id" in transaction and transaction["cash_desk_id"]:
                    # Получаем имя кассы из БД
                    from .db import db
                    cash_desk = db.cash_desks.find_one({"id": transaction["cash_desk_id"], "tenant_id": tenant_id})
                    if cash_desk:
                        cash_desks.add((transaction["cash_desk_id"], cash_desk["name"]))
            
            # Если есть кассы, создаем структурированные листы
            if cash_desks:
                self._create_structured_sheets(spreadsheet, transactions, cash_status, realized_profits, tenant_id, list(cash_desks))
            else:
                # Если нет касс, создаем общий лист (обратная совместимость)
                self._create_legacy_sheets(spreadsheet, transactions, cash_status, realized_profits)
            
            print(f"✅ All data synced for tenant {tenant_id}: {len(transactions)} transactions, {len(cash_status)} cash items, {len(realized_profits)} profit items")
            
        except Exception as e:
            raise Exception(f"Failed to sync all data: {str(e)}")
    
    def _create_aggregate_sheet(self, spreadsheet, transactions, cash_status, realized_profits):
        """Создает сводный лист со всеми данными"""
        try:
            # Получаем или создаем сводный лист
            try:
                aggregate_sheet = spreadsheet.worksheet("Сводка")
            except gspread.exceptions.WorksheetNotFound:
                aggregate_sheet = spreadsheet.add_worksheet(title="Сводка", rows=1000, cols=16)
            
            # Очищаем лист
            aggregate_sheet.clear()
            
            # Заголовки
            headers = [
                "Дата/Время", "Тип операции", "Принял", "Количество", 
                "Выдал", "Количество", "Курс", "Комиссия %", 
                "Прибыль", "Валюта прибыли", "Примечание", "Касса", "Id",
                "", "Последнее обновление:"
            ]
            all_data = [headers]
            
            # Добавляем все транзакции с указанием кассы
            all_data.append(["ВСЕ ТРАНЗАКЦИИ", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
            all_data.append([""])
            
            # Группируем транзакции по кассам
            from .db import db
            for transaction in transactions:
                cash_desk_name = "Общая касса"
                if transaction.get("cash_desk_id"):
                    cash_desk = db.cash_desks.find_one({"id": transaction["cash_desk_id"]})
                    if cash_desk:
                        cash_desk_name = cash_desk["name"]
                
                row_data = self._format_transaction_row(transaction, cash_desk_name)  # Касса уже включена в row_data
                # Дополняем до 16 колонок (теперь с Кассой)
                while len(row_data) < 16:
                    row_data.append("")
                all_data.append(row_data)
            
            # Добавляем сводку по кассам
            all_data.append([""])
            all_data.append(["СВОДКА ПО КАССАМ", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
            all_data.append(["Касса", "Валюта", "Баланс", "", "", "", "", "", "", "", "", "", "", "", ""])
            
            # Группируем кассу по кассам
            for currency, balance in cash_status.items():
                all_data.append(["Все кассы", currency, balance, "", "", "", "", "", "", "", "", "", "", "", ""])
            
            # Записываем данные
            if all_data:
                clean_data = []
                for row in all_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_data.append(clean_row)
                
                range_name = f"A1:P{len(clean_data)}"
                aggregate_sheet.update(range_name, clean_data, value_input_option='RAW')
            
        except Exception as e:
            print(f"❌ Ошибка создания сводного листа: {e}")
    
    def _create_structured_sheets(self, spreadsheet, transactions, cash_status, realized_profits, tenant_id: str, cash_desks: list):
        """Создает структурированные листы с группировкой по кассам"""
        try:
            # 1. Создаем лист "Транзакции" с группировкой по кассам
            try:
                transactions_sheet = spreadsheet.worksheet("Транзакции")
                transactions_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                transactions_sheet = spreadsheet.add_worksheet(title="Транзакции", rows=1000, cols=16)
            
            # Заголовки
            headers = [
                "Касса", "Дата/Время", "Тип операции", "Принял", "Количество", 
                "Выдал", "Количество", "Курс", "Комиссия %", 
                "Прибыль", "Валюта прибыли", "Примечание", "Id",
                "", "Обновлено:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            
            all_data = [headers]
            all_data.append([""] * 16)  # Пустая строка после заголовков
            
            # Группируем транзакции по кассам
            for cash_desk_id, cash_desk_name in sorted(cash_desks, key=lambda x: x[1]):  # Сортируем по имени кассы
                # Добавляем разделитель кассы
                separator = [f"=== {cash_desk_name.upper()} ==="] + [""] * 15
                all_data.append(separator)
                
                # Фильтруем транзакции этой кассы
                cash_desk_transactions = [t for t in transactions if t.get("cash_desk_id") == cash_desk_id]
                cash_desk_transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)  # Новые сверху
                
                # Добавляем транзакции кассы
                for transaction in cash_desk_transactions:
                    row_data = self._format_transaction_row(transaction, cash_desk_name)
                    while len(row_data) < 16:
                        row_data.append("")
                    all_data.append(row_data)
                
                # Пустая строка между кассами
                all_data.append([""] * 16)
            
            # Записываем все данные
            if all_data:
                clean_data = []
                for row in all_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_data.append(clean_row)
                
                range_name = f"A1:P{len(clean_data)}"
                transactions_sheet.update(range_name, clean_data, value_input_option='RAW')
            
            # 2. Создаем листы "Касса" и "Прибыль" с группировкой
            self._create_cash_summary_sheets(spreadsheet, cash_status, realized_profits, cash_desks)
            
        except Exception as e:
            print(f"❌ Ошибка создания структурированных листов: {e}")
    
    def _create_cash_summary_sheets(self, spreadsheet, cash_status, realized_profits, cash_desks):
        """Создает сводные листы кассы и прибыли с группировкой"""
        try:
            # Лист "Касса"
            try:
                cash_sheet = spreadsheet.worksheet("Касса")
                cash_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                cash_sheet = spreadsheet.add_worksheet(title="Касса", rows=100, cols=4)
            
            cash_data = [["Касса", "Валюта", "Баланс", f"Обновлено: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}"]]
            
            # Группируем по кассам
            from .db import db
            for cash_desk_id, cash_desk_name in sorted(cash_desks, key=lambda x: x[1]):
                # Получаем балансы для этой кассы
                cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id}, {"_id": 0}))
                if cash_items:
                    for item in cash_items:
                        cash_data.append([cash_desk_name, item["asset"], item["balance"], ""])
            
            if len(cash_data) > 1:
                cash_sheet.update(f"A1:D{len(cash_data)}", cash_data, value_input_option='RAW')
            
            # Лист "Прибыль"
            try:
                profit_sheet = spreadsheet.worksheet("Прибыль")
                profit_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                profit_sheet = spreadsheet.add_worksheet(title="Прибыль", rows=100, cols=4)
            
            profit_data = [["Касса", "Валюта", "Прибыль", f"Обновлено: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}"]]
            
            # Группируем прибыль по кассам
            for cash_desk_id, cash_desk_name in sorted(cash_desks, key=lambda x: x[1]):
                # Вычисляем прибыль для этой кассы
                pipeline = [
                    {"$match": {"cash_desk_id": cash_desk_id}},
                    {"$group": {"_id": "$profit_currency", "total_profit": {"$sum": "$realized_profit"}}}
                ]
                profit_results = list(db.transactions.aggregate(pipeline))
                for result in profit_results:
                    if result["_id"] and result["total_profit"]:
                        profit_data.append([cash_desk_name, result["_id"], result["total_profit"], ""])
            
            if len(profit_data) > 1:
                profit_sheet.update(f"A1:D{len(profit_data)}", profit_data, value_input_option='RAW')
                
        except Exception as e:
            print(f"❌ Ошибка создания сводных листов: {e}")
    
    def _create_legacy_sheets(self, spreadsheet, transactions, cash_status, realized_profits):
        """Создает старые листы для обратной совместимости"""
        try:
            # 1. Синхронизируем транзакции
            try:
                transactions_sheet = spreadsheet.worksheet("Транзакции")
            except gspread.exceptions.WorksheetNotFound:
                transactions_sheet = spreadsheet.add_worksheet(title="Транзакции", rows=1000, cols=16)
            
            # Очищаем весь лист
            transactions_sheet.clear()
            
            # Подготавливаем все данные для записи одним запросом
            all_data = []
            
            # Заголовки в новом формате
            headers = [
                "Касса", "Дата/Время", "Тип операции", "Принял", "Количество", 
                "Выдал", "Количество", "Курс", "Комиссия %", 
                "Прибыль", "Валюта прибыли", "Примечание", "Id",
                "", "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            all_data.append(headers)
            
            # Добавляем все транзакции
            for transaction in transactions:
                row_data = self._format_transaction_row(transaction)  # Касса будет "Общая касса" по умолчанию
                # Дополняем до 16 колонок (теперь с Кассой)
                while len(row_data) < 16:
                    row_data.append("")
                all_data.append(row_data)
            
            # Записываем все данные одним пакетом
            if all_data:
                # Убеждаемся что все None значения заменены на пустые строки
                clean_data = []
                for row in all_data:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_data.append(clean_row)
                
                range_name = f"A1:P{len(clean_data)}"
                transactions_sheet.update(range_name, clean_data, value_input_option='RAW')
            
            # 2. Синхронизируем касса и прибыль
            try:
                summary_sheet = spreadsheet.worksheet("Касса и Прибыль")
            except gspread.exceptions.WorksheetNotFound:
                summary_sheet = spreadsheet.add_worksheet(title="Касса и Прибыль", rows=100, cols=10)
            
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
            
            print(f"✅ Legacy data synced: {len(transactions)} transactions, {len(cash_status)} cash items, {len(realized_profits)} profit items")
            
        except Exception as e:
            print(f"❌ Ошибка создания старых листов: {e}")
            raise e
    
    def update_balance_for_desk(self, cash_desk_name: str, currency: str, new_balance: float, tenant_id: str):
        """Обновляет одну строку баланса для конкретной кассы в плоской структуре"""
        if not tenant_id:
            print(f"⚠️ No tenant_id provided for balance update")
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
            
            # Получаем или создаем лист "Касса"
            try:
                cash_sheet = spreadsheet.worksheet("Касса")
            except gspread.exceptions.WorksheetNotFound:
                cash_sheet = spreadsheet.add_worksheet(title="Касса", rows=100, cols=3)
                # Добавляем заголовки
                cash_sheet.append_row(["Касса", "Валюта", "Баланс"])

            # Ищем строку по Кассе и Валюте
            all_records = cash_sheet.get_all_records()
            found_row = None
            
            for i, record in enumerate(all_records, start=2):  # start=2 потому что строка 1 - заголовки
                if record.get("Касса") == cash_desk_name and record.get("Валюта") == currency:
                    found_row = i
                    break
            
            if found_row:
                # Обновляем баланс в найденной строке
                cash_sheet.update_cell(found_row, 3, new_balance)
                print(f"✅ Updated balance for {cash_desk_name} {currency}: {new_balance}")
            else:
                # Добавляем новую строку
                cash_sheet.append_row([cash_desk_name, currency, new_balance])
                print(f"✅ Added new balance row for {cash_desk_name} {currency}: {new_balance}")
                
            # Обновляем timestamp
            try:
                cash_sheet.update("D1", [["Обновлено:"]], value_input_option='USER_ENTERED')
                cash_sheet.update("E1", [[datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")]], value_input_option='USER_ENTERED')
            except Exception as e:
                print(f"Warning: Could not update timestamp: {e}")
                
        except Exception as e:
            print(f"❌ Failed to update balance in Sheets for {cash_desk_name}: {e}")

    def update_profit_for_desk(self, cash_desk_name: str, currency: str, new_profit: float, tenant_id: str):
        """Обновляет одну строку прибыли для конкретной кассы в плоской структуре"""
        if not tenant_id:
            print(f"⚠️ No tenant_id provided for profit update")
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
            
            # Получаем или создаем лист "Прибыль"
            try:
                profit_sheet = spreadsheet.worksheet("Прибыль")
            except gspread.exceptions.WorksheetNotFound:
                profit_sheet = spreadsheet.add_worksheet(title="Прибыль", rows=100, cols=3)
                # Добавляем заголовки
                profit_sheet.append_row(["Касса", "Валюта", "Прибыль"])

            # Ищем строку по Кассе и Валюте
            all_records = profit_sheet.get_all_records()
            found_row = None
            
            for i, record in enumerate(all_records, start=2):  # start=2 потому что строка 1 - заголовки
                if record.get("Касса") == cash_desk_name and record.get("Валюта") == currency:
                    found_row = i
                    break
            
            if found_row:
                # Обновляем прибыль в найденной строке
                profit_sheet.update_cell(found_row, 3, new_profit)
                print(f"✅ Updated profit for {cash_desk_name} {currency}: {new_profit}")
            else:
                # Добавляем новую строку
                profit_sheet.append_row([cash_desk_name, currency, new_profit])
                print(f"✅ Added new profit row for {cash_desk_name} {currency}: {new_profit}")
                
            # Обновляем timestamp
            try:
                profit_sheet.update("D1", [["Обновлено:"]], value_input_option='USER_ENTERED')
                profit_sheet.update("E1", [[datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")]], value_input_option='USER_ENTERED')
            except Exception as e:
                print(f"Warning: Could not update timestamp: {e}")
                
        except Exception as e:
            print(f"❌ Failed to update profit in Sheets for {cash_desk_name}: {e}")
    
    def add_transaction(self, transaction_data: dict, tenant_id: str = None, cash_desk_id: str = None):
        """
        Добавляет транзакцию в Google Sheets для конкретной кассы
        
        Args:
            transaction_data: Данные транзакции из MongoDB
            tenant_id: ID tenant'а для изоляции данных
            cash_desk_id: ID кассы (Фаза 2)
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
            
            # Используем единый лист "Транзакции" для всех касс
            try:
                worksheet = spreadsheet.worksheet("Транзакции")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title="Транзакции", 
                    rows=1000, 
                    cols=16  # 16 колонок с учетом новой колонки "Касса"
                )
                # Добавляем заголовки для плоской структуры
                headers = [
                    "Касса", "Дата/Время", "Тип операции", "Принял", "Количество", 
                    "Выдал", "Количество", "Курс", "Комиссия %", 
                    "Прибыль", "Валюта прибыли", "Примечание", "Id",
                    "", "Обновлено:", ""
                ]
                worksheet.append_row(headers)
            
            # Получаем имя кассы
            if cash_desk_id:
                from .db import db
                cash_desk = db.cash_desks.find_one({"_id": ObjectId(cash_desk_id)})
                cash_desk_name = cash_desk["name"] if cash_desk else "Неизвестная касса"
            else:
                cash_desk_name = "Общая касса"
            
            # Проверяем, есть ли уже данные этой кассы в листе
            try:
                all_values = worksheet.get_all_values()
                cash_desk_found = False
                for row in all_values:
                    if len(row) > 0 and row[0] == cash_desk_name:
                        cash_desk_found = True
                        break
                
                # Если это первая транзакция для этой кассы, добавляем разделитель
                if not cash_desk_found and len(all_values) > 1:  # > 1 потому что есть заголовки
                    separator_row = [f"=== КАССА: {cash_desk_name.upper()} ==="] + [""] * 15
                    worksheet.append_row(separator_row)
            except Exception as e:
                print(f"Warning: Could not check existing cash desks: {e}")
            
            row_data = self._format_transaction_row(transaction_data, cash_desk_name)
            worksheet.append_row(row_data)
            
            # Обновляем время последнего обновления в заголовке
            try:
                worksheet.update("P1", [[datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")]], value_input_option='USER_ENTERED')
            except Exception as e:
                print(f"Warning: Could not update timestamp: {e}")
            
            print(f"✅ Transaction added to Google Sheets for cash desk '{cash_desk_name}' (tenant {tenant_id})")
            
        except Exception as e:
            print(f"❌ Failed to add transaction to Google Sheets for tenant {tenant_id}: {e}")
    
    def update_cash_and_profits(self, cash_status: dict, realized_profits: dict, tenant_id: str = None, cash_desk_id: str = None, spreadsheet_id: str = None):
        """
        Обновляет данные кассы и прибыли для конкретной кассы
        
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
                    
                    # Получаем имя кассы из обновленных данных
                    updated_row = self._format_transaction_row(updated_data)
                    
                    # Обновляем в таблице
                    range_name = f"A{row_number}:M{row_number}"  # M потому что updated_row содержит 13 элементов (без cash_desk)
                    worksheet.update(range_name, [updated_row])
                    
                    # Обновляем время последнего обновления
                    try:
                        worksheet.update("O1", [[datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")]], value_input_option='USER_ENTERED')
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
                        worksheet.update("O1", [[datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")]], value_input_option='USER_ENTERED')
                    except Exception as e:
                        print(f"Warning: Could not update timestamp: {e}")
                    
                    print(f"✅ Transaction {transaction_id} deleted from Google Sheets for tenant {tenant_id}")
                    return
            
            print(f"⚠️ Transaction {transaction_id} not found in Google Sheets for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to delete transaction from Google Sheets for tenant {tenant_id}: {e}")


# Создаем глобальный экземпляр
sheets_manager = GoogleSheetsManager()