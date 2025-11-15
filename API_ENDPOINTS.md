# API Endpoints Used in Frontend

## Кассы

| Метод | Путь                               | Параметры    | Тело запроса          | Где используется                 |
| ----- | ---------------------------------- | ------------ | --------------------- | -------------------------------- |
| GET   | /cash/status?cash_desk_id={id}     | cash_desk_id | —                     | TransactionsManager, CashManager |
| POST  | /cash/deposit?cash_desk_id={id}    | cash_desk_id | {asset, amount, note} | TransactionsManager, CashManager |
| POST  | /cash/withdrawal?cash_desk_id={id} | cash_desk_id | {asset, amount, note} | TransactionsManager, CashManager |

## Транзакции

| Метод  | Путь                                              | Параметры     | Тело запроса                      | Где используется                                     |
| ------ | ------------------------------------------------- | ------------- | --------------------------------- | ---------------------------------------------------- |
| GET    | /transactions?cash_desk_id={id}                   | cash_desk_id  | —                                 | TransactionsManager, TransactionsHistory, apiAdapter |
| POST   | /transactions?cash_desk_id={id}                   | cash_desk_id  | {type, from_asset, to_asset, ...} | TransactionsManager, apiAdapter                      |
| GET    | /transactions/{transactionId}                     | transactionId | —                                 | TransactionsHistory                                  |
| DELETE | /transactions/{transactionId}                     | transactionId | —                                 | TransactionsHistory                                  |
| GET    | /transactions/calculate-preview?cash_desk_id={id} | cash_desk_id  | —                                 | TransactionsManager                                  |
| GET    | /transactions/export/csv                          | —             | —                                 | TransactionsHistory                                  |
| GET    | /transactions/export/csv/simple                   | —             | —                                 | TransactionsHistory                                  |

## Фиатные лоты

| Метод | Путь                                                 | Параметры              | Тело запроса | Где используется           |
| ----- | ---------------------------------------------------- | ---------------------- | ------------ | -------------------------- |
| GET   | /transactions/fiat-lots/{currency}?cash_desk_id={id} | currency, cash_desk_id | —            | FiatLotsViewer, apiAdapter |

## PnL-матчи

| Метод | Путь                                        | Параметры    | Тело запроса | Где используется       |
| ----- | ------------------------------------------- | ------------ | ------------ | ---------------------- |
| GET   | /transactions/pnl-matches?cash_desk_id={id} | cash_desk_id | —            | PnLMatches, apiAdapter |

## Google Sheets

| Метод | Путь                                       | Параметры  | Тело запроса | Где используется                                         |
| ----- | ------------------------------------------ | ---------- | ------------ | -------------------------------------------------------- |
| GET   | /google-sheets/status                      | —          | —            | GoogleSheetsManager, GoogleSheetsIcon, GoogleSheetsModal |
| POST  | /google-sheets/enable                      | —          | —            | GoogleSheetsManager, GoogleSheetsModal                   |
| POST  | /google-sheets/disable                     | —          | —            | GoogleSheetsManager, GoogleSheetsModal                   |
| POST  | /google-sheets/re-enable                   | —          | —            | GoogleSheetsModal                                        |
| POST  | /google-sheets/disconnect                  | —          | —            | GoogleSheetsModal                                        |
| POST  | /google-sheets/sync-cash-desk/{cashDeskId} | cashDeskId | —            | GoogleSheetsManager                                      |
| POST  | /google-sheets/sync-all                    | —          | —            | GoogleSheetsModal                                        |
| POST  | /google-sheets/sync-aggregate-report       | —          | —            | GoogleSheetsManager                                      |
| GET   | /google-sheets/instructions                | —          | —            | GoogleSheetsModal                                        |

## Системные

| Метод  | Путь                    | Параметры | Тело запроса | Где используется    |
| ------ | ----------------------- | --------- | ------------ | ------------------- |
| DELETE | /reset-all-transactions | —         | —            | TransactionsHistory |
| DELETE | /reset-fiat-lots        | —         | —            | —                   |

## Кассы (менеджмент)

| Метод  | Путь                            | Параметры | Тело запроса | Где используется                  |
| ------ | ------------------------------- | --------- | ------------ | --------------------------------- |
| GET    | /cash-desks/                    | —         | —            | CashDesksManager, cashDeskService |
| GET    | /cash-desks/deleted             | —         | —            | CashDesksManager                  |
| GET    | /cash-desks/{deskId}            | deskId    | —            | CashDesksManager                  |
| GET    | /cash-desks/{deskId}/usage-info | deskId    | —            | SafeCashDeskDeletion              |
| DELETE | /cash-desks/{deskId}            | deskId    | —            | SafeCashDeskDeletion              |
| POST   | /cash-desks/{deskId}/restore    | deskId    | —            | SafeCashDeskDeletion              |

## V2-эндпоинты (если включено)

| Метод | Путь                                     | Параметры    | Тело запроса          | Где используется |
| ----- | ---------------------------------------- | ------------ | --------------------- | ---------------- |
| GET   | /v2/cash-desks/{id}/status               | id           | —                     | apiAdapter       |
| GET   | /v2/cash-desks/{id}/transactions         | id           | —                     | apiAdapter       |
| GET   | /v2/cash-desks/{id}/fiat-lots/{currency} | id, currency | —                     | apiAdapter       |
| GET   | /v2/cash-desks/{id}/pnl-matches          | id           | —                     | apiAdapter       |
| POST  | /v2/cash-desks/{id}/deposit              | id           | {asset, amount, note} | apiAdapter       |
| POST  | /v2/cash-desks/{id}/withdrawal           | id           | {asset, amount, note} | apiAdapter       |
| POST  | /v2/cash-desks/{id}/transactions         | id           | {type, ...}           | apiAdapter       |
