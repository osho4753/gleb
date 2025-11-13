"""
Репозиторий для работы с кассой с автоматической изоляцией данных по tenant_id и cash_desk_id
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId


class CashRepository:
    """Репозиторий для безопасной работы с кассой"""
    
    def __init__(self, db, tenant_id: str, cash_desk_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.cash_desk_id = cash_desk_id
        # Базовый фильтр, который применится ко всем запросам
        self.filter = {
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id
        }
    
    def find_one_asset(self, asset: str) -> Optional[Dict[str, Any]]:
        """Найти кассу для конкретного актива"""
        return self.db.cash.find_one({"asset": asset, **self.filter})
    
    def find_all_assets(self) -> List[Dict[str, Any]]:
        """Найти все активы в кассе"""
        return list(self.db.cash.find(self.filter))
    
    def create_asset_if_not_exists(self, asset: str, initial_balance: float = 0.0) -> bool:
        """Создать актив в кассе если его нет. Возвращает True если создан новый."""
        existing = self.find_one_asset(asset)
        if existing:
            return False
        
        self.db.cash.insert_one({
            "asset": asset,
            "balance": initial_balance,
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        return True
    
    def update_balance(self, asset: str, new_balance: float) -> bool:
        """Установить новый баланс актива"""
        result = self.db.cash.update_one(
            {"asset": asset, **self.filter},
            {
                "$set": {
                    "balance": new_balance, 
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    def increment_balance(self, asset: str, amount: float) -> bool:
        """Увеличить/уменьшить баланс актива"""
        result = self.db.cash.update_one(
            {"asset": asset, **self.filter},
            {
                "$inc": {"balance": amount},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0
    
    def get_balance(self, asset: str) -> float:
        """Получить баланс актива"""
        cash_item = self.find_one_asset(asset)
        return cash_item["balance"] if cash_item else 0.0
    
    def delete_asset(self, asset: str) -> bool:
        """Удалить актив из кассы"""
        result = self.db.cash.delete_one({"asset": asset, **self.filter})
        return result.deleted_count > 0


class TransactionRepository:
    """Репозиторий для работы с транзакциями"""
    
    def __init__(self, db, tenant_id: str, cash_desk_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.cash_desk_id = cash_desk_id
        self.filter = {
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id
        }
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Получить все транзакции кассы"""
        return list(self.db.transactions.find(self.filter))
    
    def find_by_id(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Найти транзакцию по ID"""
        try:
            return self.db.transactions.find_one({
                "_id": ObjectId(transaction_id), 
                **self.filter
            })
        except:
            return None
    
    def create(self, transaction_data: Dict[str, Any]) -> str:
        """Создать новую транзакцию"""
        transaction_data.update({
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id,
            "created_at": datetime.utcnow()
        })
        
        result = self.db.transactions.insert_one(transaction_data)
        return str(result.inserted_id)
    
    def update_by_id(self, transaction_id: str, update_data: Dict[str, Any]) -> bool:
        """Обновить транзакцию по ID"""
        try:
            update_data["modified_at"] = datetime.utcnow()
            result = self.db.transactions.update_one(
                {"_id": ObjectId(transaction_id), **self.filter},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except:
            return False
    
    def delete_by_id(self, transaction_id: str) -> bool:
        """Удалить транзакцию по ID"""
        try:
            result = self.db.transactions.delete_one({
                "_id": ObjectId(transaction_id), 
                **self.filter
            })
            return result.deleted_count > 0
        except:
            return False


class FiatLotsRepository:
    """Репозиторий для работы с фиатными лотами"""
    
    def __init__(self, db, tenant_id: str, cash_desk_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.cash_desk_id = cash_desk_id
        self.filter = {
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id
        }
    
    def find_by_currency(self, currency: str) -> List[Dict[str, Any]]:
        """Найти все лоты определенной валюты"""
        return list(self.db.fiat_lots.find({
            "currency": currency,
            **self.filter
        }))
    
    def find_active_by_currency(self, currency: str, source: str = None) -> List[Dict[str, Any]]:
        """Найти активные лоты определенной валюты"""
        query = {
            "currency": currency,
            "remaining": {"$gt": 0},
            **self.filter
        }
        
        if source:
            query["meta.source"] = source
        
        return list(self.db.fiat_lots.find(query).sort("created_at", 1))
    
    def create_lot(self, lot_data: Dict[str, Any]) -> str:
        """Создать новый лот"""
        lot_data.update({
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id,
            "created_at": datetime.utcnow()
        })
        
        result = self.db.fiat_lots.insert_one(lot_data)
        return str(result.inserted_id)
    
    def update_remaining(self, lot_id: str, new_remaining: float) -> bool:
        """Обновить остаток лота"""
        try:
            result = self.db.fiat_lots.update_one(
                {"_id": ObjectId(lot_id), **self.filter},
                {"$set": {"remaining": new_remaining}}
            )
            return result.modified_count > 0
        except:
            return False


class PnLMatchesRepository:
    """Репозиторий для работы с PnL матчами"""
    
    def __init__(self, db, tenant_id: str, cash_desk_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.cash_desk_id = cash_desk_id
        self.filter = {
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id
        }
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Получить все PnL матчи"""
        return list(self.db.pnl_matches.find(self.filter))
    
    def create_match(self, match_data: Dict[str, Any]) -> str:
        """Создать новый PnL матч"""
        match_data.update({
            "tenant_id": self.tenant_id,
            "cash_desk_id": self.cash_desk_id,
            "created_at": datetime.utcnow()
        })
        
        result = self.db.pnl_matches.insert_one(match_data)
        return str(result.inserted_id)


def get_repositories(db, tenant_id: str, cash_desk_id: str) -> tuple:
    """Создать все репозитории для данной кассы"""
    return (
        CashRepository(db, tenant_id, cash_desk_id),
        TransactionRepository(db, tenant_id, cash_desk_id),
        FiatLotsRepository(db, tenant_id, cash_desk_id),
        PnLMatchesRepository(db, tenant_id, cash_desk_id)
    )