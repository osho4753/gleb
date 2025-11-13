"""
Модуль аутентификации для многопользовательской системы
"""
import hashlib
import secrets
from fastapi import HTTPException, Depends, Header
from typing import Optional
from .db import db
from .models import Tenant, CreateTenant


class AuthenticationService:
    """Сервис для управления аутентификацией tenants"""
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """
        Хэширует пароль с солью
        
        Returns:
            tuple: (hashed_password, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Используем SHA-256 с солью
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{password_hash}:{salt}", salt
    
    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """
        Проверяет пароль против хэша
        
        Args:
            password: Введенный пароль
            stored_hash: Сохраненный хэш в формате "hash:salt"
        """
        try:
            hash_part, salt = stored_hash.split(":")
            expected_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return expected_hash == hash_part
        except ValueError:
            return False
    
    @staticmethod
    def create_tenant(tenant_data: CreateTenant) -> str:
        """
        Создает нового tenant
        
        Returns:
            tenant_id: ID созданного tenant
        """
        # Проверяем, что tenant_id уникален
        existing_tenant = db.tenants.find_one({"_id": tenant_data.tenant_id})
        if existing_tenant:
            raise HTTPException(
                status_code=400, 
                detail=f"Tenant with ID '{tenant_data.tenant_id}' already exists"
            )
        
        # Хэшируем пароль
        password_hash, _ = AuthenticationService.hash_password(tenant_data.master_key)
        
        # Создаем tenant
        tenant_doc = {
            "_id": tenant_data.tenant_id,
            "master_key_hash": password_hash,
            "name": tenant_data.name,
            "created_at": tenant_data.created_at if hasattr(tenant_data, 'created_at') else None,
            "is_active": True
        }
        
        try:
            db.tenants.insert_one(tenant_doc)
            
            # Инициализируем кассу для нового tenant
            AuthenticationService._init_tenant_cash(tenant_data.tenant_id)
            
            return tenant_data.tenant_id
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create tenant: {str(e)}"
            )
    
    @staticmethod
    def _init_tenant_cash(tenant_id: str):
        """Инициализирует кассу для нового tenant"""
        from .constants import CURRENCIES
        
        cash_docs = []
        for currency in CURRENCIES:
            cash_docs.append({
                "tenant_id": tenant_id,
                "asset": currency,
                "balance": 0.0,
                "created_at": None,  # Будет установлено при первом депозите
            })
        
        if cash_docs:
            db.cash.insert_many(cash_docs)
    
    @staticmethod
    def authenticate_tenant(password: str) -> str:
        """
        Аутентифицирует tenant по паролю
        
        Returns:
            tenant_id: ID аутентифицированного tenant
        """
        # Ищем tenant по паролю
        tenants = list(db.tenants.find({"is_active": True}))
        
        for tenant in tenants:
            if AuthenticationService.verify_password(password, tenant["master_key_hash"]):
                return tenant["_id"]
        
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
    
    @staticmethod
    def get_tenant_info(tenant_id: str) -> dict:
        """Получает информацию о tenant"""
        tenant = db.tenants.find_one({"_id": tenant_id})
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found"
            )
        
        # Удаляем чувствительную информацию
        tenant.pop("master_key_hash", None)
        return tenant


# FastAPI Dependency для получения текущего tenant
async def get_current_tenant(
    x_auth_password: Optional[str] = Header(None, alias="X-Auth-Password")
) -> str:
    """
    FastAPI dependency для аутентификации tenant
    
    Args:
        x_auth_password: Пароль из заголовка X-Auth-Password
        
    Returns:
        tenant_id: ID аутентифицированного tenant
        
    Raises:
        HTTPException: Если аутентификация не удалась
    """
    if not x_auth_password:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-Auth-Password header."
        )
    
    return AuthenticationService.authenticate_tenant(x_auth_password)


# Глобальные экземпляры
auth_service = AuthenticationService()