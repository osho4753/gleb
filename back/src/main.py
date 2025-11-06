from fastapi import FastAPI, HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from .db import db
from .models import Rate, Transaction, TransactionUpdate, CashDeposit
from datetime import datetime
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP


app = FastAPI(title="Local Exchange Dashboard")
FIAT_ASSETS = ["CZK", "USD", "EUR"]

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

@app.get("/")
def root():
    """Корневой эндпоинт для проверки работы API"""
    return {"message": "Exchange API is running", "status": "ok"}

@app.get("/health")
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Проверяем соединение с базой данных
        db.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@app.post("/cash/init")
def init_cash():
    """Инициализирует кассу с нулевыми балансами для всех валют"""
    # список валют, с которыми работает система
    currencies = ["USD", "USDT", "EUR", "CZK", "BTC", "ETH", "CRON"]

    initialized = []
    for asset in currencies:
        existing = db.cash.find_one({"asset": asset})
        if existing:
            db.cash.update_one(
                {"asset": asset},
                {"$set": {"balance": 0.0, "updated_at": datetime.utcnow()}}
            )
        else:
            db.cash.insert_one({
                "asset": asset,
                "balance": 0.0,
                "updated_at": datetime.utcnow()
            })
        initialized.append(asset)

    return {
        "message": "Cash register initialized with zero balances",
        "assets": initialized
    }

# ---------- RATES ----------
class CashSetRequest(BaseModel):
    asset: str
    amount: float

@app.post("/cash/set")
def set_cash(request: CashSetRequest):
    """Устанавливает или обновляет баланс конкретной валюты"""
    asset = request.asset
    amount = request.amount
    existing = db.cash.find_one({"asset": asset})
    if existing:
        db.cash.update_one(
            {"asset": asset},
            {"$set": {"balance": amount, "updated_at": datetime.utcnow()}}
        )
    else:
        db.cash.insert_one({
            "asset": asset,
            "balance": amount,
            "updated_at": datetime.utcnow()
        })
    return {"message": f"Balance for {asset} set to {amount}"}

@app.put("/cash/{asset}")
def update_cash_balance(asset: str, amount: float):
    """Обновляет баланс существующей валюты"""
    existing = db.cash.find_one({"asset": asset})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found in cash")
    
    db.cash.update_one(
        {"asset": asset},
        {"$set": {"balance": amount, "updated_at": datetime.utcnow()}}
    )
    return {"message": f"Balance for {asset} updated to {amount}"}

@app.delete("/cash/{asset}")
def delete_cash_asset(asset: str):
    """Удаляет валюту из кассы"""
    existing = db.cash.find_one({"asset": asset})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found in cash")
    
    result = db.cash.delete_one({"asset": asset})
    if result.deleted_count > 0:
        return {"message": f"Asset {asset} removed from cash"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to remove {asset} from cash")

@app.post("/cash/deposit")
def deposit_to_cash(deposit: CashDeposit):
    """Пополнение кассы с сохранением как транзакции"""
    
    # Проверяем/создаем актив в кассе
    existing = db.cash.find_one({"asset": deposit.asset})
    if not existing:
        # Создаем новый актив с нулевым балансом
        db.cash.insert_one({
            "asset": deposit.asset,
            "balance": 0.0,
            "updated_at": datetime.utcnow()
        })
        old_balance = 0.0
    else:
        old_balance = existing["balance"]
    
    new_balance = old_balance + deposit.amount
    
    # Обновляем баланс в кассе
    db.cash.update_one(
        {"asset": deposit.asset},
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
        "is_modified": False
    }
    
    # Сохраняем в коллекцию транзакций
    transaction_result = db.transactions.insert_one(deposit_transaction)
    
    return {
        "message": f"Deposited {deposit.amount} {deposit.asset} to cash",
        "asset": deposit.asset,
        "amount": deposit.amount,
        "old_balance": old_balance,
        "new_balance": new_balance,
        "note": deposit.note,
        "transaction_id": str(transaction_result.inserted_id)
    }



# ---------- TRANSACTIONS ----------

@app.post("/transactions")
def create_transaction(tx: Transaction):
    """
    Создание транзакции:
    - активы (crypto): USDT, BTC, ETH и т.д.
    - товар (fiat): USD, EUR, CZK
    - при crypto_to_fiat — комиссия ДОПЛАЧИВАЕТСЯ
    - при fiat_to_crypto — комиссия УДЕРЖИВАЕТСЯ
    - прибыль считается при замыкании цикла (продажа кэша)
    """

    # Определяем категории активов

    SPECIAL_FIAT = ["CZK"]

    # --- Проверки ---
    if tx.type not in ["fiat_to_crypto", "crypto_to_fiat"]:
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    if tx.type == "fiat_to_crypto" and tx.from_asset in SPECIAL_FIAT:
        # Клиент платит кронами → делим
        tx.amount_to_clean = tx.amount_from / tx.rate_used
    elif tx.type == "crypto_to_fiat" and tx.to_asset in SPECIAL_FIAT:
        # Клиент получает кроны → умножаем
        tx.amount_to_clean = tx.amount_from * tx.rate_used
    elif tx.type == "crypto_to_fiat" and tx.to_asset == "EUR":
        # Все остальные случаи → стандартно умножаем
        tx.amount_to_clean = tx.amount_from / tx.rate_used
    else:
        tx.amount_to_clean = tx.amount_from * tx.rate_used

    # --- Расчёт комиссии ---
    if tx.type == "crypto_to_fiat":
        # Клиент получает фиат → мы доплачиваем комиссию
        tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
        tx.amount_to_final = round(tx.amount_to_clean + tx.fee_amount)  # округляем до целого
        tx.profit = round(-tx.fee_amount) 
        fee_direction = "added"

    elif tx.type == "fiat_to_crypto":
        # Клиент платит фиат → мы удерживаем комиссию
        tx.amount_to_final = round(tx.amount_to_clean / (1 + (tx.fee_percent / 100)))  # округляем до целого
        tx.fee_amount = tx.amount_to_clean - tx.amount_to_final
        tx.profit = round(tx.fee_amount)  
        fee_direction = "deducted"

    from_cash = db.cash.find_one({"asset": tx.from_asset})
    to_cash = db.cash.find_one({"asset": tx.to_asset})

    if not from_cash:
        db.cash.insert_one({"asset": tx.from_asset, "balance": 0.0, "updated_at": datetime.utcnow()})
        from_cash = {"asset": tx.from_asset, "balance": 0.0}

    if not to_cash:
        db.cash.insert_one({"asset": tx.to_asset, "balance": 0.0, "updated_at": datetime.utcnow()})
        to_cash = {"asset": tx.to_asset, "balance": 0.0}


    if tx.type == "crypto_to_fiat":
        tx.profit_currency = tx.to_asset  # клиент получает фиат → прибыль в нём
    elif tx.type == "fiat_to_crypto":
        tx.profit_currency = tx.from_asset  # клиент платит фиат → прибыль в нём
    
    if tx.type == "fiat_to_crypto":
        # клиент отдаёт фиат, получает крипту
        # проверяем, достаточно ли крипты (to_asset), чтобы выдать клиенту
        if to_cash["balance"] < tx.amount_to_final:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.to_asset} in cash")
        
        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})

    elif tx.type == "crypto_to_fiat":
        # клиент отдаёт крипту, получает фиат
        if to_cash["balance"] < tx.amount_to_final:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.to_asset} in cash")
        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})
    # --- Подсчёт реализованной прибыли ---
    realized_profit = 0.0

    if tx.type == "crypto_to_fiat" and tx.from_asset == "USDT" and tx.to_asset in FIAT_ASSETS:
        amount_sold_usdt = Decimal(str(tx.amount_from))
        sell_rate = Decimal(str(tx.rate_used))
        sell_fee = Decimal(str(tx.fee_percent))

        # Получаем все покупки кэша (fiat_to_crypto)
        buys = list(db.transactions.find({
            "type": "fiat_to_crypto",
            "to_asset": "USDT"
        }).sort("created_at", 1))

        remaining_to_sell = amount_sold_usdt
        profit = Decimal("0.0")

        for b in buys:
            if remaining_to_sell <= 0:
                break

            buy_remaining = Decimal(str(b.get("remaining", b["amount_to_final"])))
            if buy_remaining <= 0:
                continue

            used_amount = min(buy_remaining, remaining_to_sell)
            buy_rate = Decimal(str(b["rate_used"]))
            buy_fee = Decimal(str(b["fee_percent"]))

            # --- считаем эффективные курсы с учётом комиссий ---
            buy_rate_with_fee = buy_rate * (1 + buy_fee / 100)
            sell_rate_with_fee = sell_rate * (1 + sell_fee / 100)

            # Твоя логика: товар — это крона → прибыль = разница в курсах
            profit += (buy_rate_with_fee - sell_rate_with_fee) * used_amount

            # обновляем остаток
            b["remaining"] = (buy_remaining - used_amount)
            remaining_to_sell -= used_amount

        realized_profit = profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    tx.profit = float(realized_profit)

    tx_data = tx.dict()
    tx_data["created_at"] = datetime.utcnow()
    tx_data["is_modified"] = False
    tx_data["realized_profit"] = float(realized_profit)

    db.transactions.insert_one(tx_data)

    return {
        "type": tx.type,
        "rate_used": tx.rate_used,
        "from_asset": tx.from_asset,
        "to_asset": tx.to_asset,
        "amount_from": tx.amount_from,
        "amount_to_clean": tx.amount_to_clean,
        "fee_percent": tx.fee_percent,
        "fee_amount": tx.fee_amount,
        "amount_to_final": tx.amount_to_final,
        "profit": realized_profit,
        "fee_direction": fee_direction,
        "message": "Transaction processed successfully"
    }

@app.get("/cash/profit")
def get_total_profit():
    """
    Возвращает суммарную реализованную прибыль, сгруппированную по валюте прибыли.
    """
    pipeline = [
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
        "message": "Realized profit grouped by profit currency"
    }

@app.get("/transactions")
def get_transactions():
    txs = list(db.transactions.find())
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs

@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    """Получить конкретную транзакцию по ID"""
    try:
        tx = db.transactions.find_one({"_id": ObjectId(transaction_id)})
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        tx["_id"] = str(tx["_id"])
        return tx
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid transaction ID: {str(e)}")

@app.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: str, update_data: TransactionUpdate):
    """Обновить существующую транзакцию"""
    try:
        print(f"Updating transaction with ID: {transaction_id}")  # Добавляем логирование
        print(f"Update data: {update_data.dict()}")  # Логируем данные для обновления
        
        # Проверяем существование транзакции
        existing_tx = db.transactions.find_one({"_id": ObjectId(transaction_id)})
        if not existing_tx:
            print(f"Transaction not found: {transaction_id}")  # Логируем если не найдена
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Подготавливаем данные для обновления
        update_fields = {}
        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                update_fields[field] = value
        
        # Добавляем метки изменения
        update_fields["is_modified"] = True
        update_fields["modified_at"] = datetime.utcnow()
        
        # Если изменились критичные поля, пересчитываем транзакцию
        critical_fields = ["amount_from", "rate_used", "fee_percent", "type"]
        if any(field in update_fields for field in critical_fields):
            # Создаем временный объект транзакции для пересчета
            temp_tx = Transaction(**{**existing_tx, **update_fields})
            
            # Пересчитываем (копируем логику из create_transaction)
            SPECIAL_FIAT = ["CZK"]
            
            if temp_tx.type == "fiat_to_crypto" and temp_tx.from_asset in SPECIAL_FIAT:
                temp_tx.amount_to_clean = temp_tx.amount_from / temp_tx.rate_used
            elif temp_tx.type == "crypto_to_fiat" and temp_tx.to_asset in SPECIAL_FIAT:
                temp_tx.amount_to_clean = temp_tx.amount_from * temp_tx.rate_used
            elif temp_tx.type == "crypto_to_fiat" and temp_tx.to_asset == "EUR":
                temp_tx.amount_to_clean = temp_tx.amount_from / temp_tx.rate_used
            else:
                temp_tx.amount_to_clean = temp_tx.amount_from * temp_tx.rate_used
            
            if temp_tx.type == "crypto_to_fiat":
                temp_tx.fee_amount = temp_tx.amount_to_clean * (temp_tx.fee_percent / 100)
                temp_tx.amount_to_final = round(temp_tx.amount_to_clean + temp_tx.fee_amount)
                temp_tx.profit = round(-temp_tx.fee_amount)
            elif temp_tx.type == "fiat_to_crypto":
                temp_tx.amount_to_final = round(temp_tx.amount_to_clean / (1 + (temp_tx.fee_percent / 100)))
                temp_tx.fee_amount = temp_tx.amount_to_clean - temp_tx.amount_to_final
                temp_tx.profit = round(temp_tx.fee_amount)
            else:
                temp_tx.fee_amount = 0
                temp_tx.amount_to_final = round(temp_tx.amount_to_clean)
                temp_tx.profit = 0
            
            # Добавляем пересчитанные поля в обновление
            update_fields.update({
                "amount_to_clean": temp_tx.amount_to_clean,
                "fee_amount": temp_tx.fee_amount,
                "amount_to_final": temp_tx.amount_to_final,
                "profit": temp_tx.profit
            })
        
        # Обновляем транзакцию
        result = db.transactions.update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0:
            updated_tx = db.transactions.find_one({"_id": ObjectId(transaction_id)})
            updated_tx["_id"] = str(updated_tx["_id"])
            return {"message": "Transaction updated successfully", "transaction": updated_tx}
        else:
            return {"message": "No changes made to transaction"}
            
    except Exception as e:
        print(f"Error updating transaction: {str(e)}")  # Логируем ошибку
        if "ObjectId" in str(e):
            raise HTTPException(status_code=400, detail=f"Invalid transaction ID format: {transaction_id}")
        raise HTTPException(status_code=400, detail=f"Error updating transaction: {str(e)}")

@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str):
    """Удалить конкретную транзакцию"""
    try:
        print(f"Deleting transaction with ID: {transaction_id}")  # Добавляем логирование
        
        existing_tx = db.transactions.find_one({"_id": ObjectId(transaction_id)})
        if not existing_tx:
            print(f"Transaction not found: {transaction_id}")  # Логируем если не найдена
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        result = db.transactions.delete_one({"_id": ObjectId(transaction_id)})
        if result.deleted_count > 0:
            return {"message": "Transaction deleted successfully", "deleted_id": transaction_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete transaction")
            
    except Exception as e:
        print(f"Error deleting transaction: {str(e)}")  # Логируем ошибку
        if "ObjectId" in str(e):
            raise HTTPException(status_code=400, detail=f"Invalid transaction ID format: {transaction_id}")
        raise HTTPException(status_code=400, detail=f"Error deleting transaction: {str(e)}")


@app.get("/cash/status")
def get_cash_status():
    """Показать все активы и их балансы"""
    try:
        items = list(db.cash.find({}, {"_id": 0}))
        total_assets = {item["asset"]: item["balance"] for item in items}
        return {"cash": total_assets}
    except Exception as e:
        print(f"Database error in get_cash_status: {e}")
        # Возвращаем пустые данные при ошибке подключения к БД
        return {"cash": {}, "error": "Database connection failed", "details": str(e)}

@app.delete("/reset-all")
def reset_cash_delete():
    """Полностью очищает кассу — все валюты и балансы (DELETE метод)"""
    result = db.cash.delete_many({})
    return {
        "message": "Cash register has been reset",
        "deleted_count": result.deleted_count
    }

@app.delete("/reset-all-transactions")
def reset_transactions():
    """Полностью очищает коллекцию транзакций"""
    result = db.transactions.delete_many({})
    return {
        "message": "All transactions have been deleted",
        "deleted_count": result.deleted_count
    }
@app.get("/cash/cashflow_profit")
def get_cashflow_profit():
    """
    Считает чистую прибыль/убыток по каждой валюте через поток кассы:
    - profit = все, что получили в этой валюте - все, что отдали из кассы в этой валюте
    """
    txs = list(db.transactions.find())
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
        "message": "Net profit calculated from actual cash flow for each currency"
    }
