from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class InvoiceResponse(BaseModel):
    id: int
    file_id: Optional[int] = None
    supplier_name_raw: Optional[str] = None
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: Optional[int] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    description: Optional[str] = None
    gross_amount: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    ocr_status: Optional[str] = None
    extraction_status: Optional[str] = None
    review_status: Optional[str] = None
    is_paid: bool = False
    is_vat_recovered: bool = False
    is_approved_to_pay: bool = False
    is_legacy: bool
    created_at: datetime
    

    class Config:
        from_attributes = True


class ManualInvoiceCreate(BaseModel):
    supplier_name_raw: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    gross_amount: Decimal
    invoice_date: date
    paying_entity_raw: Optional[str] = None
    paying_entity_id: Optional[int] = None
    project_id: int
    vat_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    description: Optional[str] = None
    currency: str = "GBP"

    @field_validator("gross_amount")
    @classmethod
    def validate_gross_amount(cls, v):
        if v <= 0:
            raise ValueError("gross_amount must be greater than 0")
        return v

    @field_validator("paying_entity_id", "paying_entity_raw")
    @classmethod
    def validate_entity(cls, v, info):
        if info.field_name == "paying_entity_id":
            if v is None and info.data.get("paying_entity_raw") is None:
                raise ValueError("Either paying_entity_raw or paying_entity_id must be provided")
        return v


class InvoiceStatusUpdate(BaseModel):
    is_paid: Optional[bool] = None
    is_approved_to_pay: Optional[bool] = None
    is_vat_recovered: Optional[bool] = None
    is_legacy: Optional[bool] = None