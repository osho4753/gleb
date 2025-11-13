"""
Модуль для управления историей изменений через снимки состояния
"""
from datetime import datetime
from typing import Optional, Dict, Any
from .db import db


class HistoryManager:
    """Менеджер для сохранения и восстановления снимков состояния"""
    
    MAX_SNAPSHOTS = 50  # Максимальное количество хранимых снимков
    
    @staticmethod
    def save_snapshot(operation_type: str, description: str = "", tenant_id: str = None) -> str:
        """
        Сохраняет снимок текущего состояния перед операцией (только для конкретного tenant)
        
        Args:
            operation_type: Тип операции (create_transaction, delete_transaction, deposit, withdrawal, etc.)
            description: Описание операции для удобства
            tenant_id: ID tenant'а для изоляции снимков
            
        Returns:
            ID созданного снимка
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required for snapshot creation")
            
            # Собираем текущее состояние всех критичных коллекций (только для конкретного tenant)
            tenant_filter = {"tenant_id": tenant_id}
            
            snapshot = {
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "description": description,
                "tenant_id": tenant_id,  # Привязываем снимок к tenant
                
                # Сохраняем транзакции только текущего tenant
                "transactions": list(db.transactions.find(tenant_filter)),
                
                # Сохраняем состояние кассы только текущего tenant
                "cash": list(db.cash.find(tenant_filter)),
                
                # Сохраняем фиатные лоты (для FIFO) только текущего tenant
                "fiat_lots": list(db.fiat_lots.find(tenant_filter)),
                
                # Сохраняем PnL матчинги только текущего tenant
                "pnl_matches": list(db.pnl_matches.find(tenant_filter))
            }
            
            # Вставляем снимок
            result = db.history_snapshots.insert_one(snapshot)
            
            # Ограничиваем количество снимков для конкретного tenant
            HistoryManager._cleanup_old_snapshots(tenant_id)
            
            print(f"✅ Snapshot saved for tenant {tenant_id}: {operation_type} - {description}")
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"❌ Failed to save snapshot: {e}")
            return None
    
    @staticmethod
    def _cleanup_old_snapshots(tenant_id: str):
        """Удаляет старые снимки для конкретного tenant, оставляя только последние MAX_SNAPSHOTS"""
        try:
            # Считаем количество снимков для конкретного tenant
            tenant_filter = {"tenant_id": tenant_id}
            count = db.history_snapshots.count_documents(tenant_filter)
            
            if count > HistoryManager.MAX_SNAPSHOTS:
                # Получаем снимки для tenant отсортированные по времени (старые первыми)
                old_snapshots = list(
                    db.history_snapshots.find(tenant_filter)
                    .sort("timestamp", 1)
                    .limit(count - HistoryManager.MAX_SNAPSHOTS)
                )
                
                # Удаляем старые снимки
                for snapshot in old_snapshots:
                    db.history_snapshots.delete_one({"_id": snapshot["_id"]})
                
                print(f"🧹 Cleaned up {len(old_snapshots)} old snapshots for tenant {tenant_id}")
                
        except Exception as e:
            print(f"❌ Failed to cleanup snapshots: {e}")
    
    @staticmethod
    def get_last_snapshot(tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Получает последний сохраненный снимок для конкретного tenant
        
        Args:
            tenant_id: ID tenant'а
            
        Returns:
            Снимок состояния или None если снимков нет
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required")
                
            snapshot = db.history_snapshots.find_one(
                {"tenant_id": tenant_id},
                sort=[("timestamp", -1)]  # Сортировка по убыванию времени
            )
            return snapshot
            
        except Exception as e:
            print(f"❌ Failed to get last snapshot: {e}")
            return None
    
    @staticmethod
    def restore_snapshot(snapshot_id: Optional[str] = None, tenant_id: str = None) -> bool:
        """
        Восстанавливает состояние из снимка (только для конкретного tenant)
        
        Args:
            snapshot_id: ID снимка для восстановления. Если None, берется последний снимок
            tenant_id: ID tenant'а для изоляции восстановления
            
        Returns:
            True если восстановление прошло успешно, False иначе
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required for snapshot restoration")
            
            # Получаем снимок для конкретного tenant
            if snapshot_id:
                from bson import ObjectId
                snapshot = db.history_snapshots.find_one({
                    "_id": ObjectId(snapshot_id), 
                    "tenant_id": tenant_id  # Проверяем принадлежность к tenant
                })
            else:
                snapshot = HistoryManager.get_last_snapshot(tenant_id)
            
            if not snapshot:
                print(f"❌ No snapshot found to restore for tenant {tenant_id}")
                return False
            
            print(f"🔄 Restoring snapshot from {snapshot['timestamp']} for tenant {tenant_id}: {snapshot['operation_type']}")
            
            # Фильтр для удаления и восстановления данных только текущего tenant
            tenant_filter = {"tenant_id": tenant_id}
            
            # Восстанавливаем транзакции только для текущего tenant
            db.transactions.delete_many(tenant_filter)
            if snapshot.get("transactions"):
                transactions = snapshot["transactions"]
                # Убеждаемся, что все записи имеют правильный tenant_id
                for tx in transactions:
                    tx["tenant_id"] = tenant_id
                if transactions:  # Проверяем, что есть что вставлять
                    db.transactions.insert_many(transactions)
            
            # Восстанавливаем кассу только для текущего tenant
            db.cash.delete_many(tenant_filter)
            if snapshot.get("cash"):
                cash_items = snapshot["cash"]
                for item in cash_items:
                    item["tenant_id"] = tenant_id
                if cash_items:
                    db.cash.insert_many(cash_items)
            
            # Восстанавливаем фиатные лоты только для текущего tenant
            db.fiat_lots.delete_many(tenant_filter)
            if snapshot.get("fiat_lots"):
                lots = snapshot["fiat_lots"]
                for lot in lots:
                    lot["tenant_id"] = tenant_id
                if lots:
                    db.fiat_lots.insert_many(lots)
            
            # Восстанавливаем PnL матчи только для текущего tenant
            db.pnl_matches.delete_many(tenant_filter)
            if snapshot.get("pnl_matches"):
                matches = snapshot["pnl_matches"]
                for match in matches:
                    match["tenant_id"] = tenant_id
                if matches:
                    db.pnl_matches.insert_many(matches)
            
            # Удаляем восстановленный снимок (он уже не нужен)
            db.history_snapshots.delete_one({"_id": snapshot["_id"]})
            
            # Синхронизируем восстановленные данные с Google Sheets (если включено)
            try:
                from .google_sheets import sheets_manager
                
                if sheets_manager.is_enabled_for_tenant(tenant_id):
                    # Получаем восстановленные данные для синхронизации
                    transactions = list(db.transactions.find({"tenant_id": tenant_id}))
                    
                    # Получаем данные кассы
                    cash_items = list(db.cash.find({"tenant_id": tenant_id}, {"_id": 0}))
                    cash_status = {item["asset"]: item["balance"] for item in cash_items}
                    
                    # Получаем данные прибыли
                    pipeline = [
                        {"$match": {"tenant_id": tenant_id}},
                        {"$group": {"_id": "$profit_currency", "total_realized_profit": {"$sum": "$realized_profit"}}}
                    ]
                    profit_results = list(db.transactions.aggregate(pipeline))
                    realized_profits = {r["_id"]: r["total_realized_profit"] for r in profit_results if r["_id"]}
                    
                    # Получаем настройки Google Sheets для синхронизации
                    settings = sheets_manager.get_tenant_settings(tenant_id)
                    if settings and settings.get("spreadsheet_id"):
                        sheets_manager.sync_all_data(
                            settings["spreadsheet_id"],
                            transactions,
                            cash_status,
                            realized_profits,
                            tenant_id
                        )
                        print(f"✅ Google Sheets synchronized after undo for tenant {tenant_id}")
                    
            except Exception as sheets_error:
                print(f"⚠️ Failed to sync Google Sheets after undo: {sheets_error}")
                # Не прерываем выполнение, так как основное восстановление прошло успешно
            
            print(f"✅ Snapshot restored successfully for tenant {tenant_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to restore snapshot: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def get_history(limit: int = 10, tenant_id: str = None) -> list:
        """
        Получает список последних снимков для отображения истории (для конкретного tenant)
        
        Args:
            limit: Максимальное количество снимков для возврата
            tenant_id: ID tenant'а
            
        Returns:
            Список снимков с метаинформацией
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required")
                
            snapshots = list(
                db.history_snapshots.find(
                    {"tenant_id": tenant_id},
                    {
                        "_id": 1,
                        "timestamp": 1,
                        "operation_type": 1,
                        "description": 1,
                        "tenant_id": 1
                    }
                )
                .sort("timestamp", -1)
                .limit(limit)
            )
            
            # Конвертируем ObjectId в строку
            for snapshot in snapshots:
                snapshot["_id"] = str(snapshot["_id"])
            
            return snapshots
            
        except Exception as e:
            print(f"❌ Failed to get history: {e}")
            return []
    
    @staticmethod
    def clear_history():
        """Очищает всю историю снимков (для reset-all-data)"""
        try:
            result = db.history_snapshots.delete_many({})
            print(f"🧹 Cleared {result.deleted_count} history snapshots")
            return result.deleted_count
            
        except Exception as e:
            print(f"❌ Failed to clear history: {e}")
            return 0


# Глобальный экземпляр
history_manager = HistoryManager()
