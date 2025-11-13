from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# Tenant Management Models
class Tenant(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    master_key_hash: str = Field(..., description="Hashed master password")
    name: str = Field(..., description="Organization/tenant name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether tenant is active")

class CreateTenant(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    master_key: str = Field(..., description="Plain text master password")
    name: str = Field(..., description="Organization/tenant name")

class TenantAuth(BaseModel):
    master_key: str = Field(..., description="Master password for authentication")

# Cash Desk Management Models (Фаза 2)
class CashDesk(BaseModel):
    id: str = Field(..., alias="_id", description="Unique cash desk identifier")
    tenant_id: str = Field(..., description="Owner tenant identifier")
    name: str = Field(..., description="Cash desk name (e.g., 'Прага', 'Украина')")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether cash desk is active")
    deleted_at: Optional[datetime] = Field(default=None, description="When cash desk was deleted")
    
    class Config:
        validate_by_name = True
        populate_by_name = True

class CreateCashDesk(BaseModel):
    name: str = Field(..., description="Cash desk name")

class UpdateCashDesk(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class Transaction(BaseModel):
    tenant_id: Optional[str] = None  # Tenant isolation field (deprecated, use cash_desk_id)
    cash_desk_id: Optional[str] = None  # Фаза 2: Cash desk isolation field
    type: str                     # "crypto_to_fiat", "fiat_to_crypto", "fiat_to_fiat"
    from_asset: str
    to_asset: str
    amount_from: float
    rate_used: float              # <-- теперь обязательно передаётся вручную
    fee_percent: Optional[float] = 0.0
    amount_to_clean: Optional[float] = None
    fee_amount: Optional[float] = None
    amount_to_final: Optional[float] = None
    rate_for_gleb_pnl: Optional[float] = None
    profit: Optional[float] = None
    profit_currency : Optional[str] = None
    cost_usdt_of_fiat_in: Optional[float] = None  # Себестоимость to_asset в USDT (для fiat_to_fiat)
    rate_usdt_of_fiat_in: Optional[float] = None  # Курс себестоимости to_asset/USDT (для fiat_to_fiat)
    note: Optional[str] = ""      # Поле для пометок к транзакции
    is_modified: Optional[bool] = False  # Флаг изменения транзакции
    modified_at: Optional[datetime] = None  # Время последнего изменения
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TransactionUpdate(BaseModel):
    type: Optional[str] = None
    from_asset: Optional[str] = None
    to_asset: Optional[str] = None
    amount_from: Optional[float] = None
    rate_used: Optional[float] = None
    fee_percent: Optional[float] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None

class CashDeposit(BaseModel):
    tenant_id: Optional[str] = None  # Tenant isolation field (deprecated, use cash_desk_id)
    cash_desk_id: Optional[str] = None  # Фаза 2: Cash desk isolation field
    asset: str
    amount: float = Field(gt=0, description="Amount must be positive")
    note: Optional[str] = ""
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class CashWithdrawal(BaseModel):
    tenant_id: Optional[str] = None  # Tenant isolation field (deprecated, use cash_desk_id)
    cash_desk_id: Optional[str] = None  # Фаза 2: Cash desk isolation field
    asset: str
    amount: float = Field(gt=0, description="Amount must be positive")
    note: Optional[str] = ""
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

# Google Sheets Integration Models
class GoogleSheetsSettings(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier")
    is_enabled: bool = Field(default=False, description="Whether Google Sheets integration is enabled")
    spreadsheet_id: Optional[str] = Field(None, description="Google Sheets spreadsheet ID")
    spreadsheet_url: Optional[str] = Field(None, description="Full URL to the spreadsheet")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class EnableGoogleSheets(BaseModel):
    spreadsheet_url: str = Field(..., description="URL of the Google Spreadsheet to connect")

class GoogleSheetsStatus(BaseModel):
    is_enabled: bool
    spreadsheet_id: Optional[str] = None
    spreadsheet_url: Optional[str] = None
    connection_status: str  # "connected", "error", "not_configured"
    last_updated: Optional[datetime] = None
