from fastapi import FastAPI, HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from .db import db
from .models import Rate, Transaction
from datetime import datetime

app = FastAPI(title="Local Exchange Dashboard")

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)
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
@app.post("/cash/set")
def set_cash(asset: str, amount: float):
    """Устанавливает или обновляет баланс конкретной валюты"""
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

# ---------- TRANSACTIONS ----------

@app.post("/transactions")
def create_transaction(tx: Transaction):
    """
    Создание транзакции:
    - курс вводится вручную (rate_used)
    - комиссия рассчитывается в зависимости от типа
    - при CZK логика курса перевёрнута (делим при fiat_to_crypto)
    - касса обновляется автоматически
    """

    SPECIAL_FIAT = ["CZK"]  # список валют, где курс считается "в обратную сторону"

    # --- Расчёт суммы с учётом типа и валюты ---
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

    # --- Расчёт комиссии и прибыли ---
    if tx.type == "crypto_to_fiat":
        # Клиент получает фиат → мы доплачиваем комиссию
        tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
        tx.amount_to_final = round(tx.amount_to_clean + tx.fee_amount)  # округляем до целого
        tx.profit = round(-tx.fee_amount)  # убыток, округляем до целого
        fee_direction = "added"

    elif tx.type == "fiat_to_crypto":
        # Клиент платит фиат → мы удерживаем комиссию
        tx.amount_to_final = round(tx.amount_to_clean / (1 + (tx.fee_percent / 100)))  # округляем до целого
        tx.fee_amount = tx.amount_to_clean - tx.amount_to_final
        tx.profit = round(tx.fee_amount)  # прибыль, округляем до целого
        fee_direction = "deducted"

    else:
        tx.fee_amount = 0
        tx.amount_to_final = round(tx.amount_to_clean)  # округляем до целого
        tx.profit = 0
        fee_direction = "none"

    # --- Проверка и обновление кассы ---
    from_cash = db.cash.find_one({"asset": tx.from_asset})
    to_cash = db.cash.find_one({"asset": tx.to_asset})

    if not from_cash:
        db.cash.insert_one({"asset": tx.from_asset, "balance": 0.0, "updated_at": datetime.utcnow()})
        from_cash = {"asset": tx.from_asset, "balance": 0.0}

    if not to_cash:
        db.cash.insert_one({"asset": tx.to_asset, "balance": 0.0, "updated_at": datetime.utcnow()})
        to_cash = {"asset": tx.to_asset, "balance": 0.0}

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
 
    # --- Сохранение транзакции ---
    db.transactions.insert_one(tx.dict())

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
        "profit": tx.profit,
        "fee_direction": fee_direction,
        "message": "Transaction processed successfully"
    }

@app.get("/transactions")
def get_transactions():
    txs = list(db.transactions.find())
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs


@app.get("/cash/status")
def get_cash_status():
    """Показать все активы и их балансы"""
    items = list(db.cash.find({}, {"_id": 0}))
    total_assets = {item["asset"]: item["balance"] for item in items}
    return {"cash": total_assets}


@app.get("/cash/profit")
def get_total_profit():
    """Возвращает прибыль/убыток по каждой валюте отдельно"""
    pipeline = [
        {"$group": {"_id": "$to_asset", "total_profit": {"$sum": "$profit"}}}
    ]
    results = list(db.transactions.aggregate(pipeline))

    profits_by_currency = {}
    for item in results:
        profits_by_currency[item["_id"]] = round(item["total_profit"], 2)

    return {
        "profits_by_currency": profits_by_currency,
        "message": "Profit grouped by currency"
    }

@app.delete("/cash/reset")
def reset_cash():
    """Полностью очищает кассу — все валюты и балансы"""
    result = db.cash.delete_many({})
    return {
        "message": "Cash register has been reset",
        "deleted_count": result.deleted_count
    }
@app.delete("/transactions/reset")
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
