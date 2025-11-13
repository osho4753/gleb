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
    def save_snapshot(operation_type: str, description: str = "", tenant_id: str = None, cash_desk_id: str = None) -> str:
        """
        Сохраняет снимок текущего состояния перед операцией (для конкретного tenant и кассы)
        
        Args:
            operation_type: Тип операции (create_transaction, delete_transaction, deposit, withdrawal, etc.)
            description: Описание операции для удобства
            tenant_id: ID tenant'а для изоляции снимков
            cash_desk_id: ID кассы для изоляции по кассе
            
        Returns:
            ID созданного снимка
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required for snapshot creation")
            
            # Собираем текущее состояние всех критичных коллекций (для конкретного tenant и кассы)
            tenant_filter = {"tenant_id": tenant_id}
            cash_desk_filter = {"tenant_id": tenant_id}
            
            # Если указан cash_desk_id, фильтруем по нему
            if cash_desk_id:
                cash_desk_filter["cash_desk_id"] = cash_desk_id
            
            snapshot = {
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "description": description,
                "tenant_id": tenant_id,  # Привязываем снимок к tenant
                "cash_desk_id": cash_desk_id,  # Привязываем снимок к кассе
                
                # Сохраняем транзакции только для указанной кассы (или всех касс tenant'а если cash_desk_id не указан)
                "transactions": list(db.transactions.find(cash_desk_filter)),
                
                # Сохраняем состояние кассы только для указанной кассы
                "cash": list(db.cash.find(cash_desk_filter)),
                
                # Сохраняем фиатные лоты (для FIFO) только для указанной кассы
                "fiat_lots": list(db.fiat_lots.find(cash_desk_filter)),
                
                # Сохраняем PnL матчинги только для указанной кассы
                "pnl_matches": list(db.pnl_matches.find(cash_desk_filter))
            }
            
            # Вставляем снимок
            result = db.history_snapshots.insert_one(snapshot)
            
            # Ограничиваем количество снимков для конкретного tenant и кассы
            HistoryManager._cleanup_old_snapshots(tenant_id, cash_desk_id)
            
            cash_desc = f" (desk: {cash_desk_id})" if cash_desk_id else " (all desks)"
            print(f"✅ Snapshot saved for tenant {tenant_id}{cash_desc}: {operation_type} - {description}")
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"❌ Failed to save snapshot: {e}")
            return None
    
    @staticmethod
    def _cleanup_old_snapshots(tenant_id: str, cash_desk_id: str = None):
        """Удаляет старые снимки для конкретного tenant и кассы, оставляя только последние MAX_SNAPSHOTS"""
        try:
            # Считаем количество снимков для конкретного tenant и кассы
            filter_criteria = {"tenant_id": tenant_id}
            if cash_desk_id:
                filter_criteria["cash_desk_id"] = cash_desk_id
            
            count = db.history_snapshots.count_documents(filter_criteria)
            
            if count > HistoryManager.MAX_SNAPSHOTS:
                # Получаем снимки отсортированные по времени (старые первыми)
                old_snapshots = list(
                    db.history_snapshots.find(filter_criteria)
                    .sort("timestamp", 1)
                    .limit(count - HistoryManager.MAX_SNAPSHOTS)
                )
                
                # Удаляем старые снимки
                for snapshot in old_snapshots:
                    db.history_snapshots.delete_one({"_id": snapshot["_id"]})
                
                cash_desc = f" (desk: {cash_desk_id})" if cash_desk_id else " (all desks)"
                print(f"🧹 Cleaned up {len(old_snapshots)} old snapshots for tenant {tenant_id}{cash_desc}")
                
        except Exception as e:
            print(f"❌ Failed to cleanup snapshots: {e}")
    
    @staticmethod
    def get_last_snapshot(tenant_id: str = None, cash_desk_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Получает последний сохраненный снимок для конкретного tenant и кассы
        
        Args:
            tenant_id: ID tenant'а
            cash_desk_id: ID кассы (опционально)
            
        Returns:
            Снимок состояния или None если снимков нет
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required")
            
            filter_criteria = {"tenant_id": tenant_id}
            if cash_desk_id:
                filter_criteria["cash_desk_id"] = cash_desk_id
                
            snapshot = db.history_snapshots.find_one(
                filter_criteria,
                sort=[("timestamp", -1)]  # Сортировка по убыванию времени
            )
            return snapshot
            
        except Exception as e:
            print(f"❌ Failed to get last snapshot: {e}")
            return None
    
    @staticmethod
    def restore_snapshot(snapshot_id: Optional[str] = None, tenant_id: str = None, cash_desk_id: str = None) -> bool:
        """
        Восстанавливает состояние из снимка (для конкретного tenant и кассы)
        
        Args:
            snapshot_id: ID снимка для восстановления. Если None, берется последний снимок
            tenant_id: ID tenant'а для изоляции восстановления
            cash_desk_id: ID кассы для изоляции восстановления
            
        Returns:
            True если восстановление прошло успешно, False иначе
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required for snapshot restoration")
            
            # Получаем снимок для конкретного tenant и кассы
            if snapshot_id:
                from bson import ObjectId
                filter_criteria = {
                    "_id": ObjectId(snapshot_id), 
                    "tenant_id": tenant_id  # Проверяем принадлежность к tenant
                }
                if cash_desk_id:
                    filter_criteria["cash_desk_id"] = cash_desk_id
                snapshot = db.history_snapshots.find_one(filter_criteria)
            else:
                snapshot = HistoryManager.get_last_snapshot(tenant_id, cash_desk_id)
            
            if not snapshot:
                cash_desc = f" (desk: {cash_desk_id})" if cash_desk_id else " (all desks)"
                print(f"❌ No snapshot found to restore for tenant {tenant_id}{cash_desc}")
                return False
            
            cash_desc = f" (desk: {cash_desk_id})" if cash_desk_id else " (all desks)"
            print(f"🔄 Restoring snapshot from {snapshot['timestamp']} for tenant {tenant_id}{cash_desc}: {snapshot['operation_type']}")
            
            # Фильтр для удаления и восстановления данных
            restore_filter = {"tenant_id": tenant_id}
            if cash_desk_id:
                restore_filter["cash_desk_id"] = cash_desk_id
            
            # Восстанавливаем транзакции
            db.transactions.delete_many(restore_filter)
            if snapshot.get("transactions"):
                transactions = snapshot["transactions"]
                for tx in transactions:
                    tx["tenant_id"] = tenant_id
                    if cash_desk_id:
                        tx["cash_desk_id"] = cash_desk_id
                if transactions:
                    db.transactions.insert_many(transactions)
            
            # Восстанавливаем кассу
            db.cash.delete_many(restore_filter)
            if snapshot.get("cash"):
                cash_items = snapshot["cash"]
                for item in cash_items:
                    item["tenant_id"] = tenant_id
                    if cash_desk_id:
                        item["cash_desk_id"] = cash_desk_id
                if cash_items:
                    db.cash.insert_many(cash_items)
            
            # Восстанавливаем фиатные лоты
            db.fiat_lots.delete_many(restore_filter)
            if snapshot.get("fiat_lots"):
                lots = snapshot["fiat_lots"]
                for lot in lots:
                    lot["tenant_id"] = tenant_id
                    if cash_desk_id:
                        lot["cash_desk_id"] = cash_desk_id
                if lots:
                    db.fiat_lots.insert_many(lots)
            
            # Восстанавливаем PnL матчи
            db.pnl_matches.delete_many(restore_filter)
            if snapshot.get("pnl_matches"):
                matches = snapshot["pnl_matches"]
                for match in matches:
                    match["tenant_id"] = tenant_id
                    if cash_desk_id:
                        match["cash_desk_id"] = cash_desk_id
                if matches:
                    db.pnl_matches.insert_many(matches)
            
            # Удаляем восстановленный снимок (он уже не нужен)
            db.history_snapshots.delete_one({"_id": snapshot["_id"]})
            
            print(f"✅ Snapshot restored successfully for tenant {tenant_id}{cash_desc}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to restore snapshot: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def get_history(limit: int = 10, tenant_id: str = None, cash_desk_id: str = None) -> list:
        """
        Получает список последних снимков для отображения истории (для конкретного tenant и кассы)
        
        Args:
            limit: Максимальное количество снимков для возврата
            tenant_id: ID tenant'а
            cash_desk_id: ID кассы (опционально)
            
        Returns:
            Список снимков с метаинформацией
        """
        try:
            if not tenant_id:
                raise ValueError("tenant_id is required")
            
            filter_criteria = {"tenant_id": tenant_id}
            if cash_desk_id:
                filter_criteria["cash_desk_id"] = cash_desk_id
                
            snapshots = list(
                db.history_snapshots.find(
                    filter_criteria,
                    {
                        "_id": 1,
                        "timestamp": 1,
                        "operation_type": 1,
                        "description": 1,
                        "tenant_id": 1,
                        "cash_desk_id": 1
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
    def clear_history(tenant_id: str = None, cash_desk_id: str = None):
        """Очищает историю снимков (для reset-all-data)
        
        Args:
            tenant_id: ID tenant'а. Если не указан, очищает всю историю
            cash_desk_id: ID кассы. Если не указан, очищает историю всех касс tenant'а
        """
        try:
            if tenant_id:
                filter_criteria = {"tenant_id": tenant_id}
                if cash_desk_id:
                    filter_criteria["cash_desk_id"] = cash_desk_id
                
                # Очищаем историю для конкретного tenant'а (и кассы если указана)
                result = db.history_snapshots.delete_many(filter_criteria)
                
                cash_desc = f" (desk: {cash_desk_id})" if cash_desk_id else " (all desks)"
                print(f"🧹 Cleared {result.deleted_count} history snapshots for tenant {tenant_id}{cash_desc}")
            else:
                # Очищаем всю историю (для полного сброса системы)
                result = db.history_snapshots.delete_many({})
                print(f"🧹 Cleared {result.deleted_count} history snapshots (all)")
            
            return result.deleted_count
            
        except Exception as e:
            print(f"❌ Failed to clear history: {e}")
            return 0


# Глобальный экземпляр
history_manager = HistoryManager()
