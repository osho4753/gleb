"""
Роутер для системных операций
"""
from fastapi import APIRouter
from ..db import db

router = APIRouter(tags=["system"])


@router.get("/")
def root():
    """Корневой эндпоинт для проверки работы API"""
    return {"message": "Exchange API is running", "status": "ok"}


@router.get("/health")
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Проверяем соединение с базой данных
        db.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.delete("/reset-all")
def reset_cash_delete():
    """Полностью очищает кассу — все валюты и балансы (DELETE метод)"""
    result = db.cash.delete_many({})
    return {
        "message": "Cash register has been reset",
        "deleted_count": result.deleted_count
    }


@router.delete("/reset-all-transactions")
def reset_transactions():
    """Полностью очищает коллекцию транзакций"""
    result = db.transactions.delete_many({})
    return {
        "message": "All transactions have been deleted",
        "deleted_count": result.deleted_count
    }


@router.delete("/reset-fiat-lots")  
def reset_fiat_lots():
    """Полностью очищает коллекцию фиатных лотов"""
    result = db.fiat_lots.delete_many({})
    return {
        "message": "All fiat lots have been deleted",
        "deleted_count": result.deleted_count
    }


@router.delete("/reset-pnl-matches")
def reset_pnl_matches():
    """Полностью очищает коллекцию PnL матчей"""
    result = db.pnl_matches.delete_many({})
    return {
        "message": "All PnL matches have been deleted", 
        "deleted_count": result.deleted_count
    }


@router.delete("/reset-all-data")
def reset_all_data():
    """Полностью очищает все данные"""
    cash_result = db.cash.delete_many({})
    tx_result = db.transactions.delete_many({})
    lots_result = db.fiat_lots.delete_many({})
    pnl_result = db.pnl_matches.delete_many({})
    
    return {
        "message": "All data has been reset",
        "cash_deleted": cash_result.deleted_count,
        "transactions_deleted": tx_result.deleted_count,
        "fiat_lots_deleted": lots_result.deleted_count,
        "pnl_matches_deleted": pnl_result.deleted_count
    }