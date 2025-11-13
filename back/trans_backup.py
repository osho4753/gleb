
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import csv
from io import StringIO
from ..db import db
from ..models import Transaction, TransactionUpdate
from ..constants import FIAT_ASSETS, SPECIAL_FIAT
from ..google_sheets import sheets_manager
from ..history_manager import history_manager

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("")
def create_transaction(tx: Transaction):
    # Сохраняем снимок состояния ПЕРЕД созданием транзакции
    history_manager.save_snapshot(
        operation_type="create_transaction",
        description=f"Creating {tx.type}: {tx.from_asset} → {tx.to_asset}"
    )

    # --- Проверки ---
    if tx.type not in ["fiat_to_crypto", "crypto_to_fiat", "fiat_to_fiat"]:
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
    elif tx.type == "fiat_to_fiat":
        # Обмен фиата на фиат: amount_to_final = amount_from / rate_used
        tx.amount_to_clean = tx.amount_from / tx.rate_used
        tx.amount_to_final = round(tx.amount_to_clean)
    else:
        tx.amount_to_clean = tx.amount_from * tx.rate_used

    # --- Расчёт комиссии ---
    if tx.type == "crypto_to_fiat":
        tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
        tx.amount_to_final = round(tx.amount_to_clean + tx.fee_amount)  # округляем до целого   
        tx.profit = round(-tx.fee_amount)
        fee_direction = "added"
        if tx.to_asset == "CZK" or tx.to_asset == "USD":
            tx.rate_for_gleb_pnl =  tx.rate_used * (1 + (tx.fee_percent / 100))
        elif tx.to_asset == "EUR":
            tx.rate_for_gleb_pnl =  tx.rate_used / (1 + (tx.fee_percent / 100))

    elif tx.type == "fiat_to_crypto":
        # Клиент платит фиат → мы удерживаем комиссию
        tx.amount_to_final = round(tx.amount_to_clean / (1 + (tx.fee_percent / 100)))  # округляем до целого
        tx.fee_amount = tx.amount_to_clean - tx.amount_to_final
        tx.profit = round(tx.fee_amount)
        fee_direction = "deducted"
        if tx.from_asset == "CZK" or tx.from_asset == "USD":
            tx.rate_for_gleb_pnl =  tx.rate_used * (1 + (tx.fee_percent / 100))
        elif tx.from_asset == "EUR":
            tx.rate_for_gleb_pnl =  tx.rate_used / (1 + (tx.fee_percent / 100))

    elif tx.type == "fiat_to_fiat":
        # Обмен фиата на фиат: комиссия = 0
        tx.fee_amount = 0.0
        tx.fee_percent = 0.0
        tx.rate_for_gleb_pnl = 0.0
        fee_direction = "none"


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
    elif tx.type == "fiat_to_fiat":
        tx.profit_currency = "USDT"  # PnL от fiat_to_fiat считается в USDT

    if tx.type == "fiat_to_crypto":
        # клиент отдаёт фиат, получает крипту
        # проверяем, достаточно ли крипты (to_asset), чтобы выдать клиенту
        if to_cash["balance"] < tx.amount_to_final:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.to_asset} in cash")    

        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})  
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})     

        # Создаём лот фиата (этот кэш позже "сгорит" при покупках USDT за этот же фиат)
        fiat_currency = tx.from_asset           # 'CZK' | 'EUR' | 'USD'
        fiat_in_fact  = Decimal(str(tx.amount_from))   # фактический приток фиата в кассу       
        usdt_out_fact = Decimal(str(tx.amount_to_final)) # фактическая выдача USDT клиенту      

        # Эффективный курс покупки = полученный фиат / выданный USDT
        lot_rate_eff = fiat_in_fact / usdt_out_fact

        db.fiat_lots.insert_one({
            "currency": fiat_currency,                # в какой валюте этот лот
            "remaining": float(fiat_in_fact),         # сколько фиата осталось в этом лоте      
            "rate": float(lot_rate_eff),              # эффективный курс с учетом комиссии (FIAT/USDT)
            "tx_id": None,  # будем заполнять после создания транзакции
            "created_at": datetime.utcnow(),
            "meta": {
                "source": "fiat_to_crypto",
                "fee_percent": float(tx.fee_percent),
            }
        })

    elif tx.type == "crypto_to_fiat":
        # клиент отдаёт крипту, получает фиат - проверяем баланс, но НЕ обновляем пока
        if to_cash["balance"] < tx.amount_to_final:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.to_asset} in cash")    

    elif tx.type == "fiat_to_fiat":
        # Обмен фиата на фиат
        # Проверяем баланс from_asset
        if from_cash["balance"] < tx.amount_from:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.from_asset} in cash")  

    # --- Подсчёт реализованной прибыли ---
    realized_profit = 0.0

    if tx.type == "fiat_to_fiat" and tx.from_asset in FIAT_ASSETS:
        # FIFO расчет себестоимости to_asset в USDT
        # Для fiat_to_fiat PnL не рассчитывается! Это просто обмен.
        # PnL будет рассчитана позже, когда we sell this to_asset через crypto_to_fiat
        def D(x):
            return Decimal(str(x))

        from_asset_currency = tx.from_asset
        fiat_out_fact = D(tx.amount_from)           # сколько фиата отдали (CZK)
        to_fiat_in = D(tx.amount_to_final)          # сколько фиata получили (EUR)

        # Просто накапливаем себестоимость для to_asset (EUR)
        need = fiat_out_fact
        eps = D("0.0000001")
        cost_usdt_total = D(0)  # Себестоимость EUR в USDT

        while need > eps:
            lot = db.fiat_lots.find_one(
                {"currency": from_asset_currency, "remaining": {"$gt": 0}},
                sort=[("created_at", 1)]
            )
            if not lot:
                print(f"WARNING: No {from_asset_currency} lots available for FIFO calculation in fiat_to_fiat")
                break

            lot_rem = D(lot["remaining"])
            lot_rate = D(lot["rate"])  # CZK/USDT курс при исходной покупке
            take = lot_rem if lot_rem <= need else need
            matched_usdt = take / lot_rate  # сколько USDT эквивалента в этом куске CZK

            # Себестоимость этой части EUR в USDT
            cost_piece_usdt = matched_usdt
            cost_usdt_total += cost_piece_usdt

            # Update lot
            new_rem = (lot_rem - take).quantize(D("0.0000001"))
            db.fiat_lots.update_one({"_id": lot["_id"]}, {"$set": {"remaining": float(new_rem)}})

            # НЕ логируем PnL для fiat_to_fiat, так как PnL будет при продаже EUR

            need -= take

        # Для fiat_to_fiat нет реализованной прибыли
        realized_profit = 0.0
        tx.profit_currency = "USDT"

        # Сохраняем себестоимость to_asset в USDT
        if cost_usdt_total > eps:
            rate_usdt_of_fiat_in = to_fiat_in / cost_usdt_total
            tx.cost_usdt_of_fiat_in = float(cost_usdt_total.quantize(D("0.0001"), rounding=ROUND_HALF_UP))
            tx.rate_usdt_of_fiat_in = float(rate_usdt_of_fiat_in.quantize(D("0.0001"), rounding=ROUND_HALF_UP))

        # Обновляем кассу
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": -tx.amount_from}})    
        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": tx.amount_to_final}})   

    elif tx.type == "crypto_to_fiat" and tx.from_asset == "USDT" and tx.to_asset in FIAT_ASSETS:
        # Двухэтапная логика FIFO по фиатным лотам
        def D(x):
            return Decimal(str(x))

        fiat_currency   = tx.to_asset                     # 'CZK' | 'EUR' | 'USD'
        fiat_out_fact   = D(tx.amount_to_final)           # сколько фиата реально отдали клиенту
        usdt_in_fact    = D(tx.amount_from)               # сколько USDT получили от клиента    
        sell_rate       = D(tx.rate_used)                 # FIAT/USDT базовый курс

        # Эффективный курс = фактически выданный фиат / полученный USDT
        sell_rate_eff = fiat_out_fact / usdt_in_fact

        pnl_fiat = D(0)
        pnl_usdt = D(0)
        need     = fiat_out_fact
        eps      = D("0.0000001")

        # ЭТАП 1: Берём из живых лотов (fiat_to_crypto)
        while need > eps:
            lot = db.fiat_lots.find_one(
                {
                    "currency": fiat_currency,
                    "remaining": {"$gt": 0},
                    "meta.source": "fiat_to_crypto"  # Только живые лоты
                },
                sort=[("created_at", 1)]
            )
            if not lot:
                # Больше нет живых лотов, переходим на этап 2
                break

            lot_rem  = D(lot["remaining"])
            lot_rate = D(lot["rate"])
            take     = lot_rem if lot_rem <= need else need       # сколько забираем из этого лота
            matched_usdt = take / sell_rate_eff                    # сколько USDT закрываем этим куском

            # кусочный PnL в валюте лота: (курс лота − курс продажи_эфф) × закрытый USDT        
            pnl_piece_fiat = (lot_rate - sell_rate_eff) * matched_usdt
            # для перевода прибыли в USDT используем эффективный курс продажи
            if fiat_currency == "EUR":
                pnl_piece_usdt = pnl_piece_fiat * sell_rate_eff  # EUR: умножаем
            else:
                pnl_piece_usdt = pnl_piece_fiat / sell_rate_eff  # CZK/USD: делим

            pnl_fiat += pnl_piece_fiat
            pnl_usdt += pnl_piece_usdt

            # уменьшаем остаток лота
            new_rem = (lot_rem - take).quantize(D("0.0000001"))
            db.fiat_lots.update_one({"_id": lot["_id"]}, {"$set": {"remaining": float(new_rem)}})

            # лог матчинга (удобно для аудита/отчётов)
            db.pnl_matches.insert_one({
                "currency": fiat_currency,
                "open_lot_id": str(lot["_id"]),
                "close_tx_id": None,
                "stage": 1,  # этап 1 - живые лоты
                "fiat_used": float(take),
                "matched_usdt": float(matched_usdt),
                "lot_rate": float(lot_rate),
                "sell_rate_eff": float(sell_rate_eff),
                "pnl_fiat": float(pnl_piece_fiat),
                "pnl_usdt": float(pnl_piece_usdt),
                "created_at": datetime.utcnow()
            })

            need -= take

        # ЭТАП 2: Если осталась потребность - берём из лотов fiat_to_fiat (обменных пунктов)    
        while need > eps:
            lot = db.fiat_lots.find_one(
                {
                    "currency": fiat_currency,
                    "remaining": {"$gt": 0},
                    "meta.source": "fiat_to_fiat"  # Лоты из обменных пунктов
                },
                sort=[("created_at", 1)]
            )
            if not lot:
                # Нет лотов для данной валюты - выходим из цикла
                print(f"WARNING: No {fiat_currency} fiat_to_fiat lots available for stage 2")   
                break

            lot_rem  = D(lot["remaining"])

            # Для fiat_to_fiat лотов используем cost_usdt_of_fiat_in для PnL расчета
            cost_usdt_of_fiat_in = D(str(lot["meta"].get("cost_usdt_of_fiat_in", 0)))

            # Курс лота = фиат / cost_usdt (сколько фиата на 1 USDT)
            if cost_usdt_of_fiat_in > 0:
                lot_rate = lot_rem / cost_usdt_of_fiat_in
            else:
                lot_rate = D(lot["rate"])  # fallback to stored rate

            take = lot_rem if lot_rem <= need else need
            matched_usdt = take / sell_rate_eff  # сколько USDT получаем от клиента

            # ✅ ПРАВИЛЬНЫЙ PnL расчет для fiat_to_fiat лотов:
            # Находим себестоимость проданной части в USDT
            portion = take / lot_rem  # какая доля лота продается
            cost_usdt_portion = cost_usdt_of_fiat_in * portion  # себестоимость в USDT

            # PnL = выручка в USDT - себестоимость в USDT
            pnl_piece_usdt = matched_usdt - cost_usdt_portion
            # Конвертируем PnL в фиат для отображения
            if fiat_currency == "EUR":
                pnl_piece_fiat = pnl_piece_usdt * sell_rate_eff  # EUR: умножаем
            else:
                pnl_piece_fiat = pnl_piece_usdt / sell_rate_eff  # CZK/USD: делим

            pnl_fiat += pnl_piece_fiat
            pnl_usdt += pnl_piece_usdt

            # уменьшаем остаток лота
            new_rem = (lot_rem - take).quantize(D("0.0000001"))
            db.fiat_lots.update_one({"_id": lot["_id"]}, {"$set": {"remaining": float(new_rem)}})

            # лог матчинга
            db.pnl_matches.insert_one({
                "currency": fiat_currency,
                "open_lot_id": str(lot["_id"]),
                "close_tx_id": None,
                "stage": 2,  # этап 2 - обменные пункты
                "fiat_used": float(take),
                "matched_usdt": float(matched_usdt),
                "lot_rate": float(lot_rate),
                "sell_rate_eff": float(sell_rate_eff),
                "pnl_fiat": float(pnl_piece_fiat),
                "pnl_usdt": float(pnl_piece_usdt),
                "cost_usdt_of_fiat_in": float(cost_usdt_of_fiat_in),
                "created_at": datetime.utcnow()
            })

            need -= take

        # ЭТАП 3: Если осталась потребность - значит, она покрывается из депозитов (без PnL)    
        if need > eps:
            matched_usdt = need / sell_rate_eff
            db.pnl_matches.insert_one({
                "currency": fiat_currency,
                "open_lot_id": "deposit",
                "close_tx_id": None,
                "stage": 3,  # этап 3 - депозиты
                "fiat_used": float(need),
                "matched_usdt": float(matched_usdt),
                "lot_rate": float(sell_rate_eff), # Себестоимость равна курсу продажи
                "sell_rate_eff": float(sell_rate_eff),
                "pnl_fiat": 0.0, # Депозиты не генерируют PnL
                "pnl_usdt": 0.0,
                "created_at": datetime.utcnow()
            })
            need = D(0)

        # округляем и сохраняем в транзакцию
        realized_profit_fiat = pnl_fiat.quantize(D("0.01"), rounding=ROUND_HALF_UP)
        realized_profit_usdt = pnl_usdt.quantize(D("0.0001"), rounding=ROUND_HALF_UP)

        realized_profit = float(realized_profit_fiat)        # profit в валюте транзакции       
        tx.profit_currency = fiat_currency
        # tx.profit_usdt = float(realized_profit_usdt)   # можно добавить в модель при необходимости

    # Для fiat_to_fiat: создаём лот для to_asset (EUR) с сохранённой себестоимостью в USDT      
    # Этот лот будет использован на следующем этапе (в crypto_to_fiat)
    if tx.type == "fiat_to_fiat" and tx.cost_usdt_of_fiat_in and tx.cost_usdt_of_fiat_in > 0:   
        def D(x):
            return Decimal(str(x))

        fiat_currency_to = tx.to_asset
        fiat_in_fact_to = D(str(tx.amount_to_final))

        # Курс to_asset/USDT на основе себестоимости
        lot_rate_to = fiat_in_fact_to / D(str(tx.cost_usdt_of_fiat_in))

        db.fiat_lots.insert_one({
            "currency": fiat_currency_to,
            "remaining": float(fiat_in_fact_to),
            "rate": float(lot_rate_to),
            "tx_id": None,  # будем заполнять после создания транзакции
            "created_at": datetime.utcnow(),
            "meta": {
                "source": "fiat_to_fiat",
                "cost_usdt_of_fiat_in": float(tx.cost_usdt_of_fiat_in),
                "rate_usdt_of_fiat_in": float(tx.rate_usdt_of_fiat_in)
            }
        })

    # Обновляем кассу ТОЛЬКО после успешного расчета прибыли (если это crypto_to_fiat)
    if tx.type == "crypto_to_fiat":
        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})  
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})     

    tx.profit = float(realized_profit)

    tx_data = tx.dict()
    tx_data["created_at"] = datetime.utcnow()
    tx_data["is_modified"] = False
    tx_data["realized_profit"] = float(realized_profit)

    result = db.transactions.insert_one(tx_data)
    tx_data["_id"] = result.inserted_id

    # Добавляем в Google Sheets
    sheets_manager.add_transaction(tx_data)

    # Обновляем сводный лист с кассой и прибылью
    try:
        cash_items = list(db.cash.find({}, {"_id": 0}))
        cash_status = {item["asset"]: item["balance"] for item in cash_items}

        pipeline = [
            {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
        ]
        profit_results = list(db.transactions.aggregate(pipeline))
        realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}

        sheets_manager.update_summary_sheet(cash_status, realized_profits)
    except Exception as e:
        print(f"Failed to update summary sheet: {e}")

    return {
        "type": tx.type,
        "rate_used": tx.rate_used,
        "rate_for_gleb_pnl": tx.rate_for_gleb_pnl,
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

