"""
Улучшенная реализация удаления (деактивации) кассы с проверками безопасности
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from datetime import datetime

from ..db import db
from ..models import CashDesk
from ..auth import get_current_tenant
from ..history_manager import history_manager

router = APIRouter(prefix="/cash-desks", tags=["cash_desks_enhanced"])

# Коллекции
cash_desks_collection = db["cash_desks"]


async def check_cash_desk_usage(cash_desk_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Проверить, используется ли касса (есть ли активные данные)
    Возвращает подробную информацию об использовании кассы
    """
    usage_info = {
        "has_balances": False,
        "has_transactions": False,
        "has_fiat_lots": False,
        "has_pnl_matches": False,
        "details": {}
    }
    
    # Проверяем балансы
    cash_balances = list(db.cash.find({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "balance": {"$ne": 0}  # Ненулевые балансы
    }))
    
    if cash_balances:
        usage_info["has_balances"] = True
        usage_info["details"]["balances"] = [
            {"asset": item["asset"], "balance": item["balance"]} 
            for item in cash_balances
        ]
    
    # Проверяем транзакции
    transactions_count = db.transactions.count_documents({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    
    if transactions_count > 0:
        usage_info["has_transactions"] = True
        usage_info["details"]["transactions_count"] = transactions_count
    
    # Проверяем фиатные лоты
    active_lots = list(db.fiat_lots.find({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "remaining": {"$gt": 0}  # Активные лоты
    }))
    
    if active_lots:
        usage_info["has_fiat_lots"] = True
        usage_info["details"]["active_lots"] = [
            {"currency": lot["currency"], "remaining": lot["remaining"]} 
            for lot in active_lots
        ]
    
    # Проверяем PnL матчи
    pnl_matches_count = db.pnl_matches.count_documents({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    
    if pnl_matches_count > 0:
        usage_info["has_pnl_matches"] = True
        usage_info["details"]["pnl_matches_count"] = pnl_matches_count
    
    return usage_info


@router.delete("/{cash_desk_id}")
async def delete_cash_desk_enhanced(
    cash_desk_id: str,
    force: bool = False,  # Принудительное удаление
    current_tenant: str = Depends(get_current_tenant)
):
    """
    Улучшенная деактивация кассы с проверками безопасности
    
    Parameters:
    - cash_desk_id: ID кассы для деактивации
    - force: Принудительная деактивация (игнорировать активные данные)
    """
    
    # Проверяем существование кассы
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    # Проверяем, не деактивирована ли касса уже
    if not existing.get("is_active", True):
        return {
            "message": f"Касса '{existing['name']}' уже деактивирована",
            "was_already_inactive": True
        }
    
    # Сохраняем снимок состояния ПЕРЕД деактивацией
    history_manager.save_snapshot(
        operation_type="deactivate_cash_desk",
        description=f"Deactivating cash desk '{existing['name']}' (ID: {cash_desk_id})",
        tenant_id=current_tenant
    )
    
    # Проверяем использование кассы
    usage_info = await check_cash_desk_usage(cash_desk_id, current_tenant)
    
    # Определяем, есть ли активные данные
    has_active_data = any([
        usage_info["has_balances"],
        usage_info["has_fiat_lots"]
    ])
    
    # Если есть активные данные и не указан force - предупреждаем
    if has_active_data and not force:
        return {
            "error": "cash_desk_has_active_data",
            "message": f"Касса '{existing['name']}' содержит активные данные и не может быть деактивирована",
            "usage_info": usage_info,
            "suggestion": "Используйте параметр 'force=true' для принудительной деактивации или очистите данные кассы"
        }
    
    # Выполняем деактивацию
    cash_desks_collection.update_one(
        {"_id": cash_desk_id, "tenant_id": current_tenant},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": datetime.utcnow(),
                "deactivated_by": "user_action"
            }
        }
    )
    
    response = {
        "message": f"Касса '{existing['name']}' успешно деактивирована",
        "cash_desk_id": cash_desk_id,
        "was_forced": force,
        "usage_info": usage_info
    }
    
    # Если были активные данные - предупреждаем
    if has_active_data:
        response["warning"] = "Касса содержала активные данные. Они останутся в системе, но станут недоступными"
        response["recommendations"] = [
            "Проверьте балансы других касс",
            "Убедитесь, что все транзакции завершены",
            "При необходимости переместите активы в другую кассу"
        ]
    
    return response


@router.get("/{cash_desk_id}/usage-info")
async def get_cash_desk_usage_info(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """
    Получить информацию об использовании кассы перед удалением
    """
    # Проверяем существование кассы
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    usage_info = await check_cash_desk_usage(cash_desk_id, current_tenant)
    
    return {
        "cash_desk": {
            "id": cash_desk_id,
            "name": existing["name"],
            "is_active": existing.get("is_active", True)
        },
        "usage_info": usage_info,
        "can_be_safely_deleted": not any([
            usage_info["has_balances"],
            usage_info["has_fiat_lots"]
        ])
    }


@router.post("/{cash_desk_id}/restore")
async def restore_cash_desk(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """
    Восстановить деактивированную кассу
    """
    # Проверяем существование кассы
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    # Проверяем, деактивирована ли касса
    if existing.get("is_active", True):
        return {
            "message": f"Касса '{existing['name']}' уже активна",
            "was_already_active": True
        }
    
    # Сохраняем снимок состояния ПЕРЕД восстановлением
    history_manager.save_snapshot(
        operation_type="restore_cash_desk",
        description=f"Restoring cash desk '{existing['name']}' (ID: {cash_desk_id})",
        tenant_id=current_tenant
    )
    
    # Восстанавливаем кассу
    cash_desks_collection.update_one(
        {"_id": cash_desk_id, "tenant_id": current_tenant},
        {
            "$set": {"is_active": True},
            "$unset": {
                "deactivated_at": "",
                "deactivated_by": ""
            }
        }
    )
    
    return {
        "message": f"Касса '{existing['name']}' успешно восстановлена",
        "cash_desk_id": cash_desk_id
    }


@router.get("/")
async def get_cash_desks_enhanced(
    include_inactive: bool = False,  # Включить деактивированные кассы
    current_tenant: str = Depends(get_current_tenant)
):
    """
    Получить список касс с возможностью включения деактивированных
    """
    query = {"tenant_id": current_tenant}
    
    if not include_inactive:
        query["is_active"] = True
    
    cash_desks = list(cash_desks_collection.find(query))
    
    # Добавляем информацию об использовании для каждой кассы
    enhanced_desks = []
    for desk in cash_desks:
        enhanced_desk = desk.copy()
        
        # Для деактивированных касс добавляем краткую информацию об использовании
        if not desk.get("is_active", True):
            usage_info = await check_cash_desk_usage(desk["_id"], current_tenant)
            enhanced_desk["usage_summary"] = {
                "has_data": any([
                    usage_info["has_balances"],
                    usage_info["has_transactions"], 
                    usage_info["has_fiat_lots"],
                    usage_info["has_pnl_matches"]
                ])
            }
        
        enhanced_desks.append(enhanced_desk)
    
    return {
        "cash_desks": enhanced_desks,
        "total_count": len(enhanced_desks),
        "active_count": len([d for d in enhanced_desks if d.get("is_active", True)]),
        "inactive_count": len([d for d in enhanced_desks if not d.get("is_active", True)])
    }