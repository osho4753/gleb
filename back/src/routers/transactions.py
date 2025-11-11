"""
Роутер для операций с транзакциями
"""
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

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("")
def create_transaction(tx: Transaction):
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
        sell_rate_eff   = fiat_out_fact / usdt_in_fact

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
            pnl_piece_usdt = pnl_piece_fiat / sell_rate_eff

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
            pnl_piece_fiat = pnl_piece_usdt / sell_rate_eff

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

    db.transactions.insert_one(tx_data)

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


@router.get("")
def get_transactions():
    txs = list(db.transactions.find())
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs


@router.get("/export/csv")
def export_transactions_csv():
    """Экспорт всех транзакций в CSV для Excel"""
    # Получаем все транзакции
    txs = list(db.transactions.find().sort("created_at", 1))
    
    # Создаем StringIO для записи CSV
    output = StringIO()
    writer = csv.writer(output, delimiter=';')  # точка с запятой для Excel
    
    # Заголовки
    writer.writerow([
        'Дата/Время',
        'Тип операции',
        'Принял',
        'Количество',
        'Выдал',
        'Количество',
        'Курс',
        'Комиссия %',
        'Прибыль',
        'Валюта прибыли',
        'Примечание'
    ])
    
    # Маппинг типов транзакций на русский
    type_mapping = {
        'deposit': 'Пополнение',
        'withdrawal': 'Вывод',
        'fiat_to_crypto': 'Фиат → Крипта',
        'crypto_to_fiat': 'Крипта → Фиат',
        'fiat_to_fiat': 'Обмен фиата'
    }
    
    # Заполняем данные
    for tx in txs:
        tx_type = tx.get('type', '')
        created_at = tx.get('created_at', '')
        
        # Форматируем дату
        if isinstance(created_at, datetime):
            date_str = created_at.strftime('%d.%m.%Y %H:%M:%S')
        elif isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M:%S')
            except:
                date_str = created_at
        else:
            date_str = ''
        
        # Обработка разных типов транзакций
        if tx_type in ['deposit', 'withdrawal']:
            # Депозит/вывод
            writer.writerow([
                date_str,
                type_mapping.get(tx_type, tx_type),
                tx.get('from_asset', ''),
                tx.get('amount_from', 0),
                '',
                '',
                '',
                '',
                '',
                '',
                tx.get('note', '')
            ])
        else:
            # Обмен
            writer.writerow([
                date_str,
                type_mapping.get(tx_type, tx_type),
                tx.get('from_asset', ''),
                tx.get('amount_from', 0),
                tx.get('to_asset', ''),
                tx.get('amount_to_final', 0),
                tx.get('rate_used', 0),
                tx.get('fee_percent', 0),
                tx.get('realized_profit', 0),
                tx.get('profit_currency', ''),
                tx.get('note', '')
            ])
    
    # Возвращаем CSV файл
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/export/csv/simple")
def export_transactions_simple_csv():
    """Упрощенный экспорт: только принял/выдал"""
    # Получаем все транзакции
    txs = list(db.transactions.find().sort("created_at", 1))
    
    # Создаем StringIO для записи CSV
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # Заголовки
    writer.writerow([
        'Дата',
        'Время',
        'Принял',
        'Выдал',
        'Прибыль',
        'Примечание'
    ])
    
    # Заполняем данные
    for tx in txs:
        tx_type = tx.get('type', '')
        created_at = tx.get('created_at', '')
        
        # Форматируем дату и время
        if isinstance(created_at, datetime):
            date_str = created_at.strftime('%d.%m.%Y')
            time_str = created_at.strftime('%H:%M:%S')
        elif isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y')
                time_str = dt.strftime('%H:%M:%S')
            except:
                date_str = created_at
                time_str = ''
        else:
            date_str = ''
            time_str = ''
        
        # Формируем строки "Принял" и "Выдал"
        if tx_type == 'deposit':
            received = f"{tx.get('amount_from', 0)} {tx.get('from_asset', '')}"
            given = ''
            profit = ''
        elif tx_type == 'withdrawal':
            received = ''
            given = f"{abs(tx.get('amount_from', 0))} {tx.get('from_asset', '')}"
            profit = ''
        else:
            # Обмен
            received = f"{tx.get('amount_from', 0)} {tx.get('from_asset', '')}"
            given = f"{tx.get('amount_to_final', 0)} {tx.get('to_asset', '')}"
            
            # Прибыль
            realized_profit = tx.get('realized_profit', 0)
            profit_currency = tx.get('profit_currency', '')
            if realized_profit and realized_profit != 0:
                profit = f"{realized_profit} {profit_currency}"
            else:
                profit = ''
        
        writer.writerow([
            date_str,
            time_str,
            received,
            given,
            profit,
            tx.get('note', '')
        ])
    
    # Возвращаем CSV файл
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=transactions_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/fiat-lots")
def get_fiat_lots():
    """Получить все фиатные лоты для аудита"""
    lots = list(db.fiat_lots.find())
    for lot in lots:
        lot["_id"] = str(lot["_id"])
    return {"lots": lots}


@router.get("/pnl-matches")
def get_pnl_matches():
    """Получить все PnL матчи для аудита"""
    matches = list(db.pnl_matches.find())
    for match in matches:
        match["_id"] = str(match["_id"])
    return {"matches": matches}


@router.get("/fiat-lots/{currency}")
def get_fiat_lots_by_currency(currency: str):
    """Получить фиатные лоты по валюте"""
    lots = list(db.fiat_lots.find({"currency": currency}))
    for lot in lots:
        lot["_id"] = str(lot["_id"])
    
    total_remaining = sum(lot["remaining"] for lot in lots)
    
    return {
        "currency": currency,
        "lots": lots,
        "total_remaining": total_remaining
    }


@router.get("/profit-summary/{currency}")
def get_profit_summary(currency: str):
    """Получить сводку по прибыли в конкретной валюте"""
    # Общая прибыль из PnL матчей
    matches = list(db.pnl_matches.find({"currency": currency}))
    total_pnl_fiat = sum(match["pnl_fiat"] for match in matches)
    total_pnl_usdt = sum(match["pnl_usdt"] for match in matches)
    
    # Оставшиеся лоты
    lots = list(db.fiat_lots.find({"currency": currency, "remaining": {"$gt": 0}}))
    remaining_value = sum(lot["remaining"] for lot in lots)
    
    # Анализ курсов активных лотов
    rates_info = {}
    if lots:
        rates = [lot["rate"] for lot in lots]
        weighted_avg_rate = sum(lot["rate"] * lot["remaining"] for lot in lots) / remaining_value if remaining_value > 0 else 0
        rates_info = {
            "min_rate": round(min(rates), 5),
            "max_rate": round(max(rates), 5),
            "avg_rate": round(sum(rates) / len(rates), 5),
            "weighted_avg_rate": round(weighted_avg_rate, 5)
        }
    
    # Количество транзакций
    buy_txs = db.transactions.count_documents({"type": "fiat_to_crypto", "from_asset": currency})
    sell_txs = db.transactions.count_documents({"type": "crypto_to_fiat", "to_asset": currency})
    
    return {
        "currency": currency,
        "realized_profit": {
            "fiat": round(total_pnl_fiat, 2),
            "usdt": round(total_pnl_usdt, 4)
        },
        "remaining_lots": {
            "count": len(lots),
            "total_value": round(remaining_value, 2)
        },
        "rates_info": rates_info,
        "transactions": {
            "buy_count": buy_txs,
            "sell_count": sell_txs
        },
        "pnl_matches_count": len(matches)
    }


@router.get("/{transaction_id}")
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


@router.put("/{transaction_id}")
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
                # Эффективный курс = фактически выданный фиат / полученная крипта
                temp_tx.rate_for_gleb_pnl = temp_tx.amount_to_final / temp_tx.amount_from
                temp_tx.profit = round(-temp_tx.fee_amount)
            elif temp_tx.type == "fiat_to_crypto":
                temp_tx.amount_to_final = round(temp_tx.amount_to_clean / (1 + (temp_tx.fee_percent / 100)))
                temp_tx.fee_amount = temp_tx.amount_to_clean - temp_tx.amount_to_final
                # Эффективный курс = полученный фиат / фактически выданная крипта
                temp_tx.rate_for_gleb_pnl = temp_tx.amount_from / temp_tx.amount_to_final
                temp_tx.profit = round(temp_tx.fee_amount)
            else:
                temp_tx.rate_for_gleb_pnl = temp_tx.rate_used
                temp_tx.fee_amount = 0
                temp_tx.amount_to_final = round(temp_tx.amount_to_clean)
                temp_tx.profit = 0
            
            # Добавляем пересчитанные поля в обновление
            update_fields.update({
                "amount_to_clean": temp_tx.amount_to_clean,
                "rate_for_gleb_pnl": temp_tx.rate_for_gleb_pnl,
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


@router.delete("/{transaction_id}")
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