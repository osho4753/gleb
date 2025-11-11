# 🔍 ПОЛНОЕ ОБЪЯСНЕНИЕ АЛГОРИТМА РАСЧЕТА ПРИБЫЛИ

**Дата:** 11 ноября 2025  
**Версия:** 1.0  
**Язык:** Python + FastAPI

---

## 📋 ОБЩАЯ АРХИТЕКТУРА

Система отслеживает операции обмена криптовалют и фиатных денег с расчетом прибыли/убытка.

```
┌─────────────────────────────────────────────────────┐
│          ТАБЛИЦЫ В MONGODB                         │
├─────────────────────────────────────────────────────┤
│ 1. transactions    - сами операции                  │
│ 2. cash            - текущие балансы активов        │
│ 3. fiat_lots       - "партии" фиата с курсами       │
│ 4. pnl_matches     - пары открыт-закрыт для PnL     │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 ОСНОВНАЯ ИДЕЯ

### Суть алгоритма - FIFO с курсами

1. **Когда покупаем крипту за фиат** → фиат становится "активом" с привязанным курсом
2. **Когда продаем крипту за фиат** → смотрим, какой фиат использовался изначально, и считаем разницу курсов
3. **Когда обмениваем фиат на фиат** → просто переводим себестоимость от одного фиата к другому

---

## 📊 ЧЕТЫРЕ ТИПА ТРАНЗАКЦИЙ

### 1️⃣ FIAT_TO_CRYPTO (например: USD → BTC)

**Пример:** Куплю 0.1 BTC за 3000 USD, комиссия 1%

```
Шаг 1: Входные данные
  amount_from = 3000 USD
  rate_used = 30000 USD/BTC
  fee_percent = 1%

Шаг 2: Расчет amount_to_clean (идеальное количество крипты)
  amount_to_clean = 3000 / 30000 = 0.1 BTC

Шаг 3: Расчет комиссии
  fee_amount = 0.1 / (1 + 0.01) = 0.099009... BTC (вычитаем комиссию)
  amount_to_final = 0.099009 BTC (клиент получит это)

Шаг 4: Наша прибыль
  profit = 0.1 - 0.099009 = 0.000991 BTC ≈ 30 USD
  profit_currency = "USD"

Шаг 5: Эффективный курс
  rate_for_gleb_pnl = 3000 / 0.099009 = 30303.03 USD/BTC
  (курс с учетом того, что мы удержали комиссию)

Шаг 6: Создаём ФИАТНЫЙ ЛОТ
  db.fiat_lots.insert_one({
    currency: "USD",
    remaining: 3000.0,
    rate: 30303.03,  // USD/BTC - обратный курс
    meta: { source: "fiat_to_crypto", fee_percent: 1.0 }
  })

  ЧТО ЭТО ЗНАЧИТ: В нашей кассе есть 3000 USD, которые были получены
  за продажу 0.099009 BTC по курсу 30303.03 USD/BTC.

  Этот ЛОТ нужен нам для расчета PnL, когда мы будем продавать
  этот USD на другую валюту!

Шаг 7: Обновляем балансы
  cash[USD] += 3000  (получили фиат)
  cash[BTC] -= 0.099009  (отдали крипту)
```

**Визуально:**

```
Клиент:          Мы (GLEB):
Отдал 3000 USD → Получили 3000 USD ✓ + 30 USD комиссии ✓
Получил 0.099009 BTC ← Отдали 0.099009 BTC ✓
```

---

### 2️⃣ CRYPTO_TO_FIAT (например: BTC → EUR)

**Пример:** Продам 0.1 BTC за 3100 EUR, комиссия 2%

```
Шаг 1: Входные данные
  amount_from = 0.1 BTC
  rate_used = 31000 BTC/EUR
  fee_percent = 2%

Шаг 2: Расчет amount_to_clean (идеальное количество фиата)
  amount_to_clean = 0.1 * 31000 = 3100 EUR

Шаг 3: Расчет комиссии (добавляем к сумме)
  fee_amount = 3100 * 0.02 = 62 EUR
  amount_to_final = 3100 + 62 = 3162 EUR (клиент получит это)

Шаг 4: Наша прибыль
  profit = 62 EUR (комиссия)
  profit_currency = "EUR"

Шаг 5: Эффективный курс
  rate_for_gleb_pnl = 3162 / 0.1 = 31620 BTC/EUR
  (курс с учетом комиссии, которую мы добавили)

Шаг 6: НАХОДИМ ФИАТНЫЕ ЛОТЫ (FIFO)

  ЭТАП 1: Живые лоты (из fiat_to_crypto)
  ─────────────────────────────────────
  Ищем EUR лоты, которые были созданы из fiat_to_crypto.
  Если их нет или мало → переходим на ЭТАП 2.

  Для каждого найденного лота рассчитываем PnL:
    lot_rate = 31620 EUR/BTC (курс, по которому был куплен EUR)
    sell_rate_eff = 31000 EUR/BTC (текущий курс продажи)
    pnl = (31620 - 31000) * 0.1 = 62 EUR ПРИБЫЛЬ! ✓

  ЭТАП 2: Если EUR закончился - лоты из fiat_to_fiat
  ─────────────────────────────────────────────────
  Ищем EUR лоты из обменных пунктов (fiat_to_fiat).
  Здесь логика сложнее - используем cost_usdt_of_fiat_in.

  Для каждого найденного лота:
    cost_usdt = lot.meta.cost_usdt_of_fiat_in
    lot_rate = EUR / USDT (себестоимость в USDT)
    pnl = (lot_rate - sell_rate_eff) * matched_btc

Шаг 7: Логируем все матчи
  db.pnl_matches.insert_one({
    stage: 1,  // этап 1 - живые лоты
    currency: "EUR",
    pnl_fiat: 62.0,
    pnl_usdt: 62.0,
    ...
  })

Шаг 8: Обновляем балансы
  cash[EUR] -= 3162  (отдали фиат клиенту)
  cash[BTC] += 0.1   (получили крипту)

Шаг 9: Сохраняем транзакцию с profit = 62 EUR
```

**Визуально:**

```
FIFO процесс:
┌─────────────────────────────────────────────┐
│ ЛОТЫ В БАЗЕ (открыты)                      │
├─────────────────────────────────────────────┤
│ EUR Лот 1: remaining=500, rate=31620       │
│ EUR Лот 2: remaining=300, rate=31500       │
│ EUR Лот 3: remaining=200, rate=31400       │
└─────────────────────────────────────────────┘
         ↓ Нужно 3162 EUR
┌─────────────────────────────────────────────┐
│ БЕРЕМ FIFO (сначала старые)                │
├─────────────────────────────────────────────┤
│ Берем 500 из Лота 1    PnL: 620 EUR ✓      │
│ Берем 300 из Лота 2    PnL: 300 EUR ✓      │
│ Берем 200 из Лота 3    PnL: 200 EUR ✓      │
│ Берем 1162 из Лота 4   PnL: 1162 EUR ✓     │
├─────────────────────────────────────────────┤
│ ИТОГО: PnL = 2282 EUR                      │
└─────────────────────────────────────────────┘
```

---

### 3️⃣ FIAT_TO_FIAT (например: USD → EUR)

**Пример:** Обменяю 2000 USD на 1900 EUR

```
Шаг 1: Входные данные
  amount_from = 2000 USD
  rate_used = 1.0526315... (USD/EUR, то есть 2000/1900)
  fee_percent = 0 (нет комиссии при обмене)

Шаг 2: Расчет amount_to_clean
  amount_to_clean = 2000 / 1.0526315 = 1900 EUR

Шаг 3: amount_to_final = 1900 EUR (обмена ровно, без потерь)

Шаг 4: profit = 0 (ЭТО КЛЮЧЕВОЙ МОМЕНТ!)
  ⚠️ ДЛЯ FIAT_TO_FIAT ПРИБЫЛЬ НЕ РАССЧИТЫВАЕТСЯ!
  Это просто обмен валут, прибыль появится позже,
  когда мы продадим EUR за крипту или другой фиат.

Шаг 5: FIFO РАСЧЕТ СЕБЕСТОИМОСТИ

  Ищем USD лоты по FIFO:
  ────────────────────────
  USD Лот 1: remaining=1000, rate=30303.03 USD/BTC (from fiat_to_crypto)
  USD Лот 2: remaining=1500, rate=30500.00 USD/BTC (from fiat_to_crypto)

  Нужно потратить 2000 USD:

  a) Берём 1000 USD из Лота 1 (rate=30303.03)
     cost_in_usdt = 1000 / 30303.03 = 0.033003... USDT

  b) Берём 1000 USD из Лота 2 (rate=30500.00)
     cost_in_usdt = 1000 / 30500.00 = 0.032786... USDT

  ИТОГО себестоимость EUR в USDT:
  cost_usdt_of_fiat_in = 0.033003 + 0.032786 = 0.065789 USDT

  ЧТО ЭТО ЗНАЧИТ:
  Чтобы получить 1900 EUR, мы "потратили" USDT эквивалент 0.065789 USDT.
  Значит: rate_usdt_of_fiat_in = 1900 / 0.065789 = 28889.36 EUR/USDT

Шаг 6: Обновляем лоты USD

  USD Лот 1: remaining = 0 (полностью исчерпан)
  USD Лот 2: remaining = 500 (осталось 500)

Шаг 7: Создаём новый ЛОТ для EUR (ВАЖНО!)

  db.fiat_lots.insert_one({
    currency: "EUR",
    remaining: 1900,
    rate: 28889.36,  // EUR/USDT (обратный курс)
    meta: {
      source: "fiat_to_fiat",
      cost_usdt_of_fiat_in: 0.065789,  // сохраняем себестоимость
      rate_usdt_of_fiat_in: 28889.36
    }
  })

  ЗАЧЕМ НУЖЕН ЭТОТ ЛОТ?
  Когда позже мы продадим 1900 EUR за крипту,
  мы используем этот лот для расчета PnL!
  На Stage 2 алгоритма мы будем смотреть на cost_usdt_of_fiat_in.

Шаг 8: Обновляем балансы
  cash[USD] -= 2000
  cash[EUR] += 1900
```

**Визуально - цепочка себестоимости:**

```
НАЧАЛО (fiat_to_crypto):
  Купили BTC за 3000 USD по курсу 30303.03 USD/BTC
  → себестоимость BTC = 0.099009 USDT (скрыто в USD лоте)

ФИАТ_ТУ_ФИАТ:
  2000 USD (из разных лотов) → 1900 EUR
  Себестоимость EUR = сумма себестоимостей потраченных USD
  = 0.033003 + 0.032786 = 0.065789 USDT

ПОЗЖЕ ПРОДАЖА (crypto_to_fiat):
  Продадим 1900 EUR за 3150 EUR/USDT
  PnL = (28889.36 - 3150) * cost_in_usdt = ПРИБЫЛЬ
```

---

### 4️⃣ DEPOSIT и WITHDRAWAL

**Пример DEPOSIT:** Пополню кассу на 5000 USD

```
Просто обновляем баланс:
  cash[USD] += 5000
  profit = 0

Создаём простую транзакцию без лотов.
```

**Пример WITHDRAWAL:** Вывожу 2000 EUR

```
Просто обновляем баланс:
  cash[EUR] -= 2000
  profit = 0

Никаких лотов не касаемся.
```

---

## 🔄 ЭТАП 1 vs ЭТАП 2 в crypto_to_fiat

### ЭТАП 1: "Живые" лоты (из fiat_to_crypto)

```python
lot = db.fiat_lots.find_one({
    "currency": fiat_currency,
    "remaining": {"$gt": 0},
    "meta.source": "fiat_to_crypto"  # ← КЛЮЧЕВОЙ ФИЛЬТР
})

# Логика: курс лота уже известен в USD/BTC
pnl = (lot_rate - sell_rate_eff) * matched_usdt
```

**Пример:**

```
Лот 1: USD, remaining=1000, rate=30303.03 USD/BTC
  (были получены за продажу BTC)

Продаем USD за EUR, sell_rate_eff = 31000 USD/EUR

PnL = (30303.03 - 31000) * matched_usdt
    = -696.97 EUR УБЫТОК (курс упал)
```

---

### ЭТАП 2: Обменные лоты (из fiat_to_fiat)

```python
lot = db.fiat_lots.find_one({
    "currency": fiat_currency,
    "remaining": {"$gt": 0},
    "meta.source": "fiat_to_fiat"  # ← КЛЮЧЕВОЙ ФИЛЬТР
})

# Логика: нужно доставать cost_usdt_of_fiat_in
cost_usdt = lot["meta"]["cost_usdt_of_fiat_in"]
lot_rate = lot_remaining / cost_usdt  # EUR/USDT

pnl = (lot_rate - sell_rate_eff) * matched_usdt
```

**Пример:**

```
Лот 2: EUR, remaining=1900, rate=28889.36 EUR/USDT
  meta.cost_usdt_of_fiat_in: 0.065789
  (были получены из fiat_to_fiat из USD)

Продаем EUR за BTC, sell_rate_eff = 31000 EUR/BTC

cost_usdt = 0.065789
lot_rate = 1900 / 0.065789 = 28889.36 EUR/USDT

PnL = (28889.36 - 31000) * matched_usdt
    = РЕЗУЛЬТАТ (может быть + или -)
```

---

## 🧮 ФОРМУЛЫ

### fiat_to_crypto

```
amount_to_clean = amount_from / rate_used
amount_to_final = amount_to_clean / (1 + fee_percent/100)
fee_amount = amount_to_clean - amount_to_final
profit = fee_amount
rate_for_gleb_pnl = amount_from / amount_to_final

lot_rate = amount_to_final / amount_from  (ОБРАТНЫЙ курс)
```

### crypto_to_fiat

```
amount_to_clean = amount_from * rate_used
fee_amount = amount_to_clean * (fee_percent / 100)
amount_to_final = amount_to_clean + fee_amount
profit = fee_amount
rate_for_gleb_pnl = amount_to_final / amount_from

PnL_FIFO = (lot_rate - sell_rate_eff) * matched_usdt
```

### fiat_to_fiat

```
amount_to_clean = amount_from / rate_used
amount_to_final = amount_to_clean
fee_amount = 0
fee_percent = 0
profit = 0  ← ВСЕГДА НОЛЬ!

cost_usdt_total = SUM(take / lot_rate for all matched lots)
rate_usdt_of_fiat_in = amount_to_final / cost_usdt_total

lot_rate (для нового лота) = amount_to_final / cost_usdt_total
```

---

## 📈 ПОЛНЫЙ ПРИМЕР: USD → BTC → EUR

### Транзакция 1: fiat_to_crypto (USD → BTC)

```
Input:  amount_from=3000 USD, rate=30000 USD/BTC, fee=1%
Output: profit=30 USD

Действия:
  ✓ Создан лот: USD, rate=30303.03, remaining=3000
  ✓ Баланс USD += 3000
  ✓ Баланс BTC -= 0.099009
  ✓ profit = 30 USD
```

### Транзакция 2: fiat_to_fiat (USD → EUR)

```
Input:  amount_from=2000 USD, rate=1.0526, fee=0
Output: profit=0 USDT

Действия:
  ✓ FIFO: берём USD лоты, рассчитываем cost_usdt = 0.065789
  ✓ Создан лот: EUR, rate=28889.36, remaining=1900
  ✓ Баланс USD -= 2000
  ✓ Баланс EUR += 1900
  ✓ profit = 0 (сохранено для позже!)
```

### Транзакция 3: crypto_to_fiat (EUR → BTC)

```
Input:  amount_from=1900 EUR, rate=31000 EUR/BTC, fee=2%
Output: profit=?

Действия:
  ЭТАП 1 (живые лоты EUR - нет)
  ЭТАП 2 (обменные лоты EUR - есть!)
    ✓ Берём EUR лот (cost_usdt=0.065789)
    ✓ PnL = (28889.36 - 31000) * 0.065789 = УБЫТОК
  ✓ Баланс EUR -= 1900
  ✓ Баланс BTC += 1900
  ✓ profit записан в транзакцию
```

---

## 💾 СОСТОЯНИЕ БАЗЫ ДАННЫХ

### После Транзакции 1:

```javascript
// fiat_lots
{ currency: "USD", remaining: 3000, rate: 30303.03, meta: {...} }

// transactions
{ type: "fiat_to_crypto", profit: 30, profit_currency: "USD" }

// cash
{ asset: "USD", balance: 3000 }
{ asset: "BTC", balance: -0.099009 }  // отрицательный = задолжили
```

### После Транзакции 2:

```javascript
// fiat_lots
{ currency: "USD", remaining: 0, rate: 30303.03 }
{ currency: "USD", remaining: 1000, rate: 30500, remaining: 1000 }
{ currency: "EUR", remaining: 1900, rate: 28889.36, meta: {
    source: "fiat_to_fiat",
    cost_usdt_of_fiat_in: 0.065789
  }
}

// transactions
{ type: "fiat_to_fiat", profit: 0, cost_usdt_of_fiat_in: 0.065789 }

// cash
{ asset: "USD", balance: 1000 }
{ asset: "EUR", balance: 1900 }
{ asset: "BTC", balance: -0.099009 }
```

### После Транзакции 3:

```javascript
// fiat_lots
(EUR лот исчерпан)
{ currency: "USD", remaining: 1000 }

// pnl_matches
{ stage: 2, currency: "EUR", pnl_fiat: X, pnl_usdt: Y, cost_usdt_of_fiat_in: 0.065789 }

// transactions
{ type: "crypto_to_fiat", profit: X, profit_currency: "EUR" }

// cash
{ asset: "USD", balance: 1000 }
{ asset: "EUR", balance: 0 }
{ asset: "BTC", balance: 1800.9 }  // получили от клиента
```

---

## 🎓 КЛЮЧЕВЫЕ ОСОБЕННОСТИ

### 1. FIFO порядок

```python
db.fiat_lots.find_one(
    {"currency": ..., "remaining": {"$gt": 0}},
    sort=[("created_at", 1)]  # ← сначала старые!
)
```

### 2. Себестоимость переходит по цепочке

```
USD (фиат_ту_крипто) → BTC (крипто) → USD (обратно, с прибылью)
                      ↓
                    USD → EUR (фиат_ту_фиат)
                      ↓
                    EUR (крипто_ту_фиат) → BTC (с использованием себестоимости)
```

### 3. fiat_to_fiat = ноль прибыли всегда

```python
# Это НЕ бага! Это по дизайну!
if tx.type == "fiat_to_fiat":
    tx.profit = 0  # ← всегда, при любых обстоятельствах
```

### 4. Двухэтапная логика для USDT

```
Stage 1: Живые USD лоты (из fiat_to_crypto)
Stage 2: Обменные USD лоты (из fiat_to_fiat)
```

---

## 🐛 ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема: Баланс уходит в минус

```
Причина: Продали крипту, которой не было в кассе
Решение: Проверка баланса перед транзакцией
```

### Проблема: FIFO лоты исчерпаны

```
Причина: Продали больше валюты, чем было куплено
Решение: Система выдаёт WARNING, но транзакция проходит
```

### Проблема: PnL не совпадает с калькулятором

```
Причина: Скорее всего, обновили rate_used, но не пересчитали
Решение: Используйте PUT /transactions/{id} для обновления
```

---

## 📝 ИТОГОВАЯ ТАБЛИЦА

| Тип            | profit | profit_currency | Создаёт лот? | FIFO?        |
| -------------- | ------ | --------------- | ------------ | ------------ |
| fiat_to_crypto | fee    | from_asset      | ✅ YES       | ❌           |
| crypto_to_fiat | fee    | to_asset        | ❌           | ✅ YES       |
| fiat_to_fiat   | **0**  | USDT            | ✅ YES (EUR) | ✅ YES (USD) |
| deposit        | 0      | —               | ❌           | ❌           |
| withdrawal     | 0      | —               | ❌           | ❌           |

---

## 🚀 ИСПОЛЬЗОВАНИЕ АЛГОРИТМА

### Как добавить транзакцию

```bash
POST /transactions
{
  "type": "fiat_to_crypto",
  "from_asset": "USD",
  "to_asset": "BTC",
  "amount_from": 3000,
  "rate_used": 30000,
  "fee_percent": 1,
  "note": "Первая покупка"
}
```

### Как получить отчет по прибыли

```bash
GET /transactions/profit-summary/EUR
```

Ответ:

```json
{
  "currency": "EUR",
  "realized_profit": {
    "fiat": 150.25,
    "usdt": 150.25
  },
  "remaining_lots": {
    "count": 3,
    "total_value": 5000.0
  }
}
```

---

**Статус:** ✅ ПОДРОБНО ОБЪЯСНЕНО  
**Сложность:** 🔴 ОЧЕНЬ ВЫСОКАЯ  
**Для изучения:** 30-60 минут
