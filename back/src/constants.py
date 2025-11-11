"""
Общие константы приложения
"""
import os

# Фиатные валюты
FIAT_ASSETS = ["CZK", "USD", "EUR"]

# Специальные фиатные валюты с особой логикой расчета
SPECIAL_FIAT = ["CZK"]

# Список валют для инициализации кассы
CURRENCIES = ["USD", "USDT", "EUR", "CZK"]

# Google Sheets Configuration
GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS_PATH", 
    "credentials/google-sheets-key.json"
)
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")