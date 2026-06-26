from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import FxRate, User
from app.core.deps import current_user
from app.core.permissions import require_permission, Permission

router = APIRouter(prefix="/fx", tags=["fx"])

SUPPORTED_CURRENCIES = ["GBP", "EUR", "USD", "SAR", "AED", "CHF", "LBP"]

CURRENCY_SYMBOLS = {
    "GBP": "£",
    "EUR": "€",
    "USD": "$",
    "SAR": "﷼",
    "AED": "د.إ",
    "CHF": "CHF",
    "LBP": "LL",
}


class FxRateIn(BaseModel):
    from_currency: str
    rate: Decimal
    effective_date: Optional[date] = None


class FxRateOut(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    source: str

    class Config:
        from_attributes = True


@router.get("/rates", response_model=List[FxRateOut])
def get_rates(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    rates = []
    for currency in SUPPORTED_CURRENCIES:
        if currency == "GBP":
            continue
        rate = (
            db.query(FxRate)
            .filter(
                FxRate.from_currency == currency,
                FxRate.to_currency == "GBP",
            )
            .order_by(FxRate.effective_date.desc())
            .first()
        )
        if rate:
            rates.append(rate)
    return rates


@router.post("/rates", response_model=FxRateOut)
def set_rate(body: FxRateIn, db: Session = Depends(get_db), actor: User = Depends(require_permission(Permission.SYSTEM_SETTINGS))):
    currency = body.from_currency.upper().strip()

    if currency not in SUPPORTED_CURRENCIES or currency == "GBP":
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {currency}")

    effective_date = body.effective_date or date.today()
    fx_rate = FxRate(
        from_currency=currency,
        to_currency="GBP",
        rate=body.rate,
        effective_date=effective_date,
        source="manual",
    )

    db.add(fx_rate)
    db.commit()
    db.refresh(fx_rate)

    return fx_rate
