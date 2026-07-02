from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class BalanceCreate(BaseModel):
    balance_amount: float
    currency: str = "GBP"
    balance_date: date
    note: Optional[str] = None
    account_name: Optional[str] = None


class BalanceResponse(BaseModel):
    id: int
    entity_id: int
    account_name: Optional[str] = None
    balance_amount: float
    currency: str
    balance_date: date
    note: Optional[str] = None
    entry_type: str
    updated_by_user_id: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True
