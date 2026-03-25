from pydantic import BaseModel
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
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceStatusUpdate(BaseModel):
    is_paid: Optional[bool] = None
    is_approved_to_pay: Optional[bool] = None
    is_vat_recovered: Optional[bool] = None