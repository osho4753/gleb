"""
Роутер для операций с транзакциями
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from ..db import db
from ..models import Transaction, TransactionUpdate, InternalFiatExchange
from ..constants import FIAT_ASSETS, SPECIAL_FIAT

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("")
def create_transaction(tx: Transaction):
    """
    Создание транзакции:
    - активы (crypto): USDT, BTC, ETH и т.д.
    - товар (fiat): USD, EUR, CZK
    - при crypto_to_fiat — комиссия ДОПЛАЧИВАЕТСЯ
    - при fiat_to_crypto — комиссия УДЕРЖИВАЕТСЯ
    - прибыль считается при замыкании цикла (продажа кэша)
    """

    # --- Проверки ---
    if tx.type not in ["fiat_to_crypto", "crypto_to_fiat", "fiat_to_fiat", "internal_fiat_exchange"]:
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    # Инициализация переменных
    fee_direction = "none"

    # --- Расчёт amount_to_clean ---

    # --- Расчёт amount_to_clean ---
    if tx.type == "fiat_to_crypto" and tx.from_asset in SPECIAL_FIAT:
        # Клиент платит кронами → делим
        tx.amount_to_clean = tx.amount_from / tx.rate_used
        add_calculation_step(calculation_log, step_counter, 
                           f"Расчет базовой конвертации ({tx.from_asset} -> {tx.to_asset}) по курсу (деление для {tx.from_asset})",
                           "amount_from / rate_used", 
                           f"{tx.amount_from} / {tx.rate_used}",
                           "amount_to_clean", tx.amount_to_clean)
        step_counter += 1
        
    elif tx.type == "crypto_to_fiat" and tx.to_asset in SPECIAL_FIAT:
        # Клиент получает кроны → умножаем
        tx.amount_to_clean = tx.amount_from * tx.rate_used
        add_calculation_step(calculation_log, step_counter,
                           f"Расчет базовой конвертации ({tx.from_asset} -> {tx.to_asset}) по курсу (умножение для {tx.to_asset})",
                           "amount_from * rate_used",
                           f"{tx.amount_from} * {tx.rate_used}",
                           "amount_to_clean", tx.amount_to_clean)
        step_counter += 1
        
    elif tx.type == "crypto_to_fiat" and tx.to_asset == "EUR":
        # Все остальные случаи → стандартно умножаем
        tx.amount_to_clean = tx.amount_from / tx.rate_used
        add_calculation_step(calculation_log, step_counter,
                           f"Расчет базовой конвертации ({tx.from_asset} -> {tx.to_asset}) по курсу (деление для EUR)",
                           "amount_from / rate_used",
                           f"{tx.amount_from} / {tx.rate_used}",
                           "amount_to_clean", tx.amount_to_clean)
        step_counter += 1
    elif tx.type == "fiat_to_fiat":
        # Для fiat_to_fiat: определяем направление по валютам
        # rate_used всегда интерпретируется как: сколько единиц from_asset за 1 to_asset
        # CZK -> USD: 1000 CZK при курсе 21.2 CZK/USD = 1000 ÷ 21.2 = 47.17 USD
        # USD -> CZK: 100 USD при курсе 21.2 CZK/USD = 100 × 21.2 = 2120 CZK
        
        add_calculation_step(calculation_log, step_counter,
                           f"Определение операции fiat_to_fiat: {tx.from_asset} -> {tx.to_asset}",
                           "rate_direction = detect_by_currencies",
                           f"rate_used = {tx.rate_used} ({tx.from_asset}/{tx.to_asset})",
                           "operation_type", f"{tx.from_asset}_to_{tx.to_asset}")
        step_counter += 1
        
        if tx.from_asset == "CZK" and tx.to_asset in ["USD", "EUR"]:
            # CZK -> другая валюта: делим
            tx.amount_to_clean = tx.amount_from / tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               f"CZK -> {tx.to_asset}: деление (крона - базовая в курсе)",
                               "amount_from / rate_used",
                               f"{tx.amount_from} / {tx.rate_used}",
                               "amount_to_clean", tx.amount_to_clean)
            step_counter += 1
        elif tx.from_asset in ["USD", "EUR"] and tx.to_asset == "CZK":
            # Другая валюта -> CZK: умножаем
            tx.amount_to_clean = tx.amount_from * tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               f"{tx.from_asset} -> CZK: умножение (крона - котируемая в курсе)",
                               "amount_from * rate_used",
                               f"{tx.amount_from} * {tx.rate_used}",
                               "amount_to_clean", tx.amount_to_clean)
            step_counter += 1
        elif tx.from_asset == "USD" and tx.to_asset == "EUR":
            # USD -> EUR: делим (rate_used = USD/EUR, например 1.1 USD/EUR)
            tx.amount_to_clean = tx.amount_from / tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               "USD -> EUR: деление (доллар - базовая в курсе USD/EUR)",
                               "amount_from / rate_used",
                               f"{tx.amount_from} / {tx.rate_used}",
                               "amount_to_clean", tx.amount_to_clean)
            step_counter += 1
        elif tx.from_asset == "EUR" and tx.to_asset == "USD":
            # EUR -> USD: умножаем (rate_used = EUR/USD, например 1.1 EUR/USD) 
            tx.amount_to_clean = tx.amount_from * tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               "EUR -> USD: умножение (евро - базовая в курсе EUR/USD)",
                               "amount_from * rate_used",
                               f"{tx.amount_from} * {tx.rate_used}",
                               "amount_to_clean", tx.amount_to_clean)
            step_counter += 1
        else:
            # Fallback: если направление неясно, используем деление
            tx.amount_to_clean = tx.amount_from / tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               f"Fallback fiat_to_fiat: {tx.from_asset} -> {tx.to_asset} (деление)",
                               "amount_from / rate_used",
                               f"{tx.amount_from} / {tx.rate_used}",
                               "amount_to_clean", tx.amount_to_clean)
            step_counter += 1
    else:
        tx.amount_to_clean = tx.amount_from * tx.rate_used
        add_calculation_step(calculation_log, step_counter,
                           f"Стандартный расчет (умножение) для типа {tx.type}",
                           "amount_from * rate_used",
                           f"{tx.amount_from} * {tx.rate_used}",
                           "amount_to_clean", tx.amount_to_clean)
        step_counter += 1

    # --- Расчёт комиссии ---
    add_calculation_step(calculation_log, step_counter,
                        "Начало расчёта комиссий",
                        "fee_calculation_start",
                        f"amount_to_clean = {tx.amount_to_clean}, fee_percent = {tx.fee_percent}%",
                        "calculation_phase", "fees")
    step_counter += 1
    
    if tx.type == "crypto_to_fiat":        
        tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
        add_calculation_step(calculation_log, step_counter,
                           "Расчёт комиссии crypto_to_fiat (добавляется к сумме)",
                           "amount_to_clean * (fee_percent / 100)",
                           f"{tx.amount_to_clean} * ({tx.fee_percent} / 100)",
                           "fee_amount", tx.fee_amount)
        step_counter += 1
        
        tx.amount_to_final = round(tx.amount_to_clean + tx.fee_amount)  # округляем до целого
        add_calculation_step(calculation_log, step_counter,
                           "Итоговая сумма crypto_to_fiat (с комиссией + округление)",
                           "round(amount_to_clean + fee_amount)",
                           f"round({tx.amount_to_clean} + {tx.fee_amount})",
                           "amount_to_final", tx.amount_to_final)
        step_counter += 1
        
        tx.profit = round(-tx.fee_amount) 
        add_calculation_step(calculation_log, step_counter,
                           "Прибыль crypto_to_fiat (отрицательная комиссия)",
                           "round(-fee_amount)",
                           f"round(-{tx.fee_amount})",
                           "profit", tx.profit)
        step_counter += 1
        
        fee_direction = "added"
        if tx.to_asset == "CZK" or tx.to_asset == "USD":
            tx.rate_for_gleb_pnl =  tx.rate_used * (1 + (tx.fee_percent / 100))
            add_calculation_step(calculation_log, step_counter,
                               f"Эффективный курс для расчёта PnL (CZK/USD): включение комиссии",
                               "rate_used * (1 + fee_percent/100)",
                               f"{tx.rate_used} * (1 + {tx.fee_percent}/100)",
                               "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
            step_counter += 1
        elif tx.to_asset == "EUR":
            tx.rate_for_gleb_pnl =  tx.rate_used / (1 + (tx.fee_percent / 100))
            add_calculation_step(calculation_log, step_counter,
                               "Эффективный курс для расчёта PnL (EUR): включение комиссии",
                               "rate_used / (1 + fee_percent/100)",
                               f"{tx.rate_used} / (1 + {tx.fee_percent}/100)",
                               "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
            step_counter += 1

    elif tx.type == "fiat_to_crypto":
        # Клиент платит фиат → мы удерживаем комиссию
        tx.amount_to_final = round(tx.amount_to_clean / (1 + (tx.fee_percent / 100)))  # округляем до целого
        add_calculation_step(calculation_log, step_counter,
                           "Итоговая сумма fiat_to_crypto (удержание комиссии + округление)",
                           "round(amount_to_clean / (1 + fee_percent/100))",
                           f"round({tx.amount_to_clean} / (1 + {tx.fee_percent}/100))",
                           "amount_to_final", tx.amount_to_final)
        step_counter += 1
        
        tx.fee_amount = tx.amount_to_clean - tx.amount_to_final
        add_calculation_step(calculation_log, step_counter,
                           "Расчёт комиссии fiat_to_crypto (разность чистой и итоговой суммы)",
                           "amount_to_clean - amount_to_final",
                           f"{tx.amount_to_clean} - {tx.amount_to_final}",
                           "fee_amount", tx.fee_amount)
        step_counter += 1
        
        tx.profit = round(tx.fee_amount)   
        add_calculation_step(calculation_log, step_counter,
                           "Прибыль fiat_to_crypto (положительная комиссия)",
                           "round(fee_amount)",
                           f"round({tx.fee_amount})",
                           "profit", tx.profit)
        step_counter += 1
        
        fee_direction = "deducted"
        if tx.from_asset == "CZK" or tx.from_asset == "USD":
            tx.rate_for_gleb_pnl =  tx.rate_used * (1 + (tx.fee_percent / 100))
            add_calculation_step(calculation_log, step_counter,
                               f"Эффективный курс fiat_to_crypto (CZK/USD источник): включение комиссии",
                               "rate_used * (1 + fee_percent/100)",
                               f"{tx.rate_used} * (1 + {tx.fee_percent}/100)",
                               "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
            step_counter += 1
        elif tx.from_asset == "EUR":
            tx.rate_for_gleb_pnl =  tx.rate_used / (1 + (tx.fee_percent / 100))
            add_calculation_step(calculation_log, step_counter,
                               "Эффективный курс fiat_to_crypto (EUR источник): включение комиссии",
                               "rate_used / (1 + fee_percent/100)",
                               f"{tx.rate_used} / (1 + {tx.fee_percent}/100)",
                               "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
            step_counter += 1

    elif tx.type == "fiat_to_fiat":
        # Для fiat_to_fiat рассчитываем как при crypto_to_fiat (удерживаем комиссию)
        if tx.fee_percent > 0:
            tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
            add_calculation_step(calculation_log, step_counter,
                               "Расчёт комиссии fiat_to_fiat (процент от чистой суммы)",
                               "amount_to_clean * (fee_percent / 100)",
                               f"{tx.amount_to_clean} * ({tx.fee_percent} / 100)",
                               "fee_amount", tx.fee_amount)
            step_counter += 1
            
            tx.amount_to_final = round(tx.amount_to_clean - tx.fee_amount)
            add_calculation_step(calculation_log, step_counter,
                               "Итоговая сумма fiat_to_fiat (удержание комиссии + округление)",
                               "round(amount_to_clean - fee_amount)",
                               f"round({tx.amount_to_clean} - {tx.fee_amount})",
                               "amount_to_final", tx.amount_to_final)
            step_counter += 1
            
            tx.profit = round(tx.fee_amount)
            add_calculation_step(calculation_log, step_counter,
                               "Прибыль fiat_to_fiat (положительная комиссия)",
                               "round(fee_amount)",
                               f"round({tx.fee_amount})",
                               "profit", tx.profit)
            step_counter += 1
        else:
            tx.fee_amount = 0
            add_calculation_step(calculation_log, step_counter,
                               "Комиссия fiat_to_fiat = 0 (fee_percent = 0)",
                               "fee_amount = 0",
                               "0% комиссия",
                               "fee_amount", 0)
            step_counter += 1
            tx.amount_to_final = round(tx.amount_to_clean)
            add_calculation_step(calculation_log, step_counter,
                               "Итоговая сумма fiat_to_fiat без комиссии (округление чистой суммы)",
                               "round(amount_to_clean)",
                               f"round({tx.amount_to_clean})",
                               "amount_to_final", tx.amount_to_final)
            step_counter += 1
            
            tx.profit = 0
            add_calculation_step(calculation_log, step_counter,
                               "Прибыль fiat_to_fiat без комиссии",
                               "profit = 0",
                               "0% комиссия = 0 прибыли",
                               "profit", 0)
            step_counter += 1
        
        # Для fiat_to_fiat effective rate должен учитывать направление
        add_calculation_step(calculation_log, step_counter,
                            "Расчёт эффективного курса для fiat_to_fiat",
                            "rate_for_gleb_pnl calculation",
                            f"base rate = {tx.rate_used}, fee = {tx.fee_percent}%",
                            "rate_calculation_start", "effective_rate")
        step_counter += 1
        
        if tx.fee_percent > 0:
            # С комиссией: effective rate = base rate + комиссия
            if tx.from_asset == "CZK" and tx.to_asset in ["USD", "EUR"]:
                # CZK -> другая валюта: effective rate выше base rate
                tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
                add_calculation_step(calculation_log, step_counter,
                                   f"Эффективный курс fiat_to_fiat (CZK -> {tx.to_asset}) с комиссией",
                                   "rate_used * (1 + fee_percent/100)",
                                   f"{tx.rate_used} * (1 + {tx.fee_percent}/100)",
                                   "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
                step_counter += 1
            elif tx.from_asset in ["USD", "EUR"] and tx.to_asset == "CZK":
                # Другая валюта -> CZK: effective rate выше base rate  
                tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
                add_calculation_step(calculation_log, step_counter,
                                   f"Эффективный курс fiat_to_fiat ({tx.from_asset} -> CZK) с комиссией",
                                   "rate_used * (1 + fee_percent/100)",
                                   f"{tx.rate_used} * (1 + {tx.fee_percent}/100)",
                                   "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
                step_counter += 1
            else:
                # Для других пар используем стандартную логику
                tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
                add_calculation_step(calculation_log, step_counter,
                                   f"Эффективный курс fiat_to_fiat ({tx.from_asset} -> {tx.to_asset}) стандартная логика с комиссией",
                                   "rate_used * (1 + fee_percent/100)",
                                   f"{tx.rate_used} * (1 + {tx.fee_percent}/100)",
                                   "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
                step_counter += 1
        else:
            # Без комиссии: effective rate = base rate
            tx.rate_for_gleb_pnl = tx.rate_used
            add_calculation_step(calculation_log, step_counter,
                               "Эффективный курс fiat_to_fiat без комиссии (базовый курс)",
                               "rate_for_gleb_pnl = rate_used",
                               f"{tx.rate_used} (без изменений)",
                               "rate_for_gleb_pnl", tx.rate_for_gleb_pnl)
            step_counter += 1
            
        tx.profit_currency = tx.to_asset
        add_calculation_step(calculation_log, step_counter,
                           "Валюта прибыли для fiat_to_fiat",
                           "profit_currency = to_asset",
                           f"profit_currency = {tx.to_asset}",
                           "profit_currency", tx.to_asset)
        step_counter += 1
        
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
        
        # Создаём лот фиата (этот кэш позже "сгорит" при покупках USDT за этот же фиат)
        fiat_currency = tx.from_asset           # 'CZK' | 'EUR' | 'USD'
        fiat_in_fact  = Decimal(str(tx.amount_from))   # фактический приток фиата в кассу
        usdt_out_fact = Decimal(str(tx.amount_to_final)) # фактическая выдача USDT клиенту
        
        # Эффективный курс покупки = полученный фиат / выданный USDT
        lot_rate_eff = fiat_in_fact / usdt_out_fact
        
        add_calculation_step(calculation_log, step_counter,
                           f"Создание фиатного лота при fiat_to_crypto",
                           "lot_rate_eff = fiat_in_fact / usdt_out_fact",
                           f"{float(fiat_in_fact)} / {float(usdt_out_fact)} = {float(lot_rate_eff)}",
                           "lot_rate_effective", float(lot_rate_eff))
        step_counter += 1

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
        
        add_calculation_step(calculation_log, step_counter,
                           "Лот создан и добавлен в базу данных",
                           "fiat_lot_inserted",
                           f"currency: {fiat_currency}, remaining: {float(fiat_in_fact)}, rate: {float(lot_rate_eff)}",
                           "lot_created", True)
        step_counter += 1

    elif tx.type == "crypto_to_fiat":
        # клиент отдаёт крипту, получает фиат - проверяем баланс, но НЕ обновляем пока
        if to_cash["balance"] < tx.amount_to_final:
            raise HTTPException(status_code=400, detail=f"Not enough {tx.to_asset} in cash")
    
    # --- Подсчёт реализованной прибыли ---
    add_calculation_step(calculation_log, step_counter,
                        "Начало расчёта реализованной прибыли",
                        "realized_profit_calculation_start",
                        f"type = {tx.type}, from = {tx.from_asset}, to = {tx.to_asset}",
                        "calculation_phase", "realized_profit")
    step_counter += 1
    
    realized_profit = 0.0

    if tx.type == "crypto_to_fiat" and tx.from_asset == "USDT" and tx.to_asset in FIAT_ASSETS:
        # Новая логика FIFO по фиатным лотам
        add_calculation_step(calculation_log, step_counter,
                           f"Запуск FIFO алгоритма для crypto_to_fiat (USDT -> {tx.to_asset})",
                           "fifo_algorithm_start",
                           f"need_fiat = {tx.amount_to_final}, usdt_received = {tx.amount_from}",
                           "fifo_start", True)
        step_counter += 1
        
        def D(x): 
            return Decimal(str(x))

        fiat_currency   = tx.to_asset                     # 'CZK' | 'EUR' | 'USD'
        fiat_out_fact   = D(tx.amount_to_final)           # сколько фиата реально отдали клиенту
        usdt_in_fact    = D(tx.amount_from)               # сколько USDT получили от клиента
        sell_rate       = D(tx.rate_used)                 # FIAT/USDT базовый курс
        
        # Эффективный курс = фактически выданный фиат / полученный USDT
        sell_rate_eff   = fiat_out_fact / usdt_in_fact
        
        add_calculation_step(calculation_log, step_counter,
                           "Расчёт эффективного курса продажи",
                           "sell_rate_eff = fiat_out_fact / usdt_in_fact",
                           f"{float(fiat_out_fact)} / {float(usdt_in_fact)} = {float(sell_rate_eff)}",
                           "sell_rate_effective", float(sell_rate_eff))
        step_counter += 1

        pnl_fiat = D(0)
        pnl_usdt = D(0)
        need     = fiat_out_fact
        eps      = D("0.0000001")
        
        fifo_iteration = 0

        while need > eps:
            fifo_iteration += 1
            add_calculation_step(calculation_log, step_counter,
                               f"FIFO итерация #{fifo_iteration}",
                               "fifo_iteration_start",
                               f"need = {float(need)}, поиск лота для валюты {fiat_currency}",
                               "fifo_iteration", fifo_iteration)
            step_counter += 1
            
            lot = db.fiat_lots.find_one(
                {"currency": fiat_currency, "remaining": {"$gt": 0}},
                sort=[("created_at", 1)]
            )
            if not lot:
                # Нет лотов для данной валюты - прибыль = 0, выходим из цикла
                add_calculation_step(calculation_log, step_counter,
                                   f"Лоты для валюты {fiat_currency} отсутствуют",
                                   "no_lots_available",
                                   f"WARNING: No {fiat_currency} lots for FIFO",
                                   "fifo_exit", "no_lots")
                step_counter += 1
                print(f"WARNING: No {fiat_currency} lots available for FIFO calculation")
                break

            lot_rem  = D(lot["remaining"])
            lot_rate = D(lot["rate"])
            take     = lot_rem if lot_rem <= need else need       # сколько забираем из этого лота
            matched_usdt = take / sell_rate_eff                    # сколько USDT закрываем этим куском
            
            add_calculation_step(calculation_log, step_counter,
                               f"FIFO #{fifo_iteration}: найден лот",
                               "lot_found",
                               f"lot_remaining = {float(lot_rem)}, lot_rate = {float(lot_rate)}, take = {float(take)}",
                               "lot_processing", {"lot_id": str(lot["_id"]), "take": float(take)})
            step_counter += 1

            # кусочный PnL в валюте лота: (курс лота − курс продажи_эфф) × закрытый USDT
            pnl_piece_fiat = (lot_rate - sell_rate_eff) * matched_usdt
            # для перевода прибыли в USDT используем эффективный курс продажи
            pnl_piece_usdt = pnl_piece_fiat / sell_rate_eff
            
            add_calculation_step(calculation_log, step_counter,
                               f"FIFO #{fifo_iteration}: расчёт PnL кусочка",
                               "pnl_piece = (lot_rate - sell_rate_eff) * matched_usdt",
                               f"({float(lot_rate)} - {float(sell_rate_eff)}) * {float(matched_usdt)} = {float(pnl_piece_fiat)} {fiat_currency}",
                               "pnl_piece_fiat", float(pnl_piece_fiat))
            step_counter += 1

            pnl_fiat += pnl_piece_fiat
            pnl_usdt += pnl_piece_usdt

            # уменьшаем остаток лота
            new_rem = (lot_rem - take).quantize(D("0.0000001"))
            db.fiat_lots.update_one({"_id": lot["_id"]}, {"$set": {"remaining": float(new_rem)}})

            # лог матчинга (удобно для аудита/отчётов)
            db.pnl_matches.insert_one({
                "currency": fiat_currency,
                "open_lot_id": str(lot["_id"]),
                "close_tx_id": None,  # при желании заполни своим id
                "fiat_used": float(take),
                "matched_usdt": float(matched_usdt),
                "lot_rate": float(lot_rate),
                "sell_rate_eff": float(sell_rate_eff),
                "pnl_fiat": float(pnl_piece_fiat),
                "pnl_usdt": float(pnl_piece_usdt),
                "created_at": datetime.utcnow()
            })

            need -= take

        # округляем и сохраняем в транзакцию
        realized_profit_fiat = pnl_fiat.quantize(D("0.01"), rounding=ROUND_HALF_UP)
        realized_profit_usdt = pnl_usdt.quantize(D("0.0001"), rounding=ROUND_HALF_UP)

        realized_profit = float(realized_profit_fiat)        # profit в валюте транзакции
        tx.profit_currency = fiat_currency
        # tx.profit_usdt = float(realized_profit_usdt)   # можно добавить в модель при необходимости

    # Обновляем кассу ТОЛЬКО после успешного расчета прибыли (если это crypto_to_fiat)
    if tx.type == "crypto_to_fiat":
        db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})
        db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})

    tx.profit = float(realized_profit)

    # Финализация логирования расчётов
    add_calculation_step(calculation_log, step_counter,
                        "Завершение расчёта транзакции",
                        "transaction_calculation_complete",
                        f"realized_profit = {realized_profit}, type = {tx.type}",
                        "calculation_complete", True)
    step_counter += 1

    tx_data = tx.dict()
    tx_data["created_at"] = datetime.utcnow()
    tx_data["is_modified"] = False
    tx_data["realized_profit"] = float(realized_profit)
    tx_data["calculation_log"] = calculation_log  # Добавляем логирование расчётов

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


def create_internal_fiat_exchange(from_asset: str, to_asset: str, amount_needed: float, 
                                 internal_rate: float, base_tx_id: str):
    """
    Создает внутреннюю транзакцию обмена фиат-фиат
    Используется когда нужно купить недостающую валюту для клиентской транзакции
    """
    def D(x): 
        return Decimal(str(x))
    
    # Рассчитываем сколько нужно продать исходной валюты с учетом направления
    if from_asset == "CZK" and to_asset in ["USD", "EUR"]:
        # CZK -> другая валюта: умножаем (rate = сколько CZK за 1 USD/EUR)
        amount_to_sell = amount_needed * internal_rate
    elif from_asset in ["USD", "EUR"] and to_asset == "CZK":
        # Другая валюта -> CZK: делим (rate = сколько CZK за 1 USD/EUR)
        amount_to_sell = amount_needed / internal_rate
    elif from_asset == "USD" and to_asset == "EUR":
        # USD -> EUR: умножаем
        amount_to_sell = amount_needed * internal_rate
    elif from_asset == "EUR" and to_asset == "USD":
        # EUR -> USD: делим
        amount_to_sell = amount_needed / internal_rate
    else:
        # Fallback
        amount_to_sell = amount_needed * internal_rate
    
    # Проверяем баланс исходной валюты
    from_cash = db.cash.find_one({"asset": from_asset})
    if not from_cash or from_cash["balance"] < amount_to_sell:
        raise HTTPException(status_code=400, 
                           detail=f"Not enough {from_asset} for internal exchange. Need {amount_to_sell}, have {from_cash['balance'] if from_cash else 0}")
    
    # Создаем внутреннюю транзакцию
    internal_tx = {
        "type": "internal_fiat_exchange",
        "base_transaction_id": base_tx_id,
        "from_asset": from_asset,
        "to_asset": to_asset,
        "amount_from": amount_to_sell,
        "amount_to_final": amount_needed,
        "rate_used": internal_rate,
        "rate_for_gleb_pnl": internal_rate,
        "fee_percent": 0.0,
        "fee_amount": 0.0,
        "profit": 0.0,  # Будет пересчитано через FIFO
        "profit_currency": from_asset,
        "note": f"Internal exchange for transaction {base_tx_id}",
        "created_at": datetime.utcnow(),
        "is_modified": False,
        "realized_profit": 0.0
    }
    
    # FIFO расчет для продаваемой валюты (например, CZK)
    realized_profit = 0.0
    if from_asset in FIAT_ASSETS:
        fiat_currency = from_asset
        fiat_out_fact = D(amount_to_sell)
        
        # Эквивалент в USDT для расчета (предполагаем что всегда через USDT)
        usdt_equivalent = D(amount_needed)  # Покупаем USD, эквивалент в USDT
        
        pnl_fiat = D(0)
        need = fiat_out_fact
        eps = D("0.0000001")
        
        while need > eps:
            lot = db.fiat_lots.find_one(
                {"currency": fiat_currency, "remaining": {"$gt": 0}},
                sort=[("created_at", 1)]
            )
            if not lot:
                print(f"WARNING: No {fiat_currency} lots available for internal FIFO calculation")
                break
            
            lot_rem = D(lot["remaining"])
            lot_rate = D(lot["rate"])
            take = lot_rem if lot_rem <= need else need
            
            # Для внутреннего обмена считаем разницу курсов
            internal_rate_d = D(internal_rate)
            matched_usdt = take / lot_rate
            
            # PnL = (курс лота - курс внутреннего обмена) × закрытый USDT  
            pnl_piece_fiat = (lot_rate - internal_rate_d) * matched_usdt
            pnl_fiat += pnl_piece_fiat
            
            # Уменьшаем остаток лота
            new_rem = (lot_rem - take).quantize(D("0.0000001"))
            db.fiat_lots.update_one({"_id": lot["_id"]}, {"$set": {"remaining": float(new_rem)}})
            
            # Записываем матч
            db.pnl_matches.insert_one({
                "currency": fiat_currency,
                "open_lot_id": str(lot["_id"]),
                "close_tx_id": base_tx_id,
                "transaction_type": "internal_fiat_exchange",
                "fiat_used": float(take),
                "matched_usdt": float(matched_usdt),
                "lot_rate": float(lot_rate),
                "sell_rate_eff": float(internal_rate_d),
                "pnl_fiat": float(pnl_piece_fiat),
                "created_at": datetime.utcnow()
            })
            
            need -= take
        
        realized_profit = float(pnl_fiat.quantize(D("0.01"), rounding=ROUND_HALF_UP))
    
    internal_tx["realized_profit"] = realized_profit
    internal_tx["profit"] = realized_profit
    
    # Обновляем балансы
    db.cash.update_one({"asset": from_asset}, {"$inc": {"balance": -amount_to_sell}})
    db.cash.update_one({"asset": to_asset}, {"$inc": {"balance": amount_needed}})
    
    # Сохраняем внутреннюю транзакцию
    result = db.transactions.insert_one(internal_tx)
    
    return {
        "internal_tx_id": str(result.inserted_id),
        "amount_exchanged": amount_needed,
        "cost": amount_to_sell,
        "rate": internal_rate,
        "realized_profit": realized_profit
    }


@router.post("/fiat-to-fiat")
def create_fiat_to_fiat_transaction(tx: Transaction):
    """
    Создание fiat-to-fiat транзакции с проверкой балансов и автоматическим внутренним обменом
    """
    if tx.type != "fiat_to_fiat":
        raise HTTPException(status_code=400, detail="Invalid transaction type for this endpoint")
    
    # Проверяем что это фиатные валюты
    if tx.from_asset not in FIAT_ASSETS or tx.to_asset not in FIAT_ASSETS:
        raise HTTPException(status_code=400, detail="Both assets must be fiat currencies")
    
    # Рассчитываем суммы для fiat_to_fiat с учетом направления
    # Используем ту же логику, что и в process_transaction
    if tx.from_asset == "CZK" and tx.to_asset in ["USD", "EUR"]:
        # CZK -> другая валюта: делим
        tx.amount_to_clean = tx.amount_from / tx.rate_used
    elif tx.from_asset in ["USD", "EUR"] and tx.to_asset == "CZK":
        # Другая валюта -> CZK: умножаем
        tx.amount_to_clean = tx.amount_from * tx.rate_used
    elif tx.from_asset == "USD" and tx.to_asset == "EUR":
        # USD -> EUR: делим
        tx.amount_to_clean = tx.amount_from / tx.rate_used
    elif tx.from_asset == "EUR" and tx.to_asset == "USD":
        # EUR -> USD: умножаем
        tx.amount_to_clean = tx.amount_from * tx.rate_used
    else:
        # Fallback: деление
        tx.amount_to_clean = tx.amount_from / tx.rate_used
    
    # Расчет комиссии для fiat_to_fiat
    if tx.fee_percent > 0:
        tx.fee_amount = tx.amount_to_clean * (tx.fee_percent / 100)
        tx.amount_to_final = round(tx.amount_to_clean - tx.fee_amount)
    else:
        tx.fee_amount = 0
        tx.amount_to_final = round(tx.amount_to_clean)
    
    # Effective rate для fiat_to_fiat
    if tx.fee_percent > 0:
        # С комиссией: effective rate учитывает комиссию
        if tx.from_asset == "CZK" and tx.to_asset in ["USD", "EUR"]:
            tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
        elif tx.from_asset in ["USD", "EUR"] and tx.to_asset == "CZK":
            tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
        else:
            tx.rate_for_gleb_pnl = tx.rate_used * (1 + (tx.fee_percent / 100))
    else:
        # Без комиссии: effective rate = base rate
        tx.rate_for_gleb_pnl = tx.rate_used
    tx.profit = round(tx.fee_amount) if tx.fee_amount > 0 else 0
    tx.profit_currency = tx.to_asset
    
    # Проверяем баланс валюты, которую нужно выдать
    to_cash = db.cash.find_one({"asset": tx.to_asset})
    if not to_cash:
        db.cash.insert_one({"asset": tx.to_asset, "balance": 0.0, "updated_at": datetime.utcnow()})
        to_cash = {"asset": tx.to_asset, "balance": 0.0}
    
    # Если недостаточно средств - возвращаем информацию для UI
    if to_cash["balance"] < tx.amount_to_final:
        shortage = tx.amount_to_final - to_cash["balance"]
        
        return {
            "status": "insufficient_funds",
            "message": f"Insufficient {tx.to_asset}. Need {tx.amount_to_final}, have {to_cash['balance']}, shortage: {shortage}",
            "shortage": shortage,
            "required_total": tx.amount_to_final,
            "available": to_cash["balance"],
            "currency": tx.to_asset,
            "suggested_sources": [asset for asset in FIAT_ASSETS if asset != tx.to_asset]
        }
    
    # Если средств достаточно - проводим обычную транзакцию
    db.cash.update_one({"asset": tx.to_asset}, {"$inc": {"balance": -tx.amount_to_final}})
    db.cash.update_one({"asset": tx.from_asset}, {"$inc": {"balance": tx.amount_from}})
    
    # Создаем лот для полученной валюты (как при fiat_to_crypto)
    if tx.from_asset in FIAT_ASSETS:
        fiat_currency = tx.from_asset
        fiat_in_fact = Decimal(str(tx.amount_from))
        
        # Эффективный курс с учетом комиссии
        effective_rate = fiat_in_fact / Decimal(str(tx.amount_to_final))
        
        db.fiat_lots.insert_one({
            "currency": fiat_currency,
            "remaining": float(fiat_in_fact),
            "rate": float(effective_rate),
            "tx_id": None,  # будем заполнять после создания транзакции
            "created_at": datetime.utcnow(),
            "meta": {
                "source": "fiat_to_fiat",
                "fee_percent": float(tx.fee_percent),
            }
        })
    
    # Сохраняем транзакцию
    # Инициализация логирования для fiat_to_fiat
    calculation_log_fiat = []
    step_counter_fiat = 1
    
    add_calculation_step(calculation_log_fiat, step_counter_fiat,
                        f"Создание fiat_to_fiat транзакции: {tx.from_asset} -> {tx.to_asset}",
                        "fiat_to_fiat_transaction_start",
                        f"amount = {tx.amount_from}, rate = {tx.rate_used}, fee = {tx.fee_percent}%",
                        "transaction_start", True)
    step_counter_fiat += 1
    
    add_calculation_step(calculation_log_fiat, step_counter_fiat,
                        "Создание лота для fiat_to_fiat транзакции",
                        "fiat_lot_creation",
                        f"currency: {tx.from_asset}, amount: {tx.amount_from}, rate: {tx.rate_for_gleb_pnl}",
                        "lot_creation", True)
    step_counter_fiat += 1
    
    tx_data = tx.dict()
    tx_data["created_at"] = datetime.utcnow()
    tx_data["is_modified"] = False
    tx_data["realized_profit"] = 0.0
    tx_data["related_internal_txns"] = []
    tx_data["calculation_log"] = calculation_log_fiat  # Добавляем логирование для fiat_to_fiat
    
    result = db.transactions.insert_one(tx_data)
    
    return {
        "status": "success",
        "transaction_id": str(result.inserted_id),
        "message": "Fiat-to-fiat transaction completed successfully",
        "details": {
            "from_amount": tx.amount_from,
            "to_amount": tx.amount_to_final,
            "fee": tx.fee_amount,
            "rate": tx.rate_used,
            "effective_rate": tx.rate_for_gleb_pnl
        }
    }


@router.post("/fiat-to-fiat-with-exchange")
def create_fiat_to_fiat_with_internal_exchange(
    main_tx: Transaction, 
    source_asset: str, 
    internal_rate: float
):
    """
    Создает fiat-to-fiat транзакцию с автоматическим внутренним обменом
    для покрытия недостающих средств
    """
    if main_tx.type != "fiat_to_fiat":
        raise HTTPException(status_code=400, detail="Invalid transaction type")
    
    # Рассчитываем основную транзакцию с правильным направлением
    if main_tx.from_asset == "CZK" and main_tx.to_asset in ["USD", "EUR"]:
        main_tx.amount_to_clean = main_tx.amount_from / main_tx.rate_used
    elif main_tx.from_asset in ["USD", "EUR"] and main_tx.to_asset == "CZK":
        main_tx.amount_to_clean = main_tx.amount_from * main_tx.rate_used
    elif main_tx.from_asset == "USD" and main_tx.to_asset == "EUR":
        main_tx.amount_to_clean = main_tx.amount_from / main_tx.rate_used
    elif main_tx.from_asset == "EUR" and main_tx.to_asset == "USD":
        main_tx.amount_to_clean = main_tx.amount_from * main_tx.rate_used
    else:
        main_tx.amount_to_clean = main_tx.amount_from / main_tx.rate_used
    if main_tx.fee_percent > 0:
        main_tx.fee_amount = main_tx.amount_to_clean * (main_tx.fee_percent / 100)
        main_tx.amount_to_final = round(main_tx.amount_to_clean - main_tx.fee_amount)
    else:
        main_tx.fee_amount = 0
        main_tx.amount_to_final = round(main_tx.amount_to_clean)
    
    # Проверяем текущий баланс
    to_cash = db.cash.find_one({"asset": main_tx.to_asset})
    if not to_cash:
        to_cash = {"balance": 0.0}
    
    shortage = main_tx.amount_to_final - to_cash["balance"]
    
    if shortage <= 0:
        raise HTTPException(status_code=400, detail="No shortage, use regular fiat-to-fiat endpoint")
    
    # Создаем основную транзакцию (пока без проведения)
    # Инициализация логирования для fiat_to_fiat с недостатком баланса
    calculation_log_main = []
    step_counter_main = 1
    
    add_calculation_step(calculation_log_main, step_counter_main,
                        f"Создание fiat_to_fiat с недостатком баланса: {main_tx.from_asset} -> {main_tx.to_asset}",
                        "fiat_to_fiat_shortage_start",
                        f"amount = {main_tx.amount_from}, needed = {main_tx.amount_to_final}, shortage = {shortage}",
                        "transaction_start", True)
    step_counter_main += 1
    
    main_tx_data = main_tx.dict()
    main_tx_data["created_at"] = datetime.utcnow()
    main_tx_data["is_modified"] = False
    main_tx_data["related_internal_txns"] = []
    main_tx_data["calculation_log"] = calculation_log_main  # Добавляем логирование
    
    result = db.transactions.insert_one(main_tx_data)
    main_tx_id = str(result.inserted_id)
    
    # Создаем внутренний обмен
    internal_result = create_internal_fiat_exchange(
        from_asset=source_asset,
        to_asset=main_tx.to_asset,
        amount_needed=shortage,
        internal_rate=internal_rate,
        base_tx_id=main_tx_id
    )
    
    # Теперь проводим основную транзакцию
    db.cash.update_one({"asset": main_tx.to_asset}, {"$inc": {"balance": -main_tx.amount_to_final}})
    db.cash.update_one({"asset": main_tx.from_asset}, {"$inc": {"balance": main_tx.amount_from}})
    
    # Обновляем основную транзакцию ссылкой на внутреннюю
    db.transactions.update_one(
        {"_id": result.inserted_id},
        {"$push": {"related_internal_txns": internal_result["internal_tx_id"]}}
    )
    
    return {
        "status": "success",
        "main_transaction_id": main_tx_id,
        "internal_exchange": internal_result,
        "message": f"Transaction completed with internal exchange of {shortage} {main_tx.to_asset}"
    }


@router.get("")
def get_transactions():
    txs = list(db.transactions.find())
    for t in txs:
        t["_id"] = str(t["_id"])
    return txs


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


@router.get("/test-fiat-to-fiat")
def test_fiat_to_fiat_endpoint():
    """Тестовый endpoint для проверки работы fiat-to-fiat функционала"""
    return {
        "message": "Fiat-to-fiat functionality is available",
        "endpoints": [
            "/transactions/fiat-to-fiat",
            "/transactions/fiat-to-fiat-with-exchange"
        ],
        "supported_types": [
            "fiat_to_crypto",
            "crypto_to_fiat", 
            "fiat_to_fiat",
            "internal_fiat_exchange"
        ]
    }