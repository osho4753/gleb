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
    def save_snapshot(operation_type: str, description: str = "") -> str:
        """
        Сохраняет снимок текущего состояния перед операцией
        
        Args:
            operation_type: Тип операции (create_transaction, delete_transaction, deposit, withdrawal, etc.)
            description: Описание операции для удобства
            
        Returns:
            ID созданного снимка
        """
        try:
            # Собираем текущее состояние всех критичных коллекций
            snapshot = {
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "description": description,
                
                # Сохраняем все транзакции
                "transactions": list(db.transactions.find()),
                
                # Сохраняем состояние кассы
                "cash": list(db.cash.find()),
                
                # Сохраняем фиатные лоты (для FIFO)
                "fiat_lots": list(db.fiat_lots.find()),
                
                # Сохраняем PnL матчинги
                "pnl_matches": list(db.pnl_matches.find())
            }
            
            # Вставляем снимок
            result = db.history_snapshots.insert_one(snapshot)
            
            # Ограничиваем количество снимков
            HistoryManager._cleanup_old_snapshots()
            
            print(f"✅ Snapshot saved: {operation_type} - {description}")
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"❌ Failed to save snapshot: {e}")
            return None
    
    @staticmethod
    def _cleanup_old_snapshots():
        """Удаляет старые снимки, оставляя только последние MAX_SNAPSHOTS"""
        try:
            # Считаем количество снимков
            count = db.history_snapshots.count_documents({})
            
            if count > HistoryManager.MAX_SNAPSHOTS:
                # Получаем снимки отсортированные по времени (старые первыми)
                old_snapshots = list(
                    db.history_snapshots.find()
                    .sort("timestamp", 1)
                    .limit(count - HistoryManager.MAX_SNAPSHOTS)
                )
                
                # Удаляем старые снимки
                for snapshot in old_snapshots:
                    db.history_snapshots.delete_one({"_id": snapshot["_id"]})
                
                print(f"🧹 Cleaned up {len(old_snapshots)} old snapshots")
                
        except Exception as e:
            print(f"❌ Failed to cleanup snapshots: {e}")
    
    @staticmethod
    def get_last_snapshot() -> Optional[Dict[str, Any]]:
        """
        Получает последний сохраненный снимок
        
        Returns:
            Снимок состояния или None если снимков нет
        """
        try:
            snapshot = db.history_snapshots.find_one(
                {},
                sort=[("timestamp", -1)]  # Сортировка по убыванию времени
            )
            return snapshot
            
        except Exception as e:
            print(f"❌ Failed to get last snapshot: {e}")
            return None
    
    @staticmethod
    def restore_snapshot(snapshot_id: Optional[str] = None) -> bool:
        """
        Восстанавливает состояние из снимка
        
        Args:
            snapshot_id: ID снимка для восстановления. Если None, берется последний снимок
            
        Returns:
            True если восстановление прошло успешно, False иначе
        """
        try:
            # Получаем снимок
            if snapshot_id:
                from bson import ObjectId
                snapshot = db.history_snapshots.find_one({"_id": ObjectId(snapshot_id)})
            else:
                snapshot = HistoryManager.get_last_snapshot()
            
            if not snapshot:
                print("❌ No snapshot found to restore")
                return False
            
            print(f"🔄 Restoring snapshot from {snapshot['timestamp']}: {snapshot['operation_type']}")
            
            # Восстанавливаем транзакции
            db.transactions.delete_many({})
            if snapshot.get("transactions"):
                # Удаляем _id из снимка перед вставкой (MongoDB создаст новые)
                transactions = snapshot["transactions"]
                for tx in transactions:
                    if "_id" in tx:
                        original_id = tx["_id"]
                        tx["_id"] = original_id  # Сохраняем оригинальные ID
                db.transactions.insert_many(transactions)
            
            # Восстанавливаем кассу
            db.cash.delete_many({})
            if snapshot.get("cash"):
                cash_items = snapshot["cash"]
                for item in cash_items:
                    if "_id" in item:
                        original_id = item["_id"]
                        item["_id"] = original_id
                db.cash.insert_many(cash_items)
            
            # Восстанавливаем фиатные лоты
            db.fiat_lots.delete_many({})
            if snapshot.get("fiat_lots"):
                lots = snapshot["fiat_lots"]
                for lot in lots:
                    if "_id" in lot:
                        original_id = lot["_id"]
                        lot["_id"] = original_id
                db.fiat_lots.insert_many(lots)
            
            # Восстанавливаем PnL матчи
            db.pnl_matches.delete_many({})
            if snapshot.get("pnl_matches"):
                matches = snapshot["pnl_matches"]
                for match in matches:
                    if "_id" in match:
                        original_id = match["_id"]
                        match["_id"] = original_id
                db.pnl_matches.insert_many(matches)
            
            # Удаляем восстановленный снимок (он уже не нужен)
            db.history_snapshots.delete_one({"_id": snapshot["_id"]})
            
            print(f"✅ Snapshot restored successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to restore snapshot: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def get_history(limit: int = 10) -> list:
        """
        Получает список последних снимков для отображения истории
        
        Args:
            limit: Максимальное количество снимков для возврата
            
        Returns:
            Список снимков с метаинформацией
        """
        try:
            snapshots = list(
                db.history_snapshots.find(
                    {},
                    {
                        "_id": 1,
                        "timestamp": 1,
                        "operation_type": 1,
                        "description": 1
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
