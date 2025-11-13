"""
Административный роутер для управления tenants
Доступен только для супер-администратора
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from datetime import datetime
from ..db import db
from ..models import CreateTenant, Tenant
from ..auth import AuthenticationService
from ..constants import CURRENCIES

router = APIRouter(prefix="/admin", tags=["admin"])

# Супер-админ пароль (в продакшене должен быть в переменных окружения)
SUPER_ADMIN_PASSWORD = "super_secret_admin_2024"


async def verify_super_admin(
    x_super_admin_key: Optional[str] = Header(None, alias="X-Super-Admin-Key")
):
    """Проверяет супер-админские права"""
    if x_super_admin_key != SUPER_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=403,
            detail="Super admin access required"
        )
    return True


@router.post("/tenants", dependencies=[Depends(verify_super_admin)])
def create_tenant(tenant_data: CreateTenant):
    """Создает нового tenant"""
    try:
        tenant_id = AuthenticationService.create_tenant(tenant_data)
        return {
            "message": "Tenant created successfully",
            "tenant_id": tenant_id,
            "name": tenant_data.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.get("/tenants", dependencies=[Depends(verify_super_admin)])
def list_tenants():
    """Получает список всех tenants"""
    try:
        tenants = list(db.tenants.find({}, {"master_key_hash": 0}))
        
        # Добавляем статистику по каждому tenant
        for tenant in tenants:
            tenant_id = tenant["_id"]
            
            # Количество транзакций
            tx_count = db.transactions.count_documents({"tenant_id": tenant_id})
            
            # Баланс кассы
            cash_balances = {}
            cash_docs = db.cash.find({"tenant_id": tenant_id})
            for cash_doc in cash_docs:
                cash_balances[cash_doc["asset"]] = cash_doc.get("balance", 0)
            
            tenant["stats"] = {
                "transaction_count": tx_count,
                "cash_balances": cash_balances
            }
        
        return {
            "tenants": tenants,
            "total_count": len(tenants)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tenants: {str(e)}"
        )


@router.get("/tenants/{tenant_id}", dependencies=[Depends(verify_super_admin)])
def get_tenant(tenant_id: str):
    """Получает информацию о конкретном tenant"""
    try:
        tenant = AuthenticationService.get_tenant_info(tenant_id)
        
        # Добавляем детальную статистику
        stats = {
            "transaction_count": db.transactions.count_documents({"tenant_id": tenant_id}),
            "fiat_lots_count": db.fiat_lots.count_documents({"tenant_id": tenant_id}),
            "pnl_matches_count": db.pnl_matches.count_documents({"tenant_id": tenant_id}),
            "history_snapshots_count": db.history_snapshots.count_documents({"tenant_id": tenant_id})
        }
        
        # Баланс кассы
        cash_balances = {}
        cash_docs = db.cash.find({"tenant_id": tenant_id})
        for cash_doc in cash_docs:
            cash_balances[cash_doc["asset"]] = cash_doc.get("balance", 0)
        
        tenant["stats"] = stats
        tenant["cash_balances"] = cash_balances
        
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant info: {str(e)}"
        )


@router.put("/tenants/{tenant_id}/password", dependencies=[Depends(verify_super_admin)])
def change_tenant_password(tenant_id: str, new_password: str):
    """Изменяет пароль tenant"""
    try:
        # Проверяем существование tenant
        tenant = db.tenants.find_one({"_id": tenant_id})
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Хэшируем новый пароль
        password_hash, _ = AuthenticationService.hash_password(new_password)
        
        # Обновляем пароль
        result = db.tenants.update_one(
            {"_id": tenant_id},
            {
                "$set": {
                    "master_key_hash": password_hash,
                    "password_changed_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update password")
        
        return {
            "message": "Password updated successfully",
            "tenant_id": tenant_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change password: {str(e)}"
        )


@router.put("/tenants/{tenant_id}/status", dependencies=[Depends(verify_super_admin)])
def toggle_tenant_status(tenant_id: str, is_active: bool):
    """Активирует/деактивирует tenant"""
    try:
        result = db.tenants.update_one(
            {"_id": tenant_id},
            {
                "$set": {
                    "is_active": is_active,
                    "status_changed_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        status_text = "activated" if is_active else "deactivated"
        return {
            "message": f"Tenant {status_text} successfully",
            "tenant_id": tenant_id,
            "is_active": is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update tenant status: {str(e)}"
        )


@router.delete("/tenants/{tenant_id}", dependencies=[Depends(verify_super_admin)])
def delete_tenant(tenant_id: str, confirm_delete: bool = False):
    """
    Удаляет tenant и все связанные данные
    ОСТОРОЖНО: Операция необратима!
    """
    if not confirm_delete:
        raise HTTPException(
            status_code=400,
            detail="Please confirm deletion by setting confirm_delete=true"
        )
    
    try:
        # Проверяем существование tenant
        tenant = db.tenants.find_one({"_id": tenant_id})
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Удаляем все данные tenant
        collections_to_clean = [
            "transactions", "cash", "fiat_lots", 
            "pnl_matches", "history_snapshots"
        ]
        
        deleted_counts = {}
        for collection_name in collections_to_clean:
            collection = getattr(db, collection_name)
            result = collection.delete_many({"tenant_id": tenant_id})
            deleted_counts[collection_name] = result.deleted_count
        
        # Удаляем самого tenant
        tenant_result = db.tenants.delete_one({"_id": tenant_id})
        
        return {
            "message": "Tenant and all associated data deleted successfully",
            "tenant_id": tenant_id,
            "tenant_name": tenant.get("name", "Unknown"),
            "deleted_counts": deleted_counts
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete tenant: {str(e)}"
        )


@router.post("/migrate-existing-data", dependencies=[Depends(verify_super_admin)])
def migrate_existing_data_to_default_tenant():
    """
    Миграция существующих данных к дефолтному tenant
    Используется при первой настройке системы
    """
    default_tenant_id = "default"
    
    try:
        # Создаем дефолтного tenant, если его нет
        existing_tenant = db.tenants.find_one({"_id": default_tenant_id})
        if not existing_tenant:
            default_tenant = CreateTenant(
                tenant_id=default_tenant_id,
                master_key="admin123",  # Пароль по умолчанию
                name="Default Tenant"
            )
            AuthenticationService.create_tenant(default_tenant)
            print(f"Created default tenant with password: admin123")
        
        # Миграция коллекций
        collections_to_migrate = [
            "transactions", "cash", "fiat_lots", 
            "pnl_matches", "history_snapshots"
        ]
        
        migrated_counts = {}
        for collection_name in collections_to_migrate:
            collection = getattr(db, collection_name)
            
            # Обновляем документы без tenant_id
            result = collection.update_many(
                {"tenant_id": {"$exists": False}},
                {"$set": {"tenant_id": default_tenant_id}}
            )
            migrated_counts[collection_name] = result.modified_count
        
        return {
            "message": "Data migration completed successfully",
            "default_tenant_id": default_tenant_id,
            "default_password": "admin123",
            "migrated_counts": migrated_counts
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )