"""
Роутер для операций с кассой
"""
import os
from fastapi import APIRouter, HTTPException, Depends,BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from ..telegram_manager import telegram_manager
from ..db import db
from ..models import CashDeposit, CashWithdrawal
from ..constants import CURRENCIES
from ..google_sheets import sheets_manager
from ..history_manager import history_manager
from ..auth import get_current_tenant
from ..utils.cash_desk_utils import verify_cash_desk_access_util

router = APIRouter(prefix="/cash", tags=["cash"])


# Модели
class CashSetRequest(BaseModel):
    asset: str
    amount: float


@router.post("/init")
def init_cash(
    cash_desk_id: str,
    tenant_id: str = Depends(get_current_tenant)
):
    """Инициализирует кассу с нулевыми балансами для всех валют для конкретной кассы"""
    # Проверяем доступ к кассе
    cash_desk = verify_cash_desk_access_util(cash_desk_id, tenant_id)
    initialized = []
    for asset in CURRENCIES:
        existing = db.cash.find_one({"asset": asset, "tenant_id": tenant_id, "cash_desk_id": cash_desk_id})
        if existing:
            db.cash.update_one(
                {"asset": asset, "tenant_id": tenant_id, "cash_desk_id": cash_desk_id},
                {"$set": {"balance": 0.0, "updated_at": datetime.utcnow()}}
            )
        else:
            db.cash.insert_one({
                "asset": asset,
                "balance": 0.0,
                "tenant_id": tenant_id,
                "cash_desk_id": cash_desk_id,
                "updated_at": datetime.utcnow()
            })
        initialized.append(asset)

    return {
        "message": f"Cash register initialized with zero balances for tenant {tenant_id}",
        "assets": initialized,
        "tenant_id": tenant_id
    }


@router.post("/set")
def set_cash(
    request: CashSetRequest, 
    cash_desk_id: str,
    tenant_id: str = Depends(get_current_tenant)
):
    """Устанавливает или обновляет баланс конкретной валюты для конкретной кассы"""
    # Проверяем доступ к кассе
    cash_desk = verify_cash_desk_access_util(cash_desk_id, tenant_id)
    
    asset = request.asset
    amount = request.amount
    existing = db.cash.find_one({"asset": asset, "cash_desk_id": cash_desk_id})
    if existing:
        db.cash.update_one(
            {"asset": asset, "cash_desk_id": cash_desk_id},
            {"$set": {"balance": amount, "updated_at": datetime.utcnow()}}
        )
    else:
        db.cash.insert_one({
            "asset": asset,
            "balance": amount,
            "tenant_id": tenant_id,
            "cash_desk_id": cash_desk_id,
            "updated_at": datetime.utcnow()
        })
    return {
        "message": f"Balance for {asset} set to {amount} for cash desk {cash_desk.name}",
        "cash_desk_id": cash_desk_id
    }


@router.put("/{asset}")
def update_cash_balance(asset: str, amount: float,cash_desk_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Обновляет баланс существующей валюты для конкретного tenant"""
    existing = db.cash.find_one({"asset": asset, "tenant_id": tenant_id, "cash_desk_id": cash_desk_id})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found in cash for cash desk {cash_desk_id}")
     
    db.cash.update_one(
        {"asset": asset, "cash_desk_id": cash_desk_id},
        {"$set": {"balance": amount, "updated_at": datetime.utcnow()}}
    )
    return {
        "message": f"Balance for {asset} updated to {amount} for tenant {tenant_id}",
        "tenant_id": tenant_id
    }


@router.delete("/{asset}")
def delete_cash_asset(asset: str,cash_desk_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Удаляет валюту из кассы для конкретного tenant"""
    existing = db.cash.find_one({"asset": asset, "tenant_id": tenant_id, "cash_desk_id": cash_desk_id})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found in cash for tenant {tenant_id}")
    
    result = db.cash.delete_one({"asset": asset, "tenant_id": tenant_id, "cash_desk_id": cash_desk_id})
    if result.deleted_count > 0:
        return {
            "message": f"Asset {asset} removed from cash for tenant {tenant_id}",
            "tenant_id": tenant_id
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to remove {asset} from cash for tenant {tenant_id}")


@router.post("/deposit")
def deposit_to_cash(
    deposit: CashDeposit, 
    cash_desk_id: str,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant)
):
    """Пополнение кассы с сохранением как транзакции для конкретной кассы"""
    
    # Проверяем доступ к кассе
    cash_desk = verify_cash_desk_access_util(cash_desk_id, tenant_id)
    
    # Проверяем/создаем актив в кассе
    existing = db.cash.find_one({"asset": deposit.asset, "cash_desk_id": cash_desk_id})
    if not existing:
        # Создаем новый актив с нулевым балансом
        db.cash.insert_one({
            "asset": deposit.asset,
            "balance": 0.0,
            "tenant_id": tenant_id,
            "cash_desk_id": cash_desk_id,
            "updated_at": datetime.utcnow()
        })
        old_balance = 0.0
    else:
        old_balance = existing["balance"]
    
    new_balance = old_balance + deposit.amount
    
    # Обновляем баланс в кассе
    # Сохраняем снимок состояния ПЕРЕД пополнением
    history_manager.save_snapshot(
        operation_type="deposit",
        description=f"Deposit {deposit.amount} {deposit.asset}",
        tenant_id=tenant_id,
        cash_desk_id=cash_desk_id
    )
    
    db.cash.update_one(
        {"asset": deposit.asset, "cash_desk_id": cash_desk_id},
        {"$set": {"balance": new_balance, "updated_at": datetime.utcnow()}}
    )
    
    # Создаем транзакцию пополнения для истории транзакций
    deposit_transaction = {
        "type": "deposit",  # новый тип транзакции
        "from_asset": deposit.asset,
        "to_asset": "",  # пустое значение для пополнения
        "amount_from": deposit.amount,  # сумма пополнения
        "amount_to_clean": 0,  # не применимо
        "amount_to_final": 0,  # не применимо  
        "rate_used": 0,  # не применимо для пополнения
        "fee_percent": 0,  # нет комиссии
        "fee_amount": 0,  # нет комиссии
        "profit": 0,  # нет прибыли
        "note": deposit.note or "",
        "created_at": deposit.created_at,
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "is_modified": False
    }
    
    # Сохраняем в коллекцию транзакций
    transaction_result = db.transactions.insert_one(deposit_transaction)
    # Add _id so Sheets helper can reference it
    deposit_transaction["_id"] = transaction_result.inserted_id

    # Try to write to Google Sheets (don't fail the request if Sheets is down)
    try:
        chat_id=os.getenv("TELEGRAM_CHAT_ID")
        # Получаем имя кассы
        if chat_id:
            # 2. Получаем новый баланс
            balances = {}
            new_cash_item = db.cash.find_one({"asset": deposit.asset, "cash_desk_id": cash_desk_id})
            if new_cash_item:
                balances[deposit.asset] = new_cash_item.get("balance", 0)

            # 3. Форматируем сообщение
            message = telegram_manager.format_transaction_message(
                cash_desk.name, 
                deposit_transaction,
                balances
            )
            
            # 4. Добавляем в очередь
            background_tasks.add_task(
                telegram_manager.send_message_async,
                chat_id,
                message
            )
        cash_desk_name = "Unknown" # Дефолтное значение
        if cash_desk_id:
            # Сначала попробуем найти по _id
            cash_desk = db.cash_desks.find_one({"_id": cash_desk_id, "tenant_id": tenant_id})
            if cash_desk:
                cash_desk_name = cash_desk["name"]
            else:
                # Пробуем также поиск по id
                cash_desk = db.cash_desks.find_one({"id": cash_desk_id, "tenant_id": tenant_id})
                if cash_desk:
                    cash_desk_name = cash_desk["name"]
                else:
                    print(f"⚠️ Cash desk {cash_desk_id} not found for tenant {tenant_id}")
        
        # Добавляем транзакцию в лист конкретной кассы
        sheets_manager.add_transaction(deposit_transaction, tenant_id=tenant_id, cash_desk_id=cash_desk_id)
        
        # Обновляем баланс для конкретной кассы и валюты
        sheets_manager.update_balance_for_desk(cash_desk_name, deposit.asset, new_balance, tenant_id)
    except Exception as e:
        print(f"Failed to add cash deposit to Google Sheets: {e}")

    return {
        "message": f"Deposited {deposit.amount} {deposit.asset} to cash for tenant {tenant_id}",
        "asset": deposit.asset,
        "amount": deposit.amount,
        "old_balance": old_balance,
        "new_balance": new_balance,
        "note": deposit.note,
        "tenant_id": tenant_id,
        "transaction_id": str(transaction_result.inserted_id)
    }


@router.post("/withdrawal")
def withdraw_from_cash(withdrawal: CashWithdrawal, cash_desk_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Вычет средств из кассы с сохранением как транзакции для конкретного tenant"""
    cash_desk = verify_cash_desk_access_util(cash_desk_id, tenant_id)
    # Проверяем существование актива в кассе
    existing = db.cash.find_one({"asset": withdrawal.asset, "cash_desk_id": cash_desk_id})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Asset {withdrawal.asset} not found in cash for tenant {tenant_id}")
    
    old_balance = existing["balance"]
    
    # Проверяем достаточность средств
    if old_balance < withdrawal.amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient balance for cash desk {cash_desk_id}. Available: {old_balance} {withdrawal.asset}"     
            )
    
    new_balance = old_balance - withdrawal.amount
    
    # Сохраняем снимок состояния ПЕРЕД выводом
    history_manager.save_snapshot(
        operation_type="withdrawal",
        description=f"Withdrawal {withdrawal.amount} {withdrawal.asset}",
        tenant_id=tenant_id,
        cash_desk_id=cash_desk_id
    )
    
    # Обновляем баланс в кассе
    db.cash.update_one(
        {"asset": withdrawal.asset, "cash_desk_id": cash_desk_id},
        {"$set": {"balance": new_balance, "updated_at": datetime.utcnow()}}
    )
    
    # Создаем транзакцию вычета для истории транзакций
    withdrawal_transaction = {
        "type": "withdrawal",  # новый тип транзакции
        "from_asset": withdrawal.asset,
        "to_asset": "",  # пустое значение для вычета
        "amount_from": -withdrawal.amount,  # отрицательная сумма для вычета
        "amount_to_clean": 0,  # не применимо
        "amount_to_final": 0,  # не применимо  
        "rate_used": 0,  # не применимо для вычета
        "fee_percent": 0,  # нет комиссии
        "fee_amount": 0,  # нет комиссии
        "profit": 0,  # нет прибыли
        "note": withdrawal.note or "",
        "created_at": withdrawal.created_at,
        "tenant_id": tenant_id,
        "cash_desk_id": cash_desk_id,
        "is_modified": False
    }
    
    # Сохраняем в коллекцию транзакций
    transaction_result = db.transactions.insert_one(withdrawal_transaction)
    # Add _id so Sheets helper can reference it
    withdrawal_transaction["_id"] = transaction_result.inserted_id

    # Try to write to Google Sheets (don't fail the request if Sheets is down)
    try:
        # Получаем имя кассы
        cash_desk_name = cash_desk.name
        sheets_manager.add_transaction(withdrawal_transaction, tenant_id=tenant_id, cash_desk_id=cash_desk_id)
        
        sheets_manager.update_balance_for_desk(cash_desk_name, withdrawal.asset, new_balance, tenant_id)
    except Exception as e:
        print(f"Failed to add cash withdrawal to Google Sheets: {e}")

    return {
        "message": f"Withdrawn {withdrawal.amount} {withdrawal.asset} from cash desk {cash_desk_id}",
        "asset": withdrawal.asset,
        "amount": withdrawal.amount,
        "old_balance": old_balance,
        "new_balance": new_balance,
        "note": withdrawal.note,
        "tenant_id": tenant_id,
        "transaction_id": str(transaction_result.inserted_id)
    }


@router.get("/status")
def get_cash_status(
    cash_desk_id: str = None,
    tenant_id: str = Depends(get_current_tenant)
):
    """Показать все активы и их балансы для конкретной кассы или агрегированно"""
    try:
        if cash_desk_id:
            # Проверяем доступ к кассе
            cash_desk = verify_cash_desk_access_util(cash_desk_id, tenant_id)
            # Получаем данные для конкретной кассы
            items = list(db.cash.find({"tenant_id": tenant_id, "cash_desk_id": cash_desk_id}, {"_id": 0}))
        else:
            # Агрегированные данные по всем кассам tenant'а
            pipeline = [
                {"$match": {"tenant_id": tenant_id}},
                {"$group": {"_id": "$asset", "balance": {"$sum": "$balance"}}}
            ]
            aggregated = list(db.cash.aggregate(pipeline))
            items = [{"asset": item["_id"], "balance": item["balance"]} for item in aggregated]
        
        total_assets = {item["asset"]: item["balance"] for item in items}
        return {
            "cash": total_assets,
            "cash_desk_id": cash_desk_id,
            "tenant_id": tenant_id
        }
    except Exception as e:
        print(f"Database error in get_cash_status: {e}")
        # Возвращаем пустые данные при ошибке подключения к БД
        return {"cash": {}, "error": "Database connection failed", "details": str(e)}


@router.get("/profit")
def get_total_profit(
    cash_desk_id: str = None,
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Возвращает суммарную реализованную прибыль, сгруппированную по валюте прибыли.
    """
    from ..constants import FIAT_ASSETS
    
    if cash_desk_id:
        # Проверяем доступ к кассе
        verify_cash_desk_access_util(cash_desk_id, tenant_id)
        match_filter = {"cash_desk_id": cash_desk_id}
    else:
        # Агрегированные данные по всем кассам tenant'а
        match_filter = {"tenant_id": tenant_id}
    
    pipeline = [
        {"$match": match_filter},
        {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
    ]
    results = list(db.transactions.aggregate(pipeline))

    profits = {
        r["_id"]: round(r["total_realized_profit"], 2)
        for r in results
        if r["_id"] in FIAT_ASSETS
    }

    return {
        "profits_by_currency": profits,
        "message": f"Realized profit for tenant {tenant_id} grouped by profit currency",
        "tenant_id": tenant_id
    }


@router.get("/cashflow_profit")
def get_cashflow_profit(
    cash_desk_id: str = None,
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Считает чистую прибыль/убыток по каждой валюте через поток кассы:
    - profit = все, что получили в этой валюте - все, что отдали из кассы в этой валюте
    """
    if cash_desk_id:
        # Проверяем доступ к кассе
        verify_cash_desk_access_util(cash_desk_id, tenant_id)
        txs = list(db.transactions.find({"cash_desk_id": cash_desk_id}))
    else:
        # Агрегированные данные по всем кассам tenant'а
        txs = list(db.transactions.find({"tenant_id": tenant_id}))
    cashflow_profit = {}

    for tx in txs:
        # Получаем и отдаем в каждой валюте
        # fiat_to_crypto: клиент отдаёт from_asset, получает to_asset
        # crypto_to_fiat: клиент отдаёт from_asset, получает to_asset

        # --- отработаем from_asset ---
        from_asset = tx["from_asset"]
        amount_from = tx["amount_from"]

        if from_asset not in cashflow_profit:
            cashflow_profit[from_asset] = 0.0
        cashflow_profit[from_asset] += amount_from  # получили в кассу

        # --- отработаем to_asset ---
        to_asset = tx["to_asset"]
        amount_to_final = tx["amount_to_final"]

        if to_asset not in cashflow_profit:
            cashflow_profit[to_asset] = 0.0

        # считаем как отдано из кассы → вычитаем
        cashflow_profit[to_asset] -= amount_to_final

    # Округляем для удобства
    cashflow_profit = {k: round(v, 2) for k, v in cashflow_profit.items()}

    return {
        "cashflow_profit_by_currency": cashflow_profit,
        "message": f"Net profit for tenant {tenant_id} calculated from actual cash flow for each currency",
        "tenant_id": tenant_id
    }