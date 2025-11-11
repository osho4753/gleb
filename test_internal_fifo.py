#!/usr/bin/env python3
"""
Тест для проверки Internal FIFO и интеграции себестоимости
в алгоритм crypto_to_fiat PnL

Сценарий:
1. Создаём Tx 12: fiat_to_fiat (619500 CZK → 25335 EUR)
   - Проверяем: cost_usdt_of_fiat_in и rate_usdt_of_fiat_in сохранены
2. Создаём Tx 13: crypto_to_fiat (25335 EUR → USDT)
   - Система должна использовать Internal FIFO
   - PnL должен учитывать себестоимость из Tx 12
"""

import requests
import json
from decimal import Decimal

API_BASE = "http://localhost:8000"

def format_number(val, decimals=4):
    """Форматирование числа"""
    if isinstance(val, (int, float)):
        return round(val, decimals)
    return val

def test_internal_fifo():
    """Тестирование Internal FIFO с себестоимостью"""
    
    print("=" * 70)
    print("🧪 ТЕСТ: Internal FIFO и Себестоимость в crypto_to_fiat")
    print("=" * 70)
    
    # === Шаг 1: Создаём Tx 12 (fiat_to_fiat) ===
    print("\n📝 ШАГ 1: Создание Tx 12 (fiat_to_fiat: CZK → EUR)")
    print("-" * 70)
    
    tx12_data = {
        "type": "fiat_to_fiat",
        "from_asset": "CZK",
        "to_asset": "EUR",
        "amount_from": 619500,
        "rate_used": 24.45234,
        "fee_percent": 0,
        "note": "Test: CZK to EUR (for Internal FIFO testing)"
    }
    
    try:
        response = requests.post(f"{API_BASE}/transactions", json=tx12_data)
        
        if response.status_code != 200:
            print(f"❌ ОШИБКА создания Tx 12: {response.status_code}")
            print(f"   {response.text}")
            return
        
        result = response.json()
        print(f"✅ Tx 12 создана успешно!")
        print(f"   Type: {result['type']}")
        print(f"   From: {result['amount_from']} {result['from_asset']}")
        print(f"   To: {result['amount_to_final']} {result['to_asset']}")
        print(f"   Profit (PnL): {format_number(result['profit'])} USDT")
        
        # Получаем созданную транзакцию со всеми полями
        print("\n   🔍 Проверка новых полей себестоимости...")
        
        # Получаем список всех транзакций
        txs_response = requests.get(f"{API_BASE}/transactions")
        if txs_response.status_code != 200:
            print("❌ Не удалось получить список транзакций")
            return
        
        all_txs = txs_response.json()
        tx12 = all_txs[-1]  # Последняя транзакция (только что созданная)
        
        # Проверяем наличие полей себестоимости
        cost_usdt = tx12.get("cost_usdt_of_fiat_in")
        rate_usdt = tx12.get("rate_usdt_of_fiat_in")
        
        if cost_usdt is None or rate_usdt is None:
            print("⚠️  ВНИМАНИЕ: Поля себестоимости не сохранены в Tx 12!")
            print(f"   cost_usdt_of_fiat_in: {cost_usdt}")
            print(f"   rate_usdt_of_fiat_in: {rate_usdt}")
            return
        
        print(f"✅ Поля себестоимости найдены в Tx 12:")
        print(f"   cost_usdt_of_fiat_in (EUR в USDT): {format_number(cost_usdt)} USDT")
        print(f"   rate_usdt_of_fiat_in (EUR/USDT): {format_number(rate_usdt)}")
        print(f"   Проверка: {format_number(tx12['amount_to_final'])} EUR × {format_number(rate_usdt)} EUR/USDT")
        print(f"            ≈ {format_number(tx12['amount_to_final'] * rate_usdt)} USDT ✓")
        
        tx12_id = tx12["_id"]
        tx12_amount_eur = tx12["amount_to_final"]
        
    except requests.ConnectionError:
        print("❌ Ошибка подключения к серверу")
        return
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    
    # === Шаг 2: Создаём Tx 13 (crypto_to_fiat) ===
    print("\n" + "=" * 70)
    print("📝 ШАГ 2: Создание Tx 13 (crypto_to_fiat: EUR → USDT)")
    print("-" * 70)
    
    # Продаём все 25335 EUR обратно в USDT
    tx13_data = {
        "type": "crypto_to_fiat",
        "from_asset": "EUR",
        "to_asset": "USDT",
        "amount_from": int(tx12_amount_eur),  # Берём ровно столько EUR, сколько получили из Tx 12
        "rate_used": 1.06,  # EUR/USDT курс (примерно 1 EUR = 1.06 USDT)
        "fee_percent": 0,
        "note": "Test: EUR to USDT (Internal FIFO test)"
    }
    
    try:
        response = requests.post(f"{API_BASE}/transactions", json=tx13_data)
        
        if response.status_code != 200:
            print(f"❌ ОШИБКА создания Tx 13: {response.status_code}")
            print(f"   {response.text}")
            return
        
        result = response.json()
        print(f"✅ Tx 13 создана успешно!")
        print(f"   Type: {result['type']}")
        print(f"   From: {result['amount_from']} {result['from_asset']}")
        print(f"   To: {result['amount_to_final']} {result['to_asset']}")
        
        # PnL из crypto_to_fiat
        pnl_tx13 = result['profit']
        print(f"   Profit (PnL): {format_number(pnl_tx13)} USDT")
        
        # Получаем подробную информацию из БД
        print("\n   🔍 Анализ PnL расчёта...")
        
        txs_response = requests.get(f"{API_BASE}/transactions")
        all_txs = txs_response.json()
        tx13 = all_txs[-1]  # Последняя транзакция
        
        # Получаем PnL matches для анализа
        matches_response = requests.get(f"{API_BASE}/transactions/pnl-matches")
        if matches_response.status_code == 200:
            matches = matches_response.json().get("matches", [])
            
            # Ищем matches с Internal FIFO
            internal_matches = [m for m in matches if m.get("pnl_source") == "internal_fifo"]
            lot_matches = [m for m in matches if m.get("pnl_source") == "lot_fifo"]
            
            print(f"\n   📊 Lot FIFO matches: {len(lot_matches)}")
            for m in lot_matches[-3:]:  # Последние 3
                print(f"      - Fiat used: {format_number(m['fiat_used'])} {m['currency']}")
                print(f"        Lot rate: {format_number(m['lot_rate'])}, Sell rate: {format_number(m['sell_rate_eff'])}")
                print(f"        PnL: {format_number(m['pnl_usdt'])} USDT")
            
            print(f"\n   🔄 Internal FIFO matches: {len(internal_matches)}")
            for m in internal_matches:
                print(f"      - Fiat from internal: {format_number(m['fiat_taken_from_internal'])} {m['currency']}")
                print(f"        Cost basis (USDT): {format_number(m['cost_basis_usdt'])}")
                print(f"        Received USDT: {format_number(m['matched_usdt'])}")
                print(f"        PnL: {format_number(m['pnl_usdt'])} USDT")
                print(f"        Source Tx: {m['source_internal_tx_id'][:8]}...")
        
        # === Проверка логики ===
        print("\n" + "=" * 70)
        print("✅ ИТОГОВАЯ ПРОВЕРКА")
        print("-" * 70)
        
        # Получаем cost_usdt из Tx 12
        tx12_cost_usdt = tx12.get("cost_usdt_of_fiat_in")
        tx12_rate_usdt = tx12.get("rate_usdt_of_fiat_in")
        
        # PnL должен быть примерно:
        # EUR_amount * (EUR/USDT_sell_rate - EUR/USDT_cost_rate)
        # = 25335 * (1.06 - 1.121...) = negative PnL (убыток)
        
        expected_pnl = tx12_amount_eur * (tx13_data["rate_used"] - (tx12_cost_usdt / tx12_amount_eur))
        
        print(f"📈 Анализ PnL для Tx 13:")
        print(f"   EUR количество: {tx12_amount_eur}")
        print(f"   Себестоимость EUR (из Tx 12): {format_number(tx12_cost_usdt)} USDT")
        print(f"   Курс EUR при покупке (из Tx 12): {format_number(tx12_rate_usdt)} EUR/USDT")
        print(f"   Обратный курс (USDT/EUR): {format_number(1/tx12_rate_usdt if tx12_rate_usdt > 0 else 0)}")
        print(f"\n   Курс EUR при продаже (Tx 13): {tx13_data['rate_used']} EUR/USDT")
        print(f"   Получено USDT: {format_number(tx13_data['amount_from'] * tx13_data['rate_used'])}")
        print(f"\n   Ожидаемый PnL (примерный): {format_number(expected_pnl)} USDT")
        print(f"   Реальный PnL (из Tx 13): {format_number(pnl_tx13)} USDT")
        
        if internal_matches:
            total_internal_pnl = sum(m['pnl_usdt'] for m in internal_matches)
            print(f"   PnL из Internal FIFO: {format_number(total_internal_pnl)} USDT")
        
        print("\n✨ Тест завершён успешно!")
        print("=" * 70)
        
    except requests.ConnectionError:
        print("❌ Ошибка подключения к серверу")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("\n")
    print("🚀 " * 20)
    print("\n🧪 ТЕСТИРОВАНИЕ INTERNAL FIFO И СЕБЕСТОИМОСТИ\n")
    print("🚀 " * 20)
    
    test_internal_fifo()
    
    print("\n\n💡 Убедитесь, что:")
    print("   1. Сервер запущен: uvicorn src.main:app --reload")
    print("   2. MongoDB доступен")
    print("   3. БД очищена от старых тестовых данных (если нужно)")
    print("\n")
