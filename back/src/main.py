"""
Главный файл приложения FastAPI с подключением роутеров
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Импорт роутеров
from .routers import cash, transactions, system, admin, google_sheets

# Создание приложения FastAPI
app = FastAPI(title="Local Exchange Dashboard")

# Настройка CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Подключение роутеров
app.include_router(system.router)      # Системные операции (/, /health, /reset-*)
app.include_router(cash.router)        # Операции с кассой (/cash/*)
app.include_router(transactions.router) # Операции с транзакциями (/transactions/*)
app.include_router(admin.router)       # Административные операции (/admin/*)
app.include_router(google_sheets.router) # Google Sheets интеграция (/google-sheets/*)
