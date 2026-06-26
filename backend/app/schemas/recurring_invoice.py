from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

VALID_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


class RecurringInvoiceCreate(BaseModel):
    supplier_name_raw: str = Field(min_length=1)
    invoice_number_base: str = Field(min_length=1)
    gross_amount: Decimal
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: int
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: str = "GBP"
    description: Optional[str] = None
    frequency: str
    frequency_interval: int = Field(default=1, ge=1)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    start_date: date
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(default=None, ge=1)

    @field_validator("gross_amount")
    @classmethod
    def validate_gross(cls, v):
        if v <= 0:
            raise ValueError("gross_amount must be greater than 0")
        return v

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v):
        if v not in VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of: {', '.join(sorted(VALID_FREQUENCIES))}")
        return v

    @model_validator(mode="after")
    def validate_entity_and_dates(self):
        if not self.paying_entity_raw and self.paying_entity_id is None:
            raise ValueError("Either paying_entity_raw or paying_entity_id must be provided")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class RecurringInvoiceUpdate(BaseModel):
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class RecurringInvoiceResponse(BaseModel):
    id: int
    supplier_name_raw: str
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: int
    invoice_number_base: str
    gross_amount: Decimal
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: str
    description: Optional[str] = None
    frequency: str
    frequency_interval: int
    day_of_month: Optional[int] = None
    start_date: date
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = None
    occurrence_count: int
    next_due_date: date
    last_generated_at: Optional[datetime] = None
    is_active: bool
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True
