from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Rate(BaseModel):
    from_asset: str
    to_asset: str
    rate: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Transaction(BaseModel):
    type: str                     # "crypto_to_fiat", "fiat_to_crypto", "fiat_to_fiat"
    from_asset: str
    to_asset: str
    amount_from: float
    rate_used: float              # <-- теперь обязательно передаётся вручную
    fee_percent: Optional[float] = 0.0
    amount_to_clean: Optional[float] = None
    fee_amount: Optional[float] = None
    amount_to_final: Optional[float] = None
    profit: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
