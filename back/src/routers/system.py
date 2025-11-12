"""
Роутер для системных операций
"""
from fastapi import APIRouter
from ..db import db
from ..google_sheets import sheets_manager

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
    
    # Очищаем Google Sheets
    try:
        sheets_manager.clear_all_transactions()
    except Exception as e:
        print(f"Failed to clear Google Sheets: {e}")
    
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
    
    # Очищаем Google Sheets
    try:
        sheets_manager.clear_all_transactions()
        # Обновляем сводный лист (пустой)
        sheets_manager.update_summary_sheet({}, {})
    except Exception as e:
        print(f"Failed to clear Google Sheets: {e}")
    
    return {
        "message": "All data has been reset",
        "cash_deleted": cash_result.deleted_count,
        "transactions_deleted": tx_result.deleted_count,
        "fiat_lots_deleted": lots_result.deleted_count,
        "pnl_matches_deleted": pnl_result.deleted_count
    }


@router.post("/sheets/update-summary")
def update_sheets_summary():
    """Ручное обновление сводного листа Google Sheets"""
    try:
        cash_items = list(db.cash.find({}, {"_id": 0}))
        cash_status = {item["asset"]: item["balance"] for item in cash_items}
        
        pipeline = [
            {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
        ]
        profit_results = list(db.transactions.aggregate(pipeline))
        realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
        
        sheets_manager.update_summary_sheet(cash_status, realized_profits)
        
        return {
            "message": "Summary sheet updated successfully",
            "cash_currencies": len(cash_status),
            "profit_currencies": len(realized_profits)
        }
    except Exception as e:
        return {
            "message": "Failed to update summary sheet",
            "error": str(e)
        }