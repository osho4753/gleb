#!/usr/bin/env python3
"""
Тест для проверки системы логирования расчётов
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_calculation_log():
    """Тест создания транзакции с логированием расчётов"""
    
    print("🧪 Тестирование системы логирования расчётов...")
    
    # Создаем тестовую транзакцию fiat_to_crypto
    transaction_data = {
        "type": "fiat_to_crypto",
        "from_asset": "USD",
        "to_asset": "USDT", 
        "amount_from": 1000,
        "rate_used": 1.0,
        "fee_percent": 2.5,
        "note": "Тест логирования расчётов"
    }
    
    try:
        response = requests.post(f"{API_BASE}/transactions", json=transaction_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Транзакция создана успешно!")
            print(f"📊 Тип: {result.get('type')}")
            print(f"💰 Сумма: {result.get('amount_from')} {result.get('from_asset')}")
            print(f"➡️  Получено: {result.get('amount_to_final')} {result.get('to_asset')}")
            print(f"💸 Комиссия: {result.get('fee_amount')}")
            print(f"📈 Прибыль: {result.get('profit')}")
            
        else:
            print(f"❌ Ошибка создания транзакции: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            
    except requests.ConnectionError:
        print("❌ Не удалось подключиться к серверу")
        print("🔧 Убедитесь, что сервер запущен на порту 8000")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_get_transactions():
    """Тест получения транзакций с логом расчётов"""
    
    print("\n📋 Получение списка транзакций...")
    
    try:
        response = requests.get(f"{API_BASE}/transactions")
        
        if response.status_code == 200:
            transactions = response.json()
            print(f"✅ Получено {len(transactions)} транзакций")
            
            # Ищем транзакции с логом расчётов
            transactions_with_log = [tx for tx in transactions if tx.get('calculation_log')]
            
            print(f"🧮 Транзакций с логом расчётов: {len(transactions_with_log)}")
            
            if transactions_with_log:
                tx = transactions_with_log[0]
                print(f"\n📊 Пример лога расчётов (ID: {tx['_id'][:8]}...):")
                
                calc_log = tx.get('calculation_log', [])
                for step in calc_log[:3]:  # Показываем первые 3 шага
                    print(f"   {step['step']}. {step['description']}")
                    if 'details' in step:
                        print(f"      📝 {step['details']}")
                    print(f"      ✅ {step['result_field']}: {step['result_value']}")
                    print()
                
                if len(calc_log) > 3:
                    print(f"   ... и ещё {len(calc_log) - 3} шагов")
                    
        else:
            print(f"❌ Ошибка получения транзакций: {response.status_code}")
            
    except requests.ConnectionError:
        print("❌ Не удалось подключиться к серверу")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("🚀 Запуск тестов системы логирования расчётов\n")
    
    test_calculation_log()
    test_get_transactions()
    
    print("\n✨ Тестирование завершено!")
    print("🌐 Откройте фронтенд и проверьте кнопку 📜 'История расчётов' в таблице транзакций")