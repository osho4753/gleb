from fastapi import APIRouter, HTTPException, Depends
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
    current_tenant: str = Depends(get_current_tenant)
):
    """Получить все кассы тенанта"""
    cash_desks = list(cash_desks_collection.find({"tenant_id": current_tenant}))
    return cash_desks

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

@router.delete("/{cash_desk_id}")
async def delete_cash_desk(
    cash_desk_id: str,
    current_tenant: str = Depends(get_current_tenant)
):
    """Деактивировать кассу (мягкое удаление)"""
    
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
    
    # Мягкое удаление - деактивируем кассу
    cash_desks_collection.update_one(
        {"_id": cash_desk_id, "tenant_id": current_tenant},
        {"$set": {"is_active": False}}
    )
    
    return {"message": f"Касса '{existing['name']}' деактивирована"}

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