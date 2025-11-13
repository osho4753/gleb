"""
Утилиты для работы с кассами (cash desks)
"""
from fastapi import HTTPException
from ..db import db
from ..models import CashDesk

def verify_cash_desk_access_util(cash_desk_id: str, tenant_id: str) -> CashDesk:
    """Проверить доступ к кассе и вернуть её данные"""
    cash_desks_collection = db["cash_desks"]
    
    cash_desk = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": tenant_id,
        "is_active": True
    })
    
    if not cash_desk:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    return CashDesk(**cash_desk)

def get_tenant_cash_desks(tenant_id: str) -> list:
    """Получить все активные кассы тенанта"""
    cash_desks_collection = get_collection("cash_desks")
    
    cash_desks = list(cash_desks_collection.find({
        "tenant_id": tenant_id,
        "is_active": True
    }))
    
    return [CashDesk(**desk) for desk in cash_desks]