"""
Общие константы приложения
"""
import os

# Фиатные валюты
FIAT_ASSETS = ["CZK", "USD", "EUR"]

# Специальные фиатные валюты с особой логикой расчета
SPECIAL_FIAT = ["CZK"]

# Валюты с обратным курсом (USDT/фиат) - для них нужно умножать USDT*курс=фиат
SPECIAL_FIAT_FOR_USDT = ["EUR"]

# Остальные валюты (CZK, USD) используют прямой курс (фиат/USDT) - для них нужно делить USDT/курс=фиат
# Примеры:
# - EUR: курс 1.15 = 1.15 USDT за 1 EUR → USDT→EUR: умножаем (1 USDT * 1.15 = 1.15 EUR) - НЕТ! Делим (1 USDT / 1.15 = 0.87 EUR)
# - CZK: курс 21.0 = 21.0 CZK за 1 USDT → USDT→CZK: делим (1 USDT / 21.0 = 0.048 CZK) - НЕТ! Умножаем (1 USDT * 21.0 = 21.0 CZK)
# ИТАК:
# - EUR (обратный): PnL_USDT * курс = PnL_EUR  
# - CZK/USD (прямой): PnL_USDT / курс = PnL_фиат
# Список валют для инициализации кассы
CURRENCIES = ["USD", "USDT", "EUR", "CZK"]

# Google Sheets Configuration
GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS_PATH", 
    "credentials/google-sheets-key.json"
)
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")