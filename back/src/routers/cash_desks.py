from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
import uuid
from datetime import datetime

from ..db import db
from ..models import CashDesk, CreateCashDesk, UpdateCashDesk
from ..auth import get_current_tenant

router = APIRouter(prefix="/cash-desks", tags=["cash_desks"])

# Коллекция касс
cash_desks_collection = db["cash_desks"]

@router.get("/", response_model=List[CashDesk])
async def get_cash_desks(
    include_deleted: bool = Query(False, description="Включить удаленные кассы в результат"),
    current_tenant: str = Depends(get_current_tenant)
):
    """Получить кассы тенанта"""
    if include_deleted:
        # Возвращаем все кассы (активные и удаленные)
        cash_desks = list(cash_desks_collection.find({"tenant_id": current_tenant}))
    else:
        # По умолчанию возвращаем только активные кассы
        cash_desks = list(cash_desks_collection.find({
            "tenant_id": current_tenant,
            "is_active": True
        }))
    return cash_desks

@router.get("/deleted", response_model=List[CashDesk])
async def get_deleted_cash_desks(
    current_tenant: str = Depends(get_current_tenant)
):
    """Получить удаленные кассы тенанта для возможности восстановления"""
    deleted_cash_desks = list(cash_desks_collection.find({
        "tenant_id": current_tenant,
        "is_active": False
    }))
    return deleted_cash_desks

@router.post("/", response_model=CashDesk)
async def create_cash_desk(
    cash_desk_data: CreateCashDesk,
    current_tenant: str = Depends(get_current_tenant)
):
    """Создать новую кассу"""
    
    # Проверяем, что касса с таким именем уже не существует у данного тенанта
    existing = cash_desks_collection.find_one({
        "tenant_id": current_tenant,
        "name": cash_desk_data.name,
        "is_active": True
    })
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Касса с названием '{cash_desk_data.name}' уже существует"
        )
    
    # Создаем уникальный ID для кассы
    cash_desk_id = f"desk_{uuid.uuid4().hex[:8]}"
    
    cash_desk = CashDesk(
        id=cash_desk_id,
        tenant_id=current_tenant,
        name=cash_desk_data.name
    )
    
    # Сохраняем в БД (конвертируем обратно в _id для MongoDB)
    cash_desk_dict = cash_desk.dict(by_alias=True)
    cash_desks_collection.insert_one(cash_desk_dict)
    
    return cash_desk

@router.get("/{cash_desk_id}", response_model=CashDesk)
async def get_cash_desk(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """Получить конкретную кассу"""
    cash_desk = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    if not cash_desk:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    return CashDesk(**cash_desk)

@router.put("/{cash_desk_id}", response_model=CashDesk)
async def update_cash_desk(
    cash_desk_id: str,
    update_data: UpdateCashDesk,
    current_tenant: str = Depends(get_current_tenant)
):
    """Обновить кассу"""
    
    # Проверяем существование кассы и права доступа
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    # Если меняем название, проверяем уникальность
    if update_data.name and update_data.name != existing["name"]:
        name_conflict = cash_desks_collection.find_one({
            "tenant_id": current_tenant,
            "name": update_data.name,
            "is_active": True,
            "_id": {"$ne": cash_desk_id}  # Исключаем текущую кассу
        })
        if name_conflict:
            raise HTTPException(
                status_code=400,
                detail=f"Касса с названием '{update_data.name}' уже существует"
            )
    
    # Обновляем только переданные поля
    update_fields = {k: v for k, v in update_data.dict().items() if v is not None}
    if update_fields:
        cash_desks_collection.update_one(
            {"_id": cash_desk_id, "tenant_id": current_tenant},
            {"$set": update_fields}
        )
    
    # Возвращаем обновленную кассу
    updated = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    return CashDesk(**updated)

@router.get("/{cash_desk_id}/usage-info")
async def get_cash_desk_usage_info(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """Получить информацию об использовании кассы для безопасного удаления"""
    
    # Проверяем существование кассы и права доступа
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    # Собираем информацию об использовании кассы
    usage_info = await _collect_usage_info(cash_desk_id, current_tenant)
    
    return {
        "cash_desk": {
            "id": cash_desk_id,
            "name": existing["name"],
            "is_active": existing.get("is_active", True)
        },
        "usage_info": usage_info,
        "can_be_safely_deleted": not _has_critical_data(usage_info)
    }

@router.delete("/{cash_desk_id}")
async def delete_cash_desk_safe(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant),
    force: bool = Query(False, description="Принудительно удалить кассу даже при наличии активных данных")
):
    """Безопасно удалить кассу с проверками"""
    
    # Проверяем существование кассы и права доступа
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    # Собираем информацию об использовании
    usage_info = await _collect_usage_info(cash_desk_id, current_tenant)
    has_critical_data = _has_critical_data(usage_info)
    
    # Если есть критичные данные и не установлен флаг force - возвращаем ошибку
    if has_critical_data and not force:
        return {
            "error": "cash_desk_has_active_data",
            "message": "Касса содержит активные данные и не может быть безопасно удалена",
            "usage_info": usage_info
        }
    
    # Каскадное удаление всех связанных данных
    deleted_data_summary = await _cascade_delete_cash_desk_data(cash_desk_id, current_tenant)
    
    # Удаляем саму кассу
    now = datetime.utcnow()
    cash_desks_collection.update_one(
        {"_id": cash_desk_id, "tenant_id": current_tenant},
        {
            "$set": {
                "is_active": False,
                "deleted_at": now.isoformat()
            }
        }
    )
    
    response = {
        "message": f"Касса '{existing['name']}' и все связанные данные удалены",
        "deleted_data": deleted_data_summary
    }
    
    if has_critical_data and force:
        response["warning"] = "Касса удалена принудительно с всеми данными."
    
    return response

@router.post("/{cash_desk_id}/restore")
async def restore_cash_desk(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """Восстановить удаленную кассу"""
    
    # Проверяем существование кассы и права доступа
    existing = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant
    })
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    
    if existing.get("is_active", True):
        raise HTTPException(
            status_code=400,
            detail="Касса уже активна"
        )
    
    # Проверяем конфликт имен
    name_conflict = cash_desks_collection.find_one({
        "tenant_id": current_tenant,
        "name": existing["name"],
        "is_active": True,
        "_id": {"$ne": cash_desk_id}
    })
    if name_conflict:
        raise HTTPException(
            status_code=400,
            detail=f"Касса с названием '{existing['name']}' уже существует. Переименуйте существующую кассу или эту перед восстановлением."
        )
    
    # Восстанавливаем кассу
    cash_desks_collection.update_one(
        {"_id": cash_desk_id, "tenant_id": current_tenant},
        {
            "$set": {"is_active": True},
            "$unset": {"deleted_at": ""}
        }
    )
    
    return {"message": f"Касса '{existing['name']}' восстановлена"}

# Вспомогательные функции для анализа использования кассы
async def _collect_usage_info(cash_desk_id: str, tenant_id: str) -> dict:
    """Собрать информацию об использовании кассы"""
    
    usage_info = {
        "has_balances": False,
        "has_transactions": False,
        "has_fiat_lots": False,
        "has_pnl_matches": False,
        "details": {}
    }
    
    # Проверяем балансы
    non_zero_balances = list(db["balances"].find({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "balance": {"$ne": 0}
    }))
    if non_zero_balances:
        usage_info["has_balances"] = True
        usage_info["details"]["balances"] = [
            {"asset": b["asset"], "balance": b["balance"]}
            for b in non_zero_balances[:5]  # Первые 5 для примера
        ]
    
    # Проверяем транзакции
    transactions_count = db["transactions"].count_documents({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    if transactions_count > 0:
        usage_info["has_transactions"] = True
        usage_info["details"]["transactions_count"] = transactions_count
    
    # Проверяем фиатные лоты
    active_lots = list(db["fiat_lots"].find({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "remaining": {"$gt": 0}
    }))
    if active_lots:
        usage_info["has_fiat_lots"] = True
        usage_info["details"]["active_lots"] = [
            {"currency": lot["currency"], "remaining": lot["remaining"]}
            for lot in active_lots[:5]  # Первые 5 для примера
        ]
    
    # Проверяем PnL матчи
    pnl_matches_count = db["pnl_matches"].count_documents({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    if pnl_matches_count > 0:
        usage_info["has_pnl_matches"] = True
        usage_info["details"]["pnl_matches_count"] = pnl_matches_count
    
    return usage_info

def _has_critical_data(usage_info: dict) -> bool:
    """Проверить, есть ли критичные данные, которые мешают безопасному удалению"""
    return (
        usage_info["has_balances"] or 
        usage_info["has_fiat_lots"]
        # Транзакции и PnL матчи не считаем критичными для удаления
    )

async def _cascade_delete_cash_desk_data(cash_desk_id: str, tenant_id: str) -> dict:
    """Каскадно удалить все данные связанные с кассой"""
    
    deleted_summary = {
        "balances_deleted": 0,
        "transactions_deleted": 0,
        "fiat_lots_deleted": 0,
        "pnl_matches_deleted": 0
    }
    
    # Удаляем балансы
    balances_result = db["balances"].delete_many({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    deleted_summary["balances_deleted"] = balances_result.deleted_count
    
    # Удаляем транзакции
    transactions_result = db["transactions"].delete_many({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    deleted_summary["transactions_deleted"] = transactions_result.deleted_count
    
    # Удаляем фиатные лоты
    fiat_lots_result = db["fiat_lots"].delete_many({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    deleted_summary["fiat_lots_deleted"] = fiat_lots_result.deleted_count
    
    # Удаляем PnL матчи
    pnl_matches_result = db["pnl_matches"].delete_many({
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id
    })
    deleted_summary["pnl_matches_deleted"] = pnl_matches_result.deleted_count
    
    return deleted_summary

# Вспомогательная функция для проверки доступа к кассе
async def verify_cash_desk_access(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
) -> CashDesk:
    """Проверить доступ к кассе и вернуть её данные"""
    cash_desk = cash_desks_collection.find_one({
        "_id": cash_desk_id,
        "tenant_id": current_tenant,
        "is_active": True
    })
    if not cash_desk:
        raise HTTPException(
            status_code=404,
            detail="Касса не найдена или нет доступа"
        )
    return CashDesk(**cash_desk)