from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class CreditNoteResponse(BaseModel):
    id: int
    file_id: Optional[int] = None
    supplier_name_raw: Optional[str] = None
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: Optional[int] = None
    credit_number: Optional[str] = None
    credit_date: Optional[date] = None
    gross_amount: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    ocr_status: Optional[str] = None
    extraction_status: Optional[str] = None
    review_status: Optional[str] = None
    is_approved_to_pay: bool = False
    is_paid: bool = False
    is_legacy: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreditNoteCreate(BaseModel):
    supplier_name_raw: str = Field(min_length=1)
    credit_number: str = Field(min_length=1)
    gross_amount: Decimal
    credit_date: date
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: int
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: str = "GBP"

    @field_validator("gross_amount")
    @classmethod
    def validate_gross_amount(cls, v):
        if v <= 0:
            raise ValueError("gross_amount must be greater than 0")
        return v


class CreditNoteStatusUpdate(BaseModel):
    is_paid: Optional[bool] = None
    is_approved_to_pay: Optional[bool] = None
    is_legacy: Optional[bool] = None


class CreditNoteLinkCreate(BaseModel):
    invoice_id: Optional[int] = None
    allocated_amount: Optional[Decimal] = None


class CreditNoteLinkResponse(BaseModel):
    id: int
    credit_note_id: int
    invoice_id: Optional[int] = None
    allocated_amount: Optional[Decimal] = None
    created_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True
