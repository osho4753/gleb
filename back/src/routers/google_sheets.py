"""
Роутер для управления Google Sheets интеграцией
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from ..db import db
from ..models import GoogleSheetsSettings, EnableGoogleSheets, GoogleSheetsStatus
from ..auth import get_current_tenant
from ..google_sheets import sheets_manager
import re

router = APIRouter(prefix="/google-sheets", tags=["google-sheets"])


def extract_spreadsheet_id(url: str) -> str:
    """Извлекает ID таблицы из URL Google Sheets"""
    pattern = r"/spreadsheets/d/([a-zA-Z0-9-_]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Google Sheets URL format")


@router.get("/status")
def get_sheets_status(tenant_id: str = Depends(get_current_tenant)):
    """Получить текущий статус Google Sheets интеграции"""
    settings = db.google_sheets_settings.find_one({"tenant_id": tenant_id})
    
    if not settings:
        return GoogleSheetsStatus(
            is_enabled=False,
            connection_status="not_configured"
        )
    
    # Проверяем соединение с таблицей если включено
    connection_status = "not_configured"
    if settings["is_enabled"] and settings.get("spreadsheet_id"):
        try:
            # Пробуем получить доступ к таблице
            sheets_manager.test_spreadsheet_access(settings["spreadsheet_id"])
            connection_status = "connected"
        except Exception as e:
            connection_status = "error"
            print(f"Google Sheets connection test failed: {e}")
    
    return GoogleSheetsStatus(
        is_enabled=settings["is_enabled"],
        spreadsheet_id=settings.get("spreadsheet_id"),
        spreadsheet_url=settings.get("spreadsheet_url"),
        connection_status=connection_status,
        last_updated=settings.get("updated_at")
    )


@router.post("/enable")
def enable_google_sheets(
    request: EnableGoogleSheets, 
    tenant_id: str = Depends(get_current_tenant)
):
    """Включить Google Sheets интеграцию для tenant"""
    try:
        # Извлекаем ID таблицы из URL
        spreadsheet_id = extract_spreadsheet_id(request.spreadsheet_url)
        
        # Проверяем доступ к таблице
        sheets_manager.test_spreadsheet_access(spreadsheet_id)
        
        # Инициализируем таблицу с нужными листами
        sheets_manager.setup_tenant_spreadsheet(spreadsheet_id, tenant_id)
        
        # Сохраняем настройки
        settings = {
            "tenant_id": tenant_id,
            "is_enabled": True,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": request.spreadsheet_url,
            "updated_at": datetime.utcnow()
        }
        
        db.google_sheets_settings.update_one(
            {"tenant_id": tenant_id},
            {"$set": settings},
            upsert=True
        )
        
        # Автоматически синхронизируем существующие данные
        try:
            # Получаем все транзакции для данного tenant
            transactions = list(db.transactions.find({"tenant_id": tenant_id}))
            
            # Получаем данные кассы
            cash_items = list(db.cash.find({"tenant_id": tenant_id}, {"_id": 0}))
            cash_status = {item["asset"]: item["balance"] for item in cash_items}
            
            # Получаем данные прибыли
            pipeline = [
                {"$match": {"tenant_id": tenant_id}},
                {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
            ]
            profit_results = list(db.transactions.aggregate(pipeline))
            realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
            
            # Синхронизируем все существующие данные
            if transactions or cash_status or realized_profits:
                sheets_manager.sync_all_data(spreadsheet_id, transactions, cash_status, realized_profits, tenant_id)
                sync_message = f" Синхронизировано: {len(transactions)} транзакций, {len(cash_status)} валют в кассе, {len(realized_profits)} валют прибыли."
            else:
                sync_message = " Новая таблица готова к использованию."
                
        except Exception as sync_error:
            print(f"Warning: Failed to sync existing data: {sync_error}")
            sync_message = " Таблица подключена, но синхронизация существующих данных не удалась. Используйте кнопку 'Синхронизировать все данные' для повторной попытки."
        
        return {
            "message": f"Google Sheets integration enabled successfully.{sync_message}",
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": request.spreadsheet_url,
            "tenant_id": tenant_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL format: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to access Google Sheets. Please ensure the spreadsheet exists and our service account has access: {str(e)}"
        )


@router.post("/disable")
def disable_google_sheets(tenant_id: str = Depends(get_current_tenant)):
    """Временно отключить Google Sheets интеграцию (настройки сохраняются)"""
    result = db.google_sheets_settings.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"is_enabled": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Google Sheets settings not found")
    
    return {
        "message": "Google Sheets integration temporarily disabled. Settings preserved.",
        "tenant_id": tenant_id
    }


@router.post("/re-enable")
def re_enable_google_sheets(tenant_id: str = Depends(get_current_tenant)):
    """Повторно включить ранее настроенную Google Sheets интеграцию"""
    # Проверяем что настройки существуют
    settings = db.google_sheets_settings.find_one({"tenant_id": tenant_id})
    if not settings:
        raise HTTPException(status_code=404, detail="No Google Sheets configuration found. Please use /enable endpoint to set up new integration.")
    
    if not settings.get("spreadsheet_id"):
        raise HTTPException(status_code=400, detail="Invalid configuration: missing spreadsheet_id")
    
    try:
        # Проверяем доступ к таблице
        sheets_manager.test_spreadsheet_access(settings["spreadsheet_id"])
        
        # Включаем интеграцию
        db.google_sheets_settings.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"is_enabled": True, "updated_at": datetime.utcnow()}}
        )
        
        # Автоматически синхронизируем все данные
        try:
            # Получаем все транзакции для данного tenant
            transactions = list(db.transactions.find({"tenant_id": tenant_id}))
            
            # Получаем данные кассы
            cash_items = list(db.cash.find({"tenant_id": tenant_id}, {"_id": 0}))
            cash_status = {item["asset"]: item["balance"] for item in cash_items}
            
            # Получаем данные прибыли
            pipeline = [
                {"$match": {"tenant_id": tenant_id}},
                {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
            ]
            profit_results = list(db.transactions.aggregate(pipeline))
            realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
            
            # Синхронизируем все существующие данные
            sheets_manager.sync_all_data(settings["spreadsheet_id"], transactions, cash_status, realized_profits, tenant_id)
            sync_message = f" Автоматически синхронизировано: {len(transactions)} транзакций, {len(cash_status)} валют в кассе, {len(realized_profits)} валют прибыли."
                
        except Exception as sync_error:
            print(f"Warning: Failed to sync existing data on re-enable: {sync_error}")
            sync_message = " Интеграция включена, но автоматическая синхронизация не удалась. Используйте кнопку 'Синхронизировать все данные'."
        
        return {
            "message": f"Google Sheets integration re-enabled successfully.{sync_message}",
            "spreadsheet_id": settings["spreadsheet_id"],
            "spreadsheet_url": settings.get("spreadsheet_url"),
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to access previously configured Google Sheets: {str(e)}"
        )


@router.delete("/disconnect")
def disconnect_google_sheets(tenant_id: str = Depends(get_current_tenant)):
    """Полностью отключить и удалить настройки Google Sheets"""
    result = db.google_sheets_settings.delete_one({"tenant_id": tenant_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Google Sheets settings not found")
    
    return {
        "message": "Google Sheets integration completely removed",
        "tenant_id": tenant_id
    }


@router.post("/sync-all")
def sync_all_data(tenant_id: str = Depends(get_current_tenant)):
    """Синхронизировать все существующие данные с Google Sheets"""
    # Проверяем что интеграция включена
    settings = db.google_sheets_settings.find_one({"tenant_id": tenant_id})
    if not settings or not settings.get("is_enabled"):
        raise HTTPException(status_code=400, detail="Google Sheets integration is not enabled")
    
    try:
        # Получаем все транзакции для данного tenant
        transactions = list(db.transactions.find({"tenant_id": tenant_id}))
        
        # Получаем данные кассы
        cash_items = list(db.cash.find({"tenant_id": tenant_id}, {"_id": 0}))
        cash_status = {item["asset"]: item["balance"] for item in cash_items}
        
        # Получаем данные прибыли
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
        ]
        profit_results = list(db.transactions.aggregate(pipeline))
        realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
        
        # Очищаем таблицу и заполняем заново
        sheets_manager.sync_all_data(settings["spreadsheet_id"], transactions, cash_status, realized_profits, tenant_id)
        
        return {
            "message": "All data synchronized successfully",
            "synced_transactions": len(transactions),
            "synced_cash_assets": len(cash_status),
            "synced_profit_currencies": len(realized_profits),
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        print(f"Failed to sync all data for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to synchronize data: {str(e)}"
        )


@router.get("/instructions")
def get_setup_instructions():
    """Получить инструкции по подключению Google Sheets"""
    return {
        "title": "Как подключить Google Таблицу",
        "steps": [
            {
                "step": 1,
                "title": "Создайте новую Google Таблицу",
                "description": "Перейдите на drive.google.com и создайте новую Google Таблицу"
            },
            {
                "step": 2, 
                "title": "Откройте доступ нашему сервису",
                "description": "Нажмите 'Настроить доступ' → 'Добавить пользователей' → введите email: mysheet@helical-realm-477920-u8.iam.gserviceaccount.com"
            },
            {
                "step": 3,
                "title": "Дайте права редактора", 
                "description": "Убедитесь что выбрана роль 'Редактор' для нашего сервисного аккаунта"
            },
            {
                "step": 4,
                "title": "Скопируйте ссылку на таблицу",
                "description": "Скопируйте полную ссылку на вашу таблицу и вставьте её в поле ниже"
            }
        ],
        "service_email": "mysheet@helical-realm-477920-u8.iam.gserviceaccount.com",
        "note": "После подключения таблицы, все ваши транзакции будут автоматически синхронизироваться с Google Таблицей"
    }