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
    
# В back/src/google_sheets.py

    def setup_tenant_spreadsheet(self, spreadsheet_id: str, tenant_id: str):
        """
        Инициализирует таблицу, создавая "Общий_Отчет" и удаляя старые листы.
        Листы для касс будут созданы динамически.
        """
        if not self.client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # 1. Создаем или очищаем лист "Общий_Отчет"
            aggregate_sheet_name = "Общий_Отчет"
            try:
                aggregate_sheet = spreadsheet.worksheet(aggregate_sheet_name)
                aggregate_sheet.clear()
            except gspread.WorksheetNotFound:
                aggregate_sheet = spreadsheet.add_worksheet(
                    title=aggregate_sheet_name, 
                    rows=1000, 
                    cols=20
                )
            
            # Устанавливаем заголовки для Общего_Отчета (как в sync_aggregate_report)
            headers = [
                "ОБЩИЙ ОТЧЕТ ПО ВСЕМ КАССАМ", "", "", "", "",
                "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            aggregate_sheet.update('A1:G1', [headers], value_input_option='RAW')
            aggregate_sheet.format('A1:G1', {'textFormat': {'bold': True}})
            print("✅ 'Общий_Отчет' создан/очищен.")

            # 2. Удаляем старые/ненужные листы
            # Мы также удаляем "Транзакции" и "Касса", т.к. они больше не используются
            default_sheet_names = [
                "Лист1", "Sheet1", 
                "Транзакции", "Касса", "Прибыль", "Касса и Прибыль"
            ]
            all_worksheets = spreadsheet.worksheets()
            
            for worksheet in all_worksheets:
                if worksheet.title in default_sheet_names:
                    try:
                        spreadsheet.del_worksheet(worksheet)
                    except Exception as e:
                        print(f"Could not remove default sheet {worksheet.title}: {e}")
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to setup spreadsheet: {str(e)}")
    # В back/src/google_sheets.py

    def _get_or_create_cash_desk_sheet(self, spreadsheet, sheet_name: str, type: str):
        """Вспомогательная функция для получения или создания листа кассы/транзакций."""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            if type == "transactions":
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=15)
                # Упрощенные заголовки, т.к. "Касса" уже в названии
                headers = [
                    "Дата/Время", "Тип операции", "Принял", "Количество", 
                    "Выдал", "Количество", "Курс", "Комиссия %", 
                    "Прибыль", "Валюта прибыли", "Примечание", "Id"
                ]
                worksheet.update('A1:L1', [headers], value_input_option='RAW')
                worksheet.format('A1:L1', {'textFormat': {'bold': True}})
            elif type == "cash_summary":
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=10)
                # Заголовки как в _sync_cash_sheet
                headers = [
                    f"КАССА - {sheet_name.replace('Касса_', '')}", "", "",
                    "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
                ]
                worksheet.update('A1:E1', [headers], value_input_option='RAW')
                worksheet.format('A1:E1', {'textFormat': {'bold': True}})
                
                # Структура баланса и прибыли
                structure = [
                    ["БАЛАНСЫ КАССЫ"], ["Валюта", "Баланс"],
                    ["USD", 0], ["EUR", 0], ["CZK", 0], ["USDT", 0], # Дефолтные валюты
                    [""], [""],
                    ["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ"], ["Валюта", "Прибыль"]
                ]
                worksheet.update('A3:B12', structure, value_input_option='RAW')
                
        return worksheet

    def _format_transaction_row_simple(self, transaction_data: dict) -> List[Any]:
        """
        Упрощенный форматер для листа "Транзакции_Касса".
        Колонка "Касса" не нужна.
        """
        created_at = transaction_data.get("created_at")
        date_str = created_at.strftime("%d.%m.%Y %H:%M:%S") if isinstance(created_at, datetime) else str(created_at)
        
        tx_type = transaction_data.get("type", "")
        type_ru = self._get_transaction_type_ru(tx_type) # Используем хелпер из прошлого ответа
        
        row = [
            date_str,                                    # Дата/Время
            type_ru,                                     # Тип операции
            transaction_data.get("from_asset", ""),      # Принял
            transaction_data.get("amount_from", 0),      # Количество
            transaction_data.get("to_asset", ""),        # Выдал
            transaction_data.get("amount_to_final", 0),  # Количество
            transaction_data.get("rate_used", 0),        # Курс
            transaction_data.get("fee_percent", 0),      # Комиссия %
            transaction_data.get("profit", 0),           # Прибыль
            transaction_data.get("profit_currency", ""), # Валюта прибыли
            transaction_data.get("note", ""),            # Примечание
            str(transaction_data.get("_id", ""))         # Id
        ]
        return self._clean_row_data(row) # Используем хелпер из прошлого ответа

    def add_transaction(self, transaction_data: dict, tenant_id: str = None, cash_desk_id: str = None):
        """
        (ПЕРЕРАБОТАНО)
        Добавляет транзакцию в лист, специфичный для кассы (f"Транзакции_{cash_desk_name}").
        """
        if not tenant_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        
        # Получаем имя кассы
        cash_desk_name = "Default" # На случай, если касса не найдена
        if cash_desk_id:
            print(f"🔍 Looking for cash desk with _id: {cash_desk_id}, tenant_id: {tenant_id}")
            cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
            if cash_desk:
                cash_desk_name = cash_desk["name"]
                print(f"✅ Found cash desk: {cash_desk_name}")
            else:
                # Попробуем также поиск по id (на случай если это строка)
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
                if cash_desk:
                    cash_desk_name = cash_desk["name"]
                    print(f"✅ Found cash desk by id: {cash_desk_name}")
                else:
                    print(f"⚠️ Cash desk not found for id: {cash_desk_id}")
        
        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            # 1. Находим или создаем лист ТРАНЗАКЦИЙ
            tx_sheet_name = f"Транзакции_{cash_desk_name}"
            worksheet = self._get_or_create_cash_desk_sheet(spreadsheet, tx_sheet_name, "transactions")
            # 2. Добавляем транзакцию
            row_data = self._format_transaction_row_simple(transaction_data)
            worksheet.append_row(row_data, value_input_option='RAW')
            print(f"✅ Transaction added to Google Sheet '{tx_sheet_name}'")

            # 3. Обновляем состояние кассы (балансы и прибыль)
            # Получаем актуальные балансы и прибыли из базы
            if cash_desk_id:
                cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
                if not cash_desk:
                    cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
                if cash_desk:
                    cash_desk_name = cash_desk["name"]
                    cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id}))
                    cash_status = {item["asset"]: item["balance"] for item in cash_items}
                    pipeline = [
                        {"$match": {"cash_desk_id": cash_desk_id, "profit_currency": {"$ne": None}}},
                        {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
                    ]
                    profit_results = list(db.transactions.aggregate(pipeline))
                    realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
                    # Обновляем балансы
                    for currency, balance in cash_status.items():
                        self.update_balance_for_desk(cash_desk_name, currency, balance, tenant_id)
                    # Обновляем прибыли
                    for currency, profit in realized_profits.items():
                        if profit != 0:
                            self.update_profit_for_desk(cash_desk_name, currency, profit, tenant_id)

            self.sync_aggregate_report(tenant_id)
        except Exception as e:
            print(f"❌ Failed to add transaction to Google Sheet '{tx_sheet_name}': {e}")
    # В back/src/google_sheets.py

    def _find_cell_and_update(self, worksheet, search_col_idx, search_key, value_col_idx, new_value, search_section="balance"):
        """
        Находит ячейку по ключу в колонке и обновляет значение в другой колонке.
        search_section: "balance" для поиска в секции балансов (A3-A7), "profit" для поиска в секции прибылей (A12+)
        """
        try:
            # Получаем все значения из колонки A
            all_cells = worksheet.col_values(search_col_idx)
            
            # Определяем диапазон поиска в зависимости от секции
            if search_section == "balance":
                # Ищем в секции балансов (строки 3-7)
                start_idx = 2  # 3-я строка (индекс 2)
                end_idx = 7    # до 7-й строки 
            else:  # profit
                # Ищем в секции прибылей (начиная с 12-й строки)
                start_idx = 11  # 12-я строка (индекс 11)
                end_idx = len(all_cells)
            
            found_row_idx = -1
            for i in range(start_idx, min(end_idx, len(all_cells))):
                if all_cells[i] == search_key:
                    found_row_idx = i + 1  # gspread нумерация с 1
                    break
            
            if found_row_idx != -1:
                # Нашли, обновляем ячейку баланса/прибыли
                worksheet.update_cell(found_row_idx, value_col_idx, new_value)
                return True
            else:
                # Не нашли, добавляем новую строку в соответствующую секцию
                if search_section == "balance":
                    # Добавляем после существующих балансов (строка 7)
                    insert_row = 8
                else:  # profit
                    # Добавляем в конец листа
                    insert_row = len(all_cells) + 1
                
                # Вставляем новую строку
                worksheet.insert_row([search_key, new_value], insert_row)
                return True
                
        except Exception as e:
            print(f"Failed to find/update cell {search_key} in {search_section}: {e}")
            return False

    def update_balance_for_desk(self, cash_desk_name: str, currency: str, new_balance: float, tenant_id: str):
        """
        (НОВОЕ)
        Обновляет баланс на листе "Касса_{cash_desk_name}".
        """
        if not self.is_enabled_for_tenant(tenant_id): return
        settings = self.get_tenant_settings(tenant_id)
        if not settings: return

        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            cash_sheet_name = f"Касса_{cash_desk_name}"
            worksheet = self._get_or_create_cash_desk_sheet(spreadsheet, cash_sheet_name, "cash_summary")
            
            # Ищем валюту баланса в колонке A (idx=1), обновляем в колонке B (idx=2)
            # (Ищем в диапазоне A4:A7 где балансы)
            if self._find_cell_and_update(worksheet, 1, currency, 2, new_balance, "balance"):
                print(f"✅ Updated balance for {cash_desk_name} {currency}: {new_balance}")
                worksheet.update_cell(1, 5, datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")) # Обновляем timestamp
            self.sync_aggregate_report(tenant_id)

        except Exception as e:
            print(f"❌ Failed to update balance in Sheets for {cash_desk_name}: {e}")

    def update_profit_for_desk(self, cash_desk_name: str, currency: str, new_profit: float, tenant_id: str):
        """
        (ПЕРЕРАБОТАНО)
        Обновляет прибыль на листе "Касса_{cash_desk_name}".
        """
        if not self.is_enabled_for_tenant(tenant_id): return
        settings = self.get_tenant_settings(tenant_id)
        if not settings: return

        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            cash_sheet_name = f"Касса_{cash_desk_name}"
            worksheet = self._get_or_create_cash_desk_sheet(spreadsheet, cash_sheet_name, "cash_summary")
            
            # Ищем валюту прибыли в колонке A (idx=1), обновляем в колонке B (idx=2)
            # (Ищем в диапазоне A12:A... где прибыли)
            if self._find_cell_and_update(worksheet, 1, currency, 2, new_profit, "profit"):
                print(f"✅ Updated profit for {cash_desk_name} {currency}: {new_profit}")
                worksheet.update_cell(1, 5, datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")) # Обновляем timestamp
            
        except Exception as e:
            print(f"❌ Failed to update profit in Sheets for {cash_desk_name}: {e}")

    def _get_transaction_type_ru(self, tx_type: str) -> str:
        type_map = {
            "fiat_to_crypto": "Расход (Фиат -> Крипта)",
            "crypto_to_fiat": "Приход (Крипта -> Фиат)", 
            "fiat_to_fiat": "Обмен (Фиат -> Фиат)",
            "deposit": "Приход (Депозит)",
            "withdrawal": "Расход (Снятие)"
        }
        return type_map.get(tx_type, tx_type)


    
    def _clean_row_data(self, row: List[Any]) -> List[str]:
        """Очищает данные строки от None."""
        return [str(cell) if cell is not None else "" for cell in row]
    
    def sync_aggregate_report(self, tenant_id: str):
        """
        (НОВОЕ) Обновляет лист "Общий_Отчет" с данными по всем кассам.
        Заменяет старые общие листы "Транзакции", "Касса", "Прибыль".
        """
        if not self.is_enabled_for_tenant(tenant_id):
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        
        try:
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            
            # Получаем или создаём лист "Общий_Отчет"
            try:
                aggregate_sheet = spreadsheet.worksheet("Общий_Отчет")
            except gspread.WorksheetNotFound:
                aggregate_sheet = spreadsheet.add_worksheet(title="Общий_Отчет", rows=1000, cols=20)
            
            # Очищаем лист
            aggregate_sheet.clear()
            
            # Готовим данные для отчёта
            all_data = []
            
            # Заголовок
            headers = [
                "ОБЩИЙ ОТЧЕТ ПО ВСЕМ КАССАМ", "", "", "", "",
                "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
            ]
            all_data.append(headers)
            all_data.append([""] * 7)  # Пустая строка
            
            # Получаем все кассы для tenant
            cash_desks = list(db.cash_desks.find({"tenant_id": tenant_id}))
            
            if not cash_desks:
                all_data.append(["Нет касс для отображения"])
                aggregate_sheet.update('A1:G3', all_data, value_input_option='RAW')
                return
            
            # Сводная информация по кассам
            all_data.append(["СВОДКА ПО КАССАМ"])
            all_data.append(["Касса", "USD", "EUR", "CZK", "USDT", "Всего транзакций", "Последняя операция"])
            
            total_balances = {"USD": 0, "EUR": 0, "CZK": 0, "USDT": 0}
            total_transactions = 0
            
            for cash_desk in cash_desks:
                cash_desk_id = cash_desk["_id"]  # Используем правильное поле _id
                cash_desk_name = cash_desk["name"]
                
                # Получаем балансы
                cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id}))
                balances = {"USD": 0, "EUR": 0, "CZK": 0, "USDT": 0}
                
                for item in cash_items:
                    asset = item["asset"]
                    if asset in balances:
                        balances[asset] = item["balance"]
                        total_balances[asset] += item["balance"]
                
                # Количество транзакций
                tx_count = db.transactions.count_documents({"cash_desk_id": cash_desk_id})
                total_transactions += tx_count
                
                # Последняя операция
                last_tx = db.transactions.find_one(
                    {"cash_desk_id": cash_desk_id}, 
                    sort=[("created_at", -1)]
                )
                last_date = ""
                if last_tx and last_tx.get("created_at"):
                    last_date = last_tx["created_at"].strftime("%d.%m.%Y")
                
                # Добавляем строку кассы
                desk_row = [
                    cash_desk_name,
                    balances["USD"],
                    balances["EUR"], 
                    balances["CZK"],
                    balances["USDT"],
                    tx_count,
                    last_date
                ]
                all_data.append(desk_row)
            
            # Общие итоги
            all_data.append([""] * 7)  # Пустая строка
            total_row = [
                "ИТОГО:",
                total_balances["USD"],
                total_balances["EUR"],
                total_balances["CZK"], 
                total_balances["USDT"],
                total_transactions,
                ""
            ]
            all_data.append(total_row)
            
            # Записываем данные
            if all_data:
                range_name = f"A1:G{len(all_data)}"
                aggregate_sheet.update(range_name, all_data, value_input_option='RAW')
                
                # Форматирование
                aggregate_sheet.format('A1:G1', {'textFormat': {'bold': True, 'fontSize': 14}})
                aggregate_sheet.format('A4:G4', {'textFormat': {'bold': True}})
                aggregate_sheet.format('A5:G5', {'textFormat': {'bold': True}})
                aggregate_sheet.format(f'A{len(all_data)}:G{len(all_data)}', {'textFormat': {'bold': True}})
            
            print(f"✅ Aggregate report updated for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to update aggregate report for tenant {tenant_id}: {e}")

    def full_sync_to_google_sheets(self, tenant_id: str):
        if not self.is_enabled_for_tenant(tenant_id):
            return
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
        # Получаем все кассы
        cash_desks = list(db.cash_desks.find({"tenant_id": tenant_id}))
        for cash_desk in cash_desks:
            cash_desk_id = cash_desk["_id"]
            cash_desk_name = cash_desk["name"]
            # Балансы и прибыли
            cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id}))
            cash_status = {item["asset"]: item["balance"] for item in cash_items}
            # Прибыль
            pipeline = [
                {"$match": {"cash_desk_id": cash_desk_id, "profit_currency": {"$ne": None}}},
                {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
            ]
            profit_results = list(db.transactions.aggregate(pipeline))
            realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results}
            # Транзакции
            transactions = list(db.transactions.find({"cash_desk_id": cash_desk_id}))
            # Создать/очистить листы и записать данные
            cash_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, f"Касса_{cash_desk_name}", "cash_summary")
            self._sync_cash_sheet(cash_sheet, cash_status, realized_profits, cash_desk_name)
            tx_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, f"Транзакции_{cash_desk_name}", "transactions")
            self._sync_transactions_sheet(tx_sheet, transactions, cash_desk_name)
        # В конце обновить общий отчет
        self.sync_aggregate_report(tenant_id)

    
    def sync_all_data_for_tenant(self, tenant_id: str):
        """
        (НОВАЯ ГЛАВНАЯ ФУНКЦИЯ СИНХРОНИЗАЦИИ)
        Полностью синхронизирует ВСЕ данные tenant'а (Backfill).
        1. Находит все кассы (филиалы).
        2. Для каждой кассы создает/обновляет лист Транзакций.
        3. Для каждой кассы создает/обновляет лист Кассы/Прибыли.
        4. Обновляет "Общий_Отчет" в конце.
        """
        if not self.is_enabled_for_tenant(tenant_id):
            print(f"Tenant {tenant_id} disabled, skipping sync.")
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            print(f"Tenant {tenant_id} settings not found, skipping sync.")
            return
        
        spreadsheet_id = settings["spreadsheet_id"]
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # 1. Получаем ВСЕ кассы (включая удаленные, чтобы сохранить историю)
            cash_desks = list(db.cash_desks.find({"tenant_id": tenant_id}))
            
            print(f"🔄 Syncing all data for tenant {tenant_id}. Found {len(cash_desks)} cash desks.")

            all_cash_desks_data_for_agg = [] # Собираем данные для Общего Отчета

            # 2. Цикл по каждой кассе (филиалу)
            for cash_desk in cash_desks:
                cash_desk_id_str = str(cash_desk["_id"]) # Важно, _id это ObjectId
                cash_desk_name = cash_desk["name"]
                
                print(f"   -> Syncing desk: {cash_desk_name} ({cash_desk_id_str})")

                # 3. Собираем данные для ЭТОЙ кассы
                transactions = list(db.transactions.find({"cash_desk_id": cash_desk_id_str}))
                cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id_str}))
                
                pipeline = [
                    {"$match": {"cash_desk_id": cash_desk_id_str, "profit_currency": {"$ne": None}}},
                    {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
                ]
                profit_results = list(db.transactions.aggregate(pipeline))
                
                cash_status = {item["asset"]: item["balance"] for item in cash_items}
                realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}

                # 4. Обновляем лист ТРАНЗАКЦИЙ (полная перезапись)
                tx_sheet_name = f"Транзакции_{cash_desk_name}"
                transactions_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, tx_sheet_name, "transactions")
                # _sync_transactions_sheet УЖЕ СУЩЕСТВУЕТ в твоем коде
                self._sync_transactions_sheet(transactions_sheet, transactions, cash_desk_name)

                # 5. Обновляем лист КАССЫ (полная перезапись)
                cash_sheet_name = f"Касса_{cash_desk_name}"
                cash_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, cash_sheet_name, "cash_summary")
                # _sync_cash_sheet УЖЕ СУЩЕСТВУЕТ в твоем коде
                self._sync_cash_sheet(cash_sheet, cash_status, realized_profits, cash_desk_name)

                # 6. Добавляем в список для агрегации
                all_cash_desks_data_for_agg.append({
                    "cash_desk_name": cash_desk_name,
                    "cash_desk_id": cash_desk_id_str,
                    "transactions": transactions, # `sync_aggregate_report` использует это
                    "cash_status": cash_status,
                    "realized_profits": realized_profits
                })

            # 7. После всех касс, обновляем ОБЩИЙ ОТЧЕТ
            # `sync_aggregate_report` УЖЕ СУЩЕСТВУЕТ в твоем коде
            self.sync_aggregate_report(tenant_id)
            
            print(f"✅ Full data sync complete for tenant {tenant_id}")
            return True

        except Exception as e:
            print(f"❌ Failed to sync all data for tenant {tenant_id}: {e}")
            return False
        
    def sync_all_data(self, tenant_id: str):
        """
        (ПЕРЕРАБОТАНО) 
        Эта функция вызывается старым кодом (enable/re-enable).
        Мы ИГНОРИРУЕМ эти данные и вызываем новый, полный синхронизатор.
        """
        print(f"Legacy 'sync_all_data' called for tenant {tenant_id}. Redirecting to 'sync_all_data_for_tenant'.")
        
        # Игнорируем `spreadsheet_id`, `transactions`, `cash_status`, `realized_profits`
        # и просто вызываем новый, полный синхронизатор, который сам получит данные.
        self.sync_all_data_for_tenant(tenant_id)

    def update_cash_and_profits(self, cash_status: dict, realized_profits: dict, tenant_id: str = None, cash_desk_id: str = None, spreadsheet_id: str = None):
        """
        (ПЕРЕРАБОТАНО) Обновляет данные кассы в новой модели.
        Вместо общих листов обновляет листы конкретных касс и общий отчёт.
        """
        if not tenant_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        try:
            # Если передан cash_desk_id, обновляем только конкретную кассу
            if cash_desk_id:
                print(f"🔍 Looking for cash desk with _id: {cash_desk_id}, tenant_id: {tenant_id}")
                cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
                if not cash_desk:
                    # Попробуем поиск по id
                    cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
                
                if cash_desk:
                    cash_desk_name = cash_desk["name"]
                    print(f"✅ Found cash desk: {cash_desk_name}")
                    
                    # Обновляем балансы и прибыль для конкретной кассы
                    for currency, balance in cash_status.items():
                        self.update_balance_for_desk(cash_desk_name, currency, balance, tenant_id)
                    
                    for currency, profit in realized_profits.items():
                        if profit != 0:
                            self.update_profit_for_desk(cash_desk_name, currency, profit, tenant_id)
            
            self.sync_aggregate_report(tenant_id)

            
            print(f"✅ Cash and profits updated using new model for tenant {tenant_id}")
            
        except Exception as e:
            print(f"❌ Failed to update cash and profits using new model for tenant {tenant_id}: {e}")
    
    def update_transaction(self, transaction_id: str, updated_data: dict, tenant_id: str = None, cash_desk_id: str = None):
        """
        (ПЕРЕРАБОТАНО) Обновляет транзакцию на листе, специфичном для кассы.
        """
        if not tenant_id or not cash_desk_id or not self.is_enabled_for_tenant(tenant_id):
            return

        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return
        
        try:
            # 1. Получаем имя кассы
            print(f"🔍 Looking for cash desk with _id: {cash_desk_id}, tenant_id: {tenant_id}")
            cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
            if not cash_desk:
                # Попробуем поиск по id
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
            
            if not cash_desk:
                print(f"⚠️ Cash desk {cash_desk_id} not found for update_transaction")
                return
            cash_desk_name = cash_desk["name"]
            print(f"✅ Found cash desk: {cash_desk_name}")
            
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            tx_sheet_name = f"Транзакции_{cash_desk_name}"
            
            worksheet = self._get_or_create_cash_desk_sheet(spreadsheet, tx_sheet_name, "transactions")

            # 2. Находим строку по ID транзакции (в колонке L, индекс 11)
            all_values = worksheet.get_all_values()
            row_number_to_update = -1

            for i, row in enumerate(all_values):
                # ID в 12-й колонке (индекс 11)
                if len(row) > 11 and row[11] == str(transaction_id):
                    row_number_to_update = i + 1 # gspread нумерация с 1
                    break
            
            if row_number_to_update != -1:
                # 3. Форматируем НОВУЮ строку
                new_row_data = self._format_transaction_row_simple(updated_data)
                
                # 4. Обновляем всю строку
                range_to_update = f"A{row_number_to_update}:L{row_number_to_update}"
                worksheet.update(range_to_update, [new_row_data], value_input_option='RAW')
             
            
                print(f"✅ Transaction {transaction_id} updated in sheet '{tx_sheet_name}'")
            else:
                print(f"⚠️ Transaction {transaction_id} not found in sheet '{tx_sheet_name}' to update")
            self.sync_aggregate_report(tenant_id)

        except Exception as e:
            print(f"❌ Failed to update transaction in Google Sheets: {e}")

    def delete_transaction(self, transaction_id: str, tenant_id: str = None, cash_desk_id: str = None):
        """
        (ПЕРЕРАБОТАНО) Удаляет транзакцию с листа, специфичного для кассы.
        """
        if not tenant_id or not cash_desk_id or not self.is_enabled_for_tenant(tenant_id):
            return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"):
            return

        try:
            # 1. Получаем имя кассы
            print(f"🔍 Looking for cash desk with _id: {cash_desk_id}, tenant_id: {tenant_id}")
            cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
            if not cash_desk:
                # Попробуем поиск по id
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
            
            if not cash_desk:
                print(f"⚠️ Cash desk {cash_desk_id} not found for delete_transaction")
                return
            cash_desk_name = cash_desk["name"]
            print(f"✅ Found cash desk: {cash_desk_name}")

            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])
            tx_sheet_name = f"Транзакции_{cash_desk_name}"
            worksheet = self._get_or_create_cash_desk_sheet(spreadsheet, tx_sheet_name, "transactions")

            # 2. Находим строку по ID (в колонке L, индекс 11)
            all_values = worksheet.get_all_values()
            row_number_to_delete = -1

            for i, row in enumerate(all_values):
                # ID в 12-й колонке (индекс 11)
                if len(row) > 11 and row[11] == str(transaction_id):
                    row_number_to_delete = i + 1 # gspread нумерация с 1
                    break

            if row_number_to_delete != -1:
                # 3. Удаляем строку
                worksheet.delete_rows(row_number_to_delete)
                
                print(f"✅ Transaction {transaction_id} deleted from sheet '{tx_sheet_name}'")
            else:
                print(f"⚠️ Transaction {transaction_id} not found in sheet '{tx_sheet_name}' to delete")
            self.sync_aggregate_report(tenant_id)

        except Exception as e:
            print(f"❌ Failed to delete transaction from Google Sheets: {e}")
    
    def resync_cash_desk(self, cash_desk_id: str, tenant_id: str):
        """
        (НОВАЯ ФУНКЦИЯ) Принудительно перезаписывает листы кассы после Undo.
        """
        if not self.is_enabled_for_tenant(tenant_id): return
        
        settings = self.get_tenant_settings(tenant_id)
        if not settings or not settings.get("spreadsheet_id"): return
        
        try:
            # 1. Получаем имя кассы
            print(f"🔍 Looking for cash desk with _id: {cash_desk_id}, tenant_id: {tenant_id}")
            cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
            if not cash_desk:
                # Попробуем поиск по id
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
            
            if not cash_desk:
                print(f"⚠️ Cash desk {cash_desk_id} not found for resync")
                return
            cash_desk_name = cash_desk["name"]
            print(f"✅ Found cash desk: {cash_desk_name}")

            print(f"🔄 Resyncing Google Sheets for cash desk '{cash_desk_name}'...")

            # 2. Получаем все актуальные данные из БД
            transactions = list(db.transactions.find({"cash_desk_id": cash_desk_id}))
            cash_items = list(db.cash.find({"cash_desk_id": cash_desk_id}))
            
            pipeline = [
                {"$match": {"cash_desk_id": cash_desk_id, "profit_currency": {"$ne": None}}},
                {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
            ]
            profit_results = list(db.transactions.aggregate(pipeline))
            
            cash_status = {item["asset"]: item["balance"] for item in cash_items}
            realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results}

            # 3. Открываем таблицу
            spreadsheet = self.client.open_by_key(settings["spreadsheet_id"])

            # 4. Перезаписываем лист ТРАНЗАКЦИЙ
            tx_sheet_name = f"Транзакции_{cash_desk_name}"
            transactions_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, tx_sheet_name, "transactions")
            self._sync_transactions_sheet(transactions_sheet, transactions, cash_desk_name)

            # 5. Перезаписываем лист КАССЫ
            cash_sheet_name = f"Касса_{cash_desk_name}"
            cash_sheet = self._get_or_create_cash_desk_sheet(spreadsheet, cash_sheet_name, "cash_summary")
            self._sync_cash_sheet(cash_sheet, cash_status, realized_profits, cash_desk_name)
            
            print(f"✅ Resync complete for '{cash_desk_name}'")
            self.sync_aggregate_report(tenant_id)
        except Exception as e:
            print(f"❌ Failed to resync Google Sheets for {cash_desk_id}: {e}")

    def _sync_transactions_sheet(self, sheet, transactions: List[Dict], cash_desk_name: str):
        """Синхронизация листа транзакций для конкретной кассы"""
        sheet.clear()
        all_data = []
        headers = [
            f"ТРАНЗАКЦИИ - {cash_desk_name.upper()}", "", "", "", "", "", "", "", "", "", "",
            "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
        ]
        all_data.append(headers)
        all_data.append([""] * 13)
        column_headers = [
            "Дата/Время", "Тип операции", "Принял", "Количество", 
            "Выдал", "Количество", "Курс", "Комиссия %", 
            "Прибыль", "Валюта прибыли", "Примечание", "Id"
        ]
        all_data.append(column_headers)
        
        for tx in transactions:
            all_data.append(self._format_transaction_row_simple(tx))
        
        if all_data:
            sheet.update(f'A1:M{len(all_data)}', all_data, value_input_option='RAW')
        
    def _sync_cash_sheet(self, sheet, cash_status: Dict, realized_profits: Dict, cash_desk_name: str):
        """Синхронизация листа кассы для конкретной кассы"""
        sheet.clear()
        all_data = []
        headers = [
            f"КАССА - {cash_desk_name.upper()}", "", "", "",
            "Последнее обновление:", datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")
        ]
        all_data.append(headers)
        all_data.append([""] * 6)
        
        all_data.append(["БАЛАНСЫ КАССЫ"])
        all_data.append(["Валюта", "Баланс"])
        for asset, balance in cash_status.items():
            all_data.append([asset, balance])
        
        all_data.append([""] * 6)
        all_data.append([""] * 6)
        
        all_data.append(["РЕАЛИЗОВАННАЯ ПРИБЫЛЬ"])
        all_data.append(["Валюта", "Прибыль"])
        for currency, profit in realized_profits.items():
            if profit != 0:
                all_data.append([currency, profit])
        
        if all_data:
            sheet.update(f'A1:F{len(all_data)}', all_data, value_input_option='RAW')

sheets_manager = GoogleSheetsManager()