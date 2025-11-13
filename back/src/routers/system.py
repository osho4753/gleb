"""
Роутер для системных операций
"""
from fastapi import APIRouter, HTTPException, Depends
from ..db import db
from ..google_sheets import sheets_manager
from ..history_manager import history_manager
from ..auth import get_current_tenant

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


@router.get("/tenant-info")
def get_tenant_info(tenant_id: str = Depends(get_current_tenant)):
    """Получить информацию о текущем tenant"""
    try:
        # Получаем информацию о tenant из базы данных
        # Ищем по _id, так как tenant'ы сохраняются с _id как основным ключом
        tenant = db.tenants.find_one({"_id": tenant_id})
        
        if not tenant:
            return {
                "tenant_id": tenant_id,
                "name": f"Организация {tenant_id}",
                "is_active": True,
                "created_at": None
            }
        
        return {
            "tenant_id": tenant.get("_id", tenant_id),  # _id является tenant_id
            "name": tenant.get("name", f"Организация {tenant_id}"),
            "is_active": tenant.get("is_active", True),
            "created_at": tenant.get("created_at")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tenant info: {str(e)}")


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
def reset_all_data(tenant_id: str = Depends(get_current_tenant)):
    """Полностью очищает все данные для текущего tenant"""
    cash_result = db.cash.delete_many({"tenant_id": tenant_id})
    tx_result = db.transactions.delete_many({"tenant_id": tenant_id})
    lots_result = db.fiat_lots.delete_many({"tenant_id": tenant_id})
    pnl_result = db.pnl_matches.delete_many({"tenant_id": tenant_id})
    
    # Очищаем историю снимков для данного tenant
    history_result = history_manager.clear_history(tenant_id)
    
    # Очищаем Google Sheets
    try:
        # Обновляем сводный лист (пустой)
        sheets_manager.update_cash_and_profits({}, {}, tenant_id)
    except Exception as e:
        print(f"Failed to clear Google Sheets: {e}")
    
    return {
        "message": "All data has been reset",
        "cash_deleted": cash_result.deleted_count,
        "transactions_deleted": tx_result.deleted_count,
        "fiat_lots_deleted": lots_result.deleted_count,
        "pnl_matches_deleted": pnl_result.deleted_count,
        "history_snapshots_deleted": history_result
    }


@router.post("/undo")
def undo_last_operation(tenant_id: str = Depends(get_current_tenant)):
    """Отменяет последнюю операцию для конкретного tenant, восстанавливая предыдущее состояние"""
    try:
        # Получаем последний снимок для конкретного tenant
        snapshot = history_manager.get_last_snapshot(tenant_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="No operations to undo")
        
        # Восстанавливаем состояние для конкретного tenant
        # (Google Sheets автоматически синхронизируется внутри restore_snapshot)
        success = history_manager.restore_snapshot(tenant_id=tenant_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to restore snapshot")
        
        return {
            "message": "Operation undone successfully",
            "restored_operation": snapshot.get("operation_type"),
            "restored_description": snapshot.get("description"),
            "restored_timestamp": snapshot.get("timestamp")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during undo: {str(e)}")


@router.get("/history")
def get_operation_history(limit: int = 10, tenant_id: str = Depends(get_current_tenant)):
    """Получает историю последних операций для конкретного tenant"""
    try:
        history = history_manager.get_history(limit=limit, tenant_id=tenant_id)
        return {
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@router.post("/sheets/update-summary")
def update_sheets_summary(tenant_id: str = Depends(get_current_tenant)):
    """Ручное обновление сводного листа Google Sheets для текущего tenant"""
    try:
        cash_items = list(db.cash.find({"tenant_id": tenant_id}, {"_id": 0}))
        cash_status = {item["asset"]: item["balance"] for item in cash_items}
        
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
        ]
        profit_results = list(db.transactions.aggregate(pipeline))
        realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
        
        sheets_manager.update_cash_and_profits(cash_status, realized_profits, tenant_id)
        
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