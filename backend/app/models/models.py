from sqlalchemy import (
    Column, Integer, String, Boolean,
    Numeric, Date, DateTime, Text,
    ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)  # admin, finance, approver
    created_at = Column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    group_name = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    aliases = Column(JSON)
    project_id_default = Column(Integer, ForeignKey("projects.id"))
    created_at = Column(DateTime, server_default=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class InvoiceFile(Base):
    __tablename__ = "invoice_files"

    id = Column(Integer, primary_key=True)
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    file_hash = Column(String, unique=True)
    source_folder = Column(String)
    mime_type = Column(String)
    uploaded_at = Column(DateTime, server_default=func.now())


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("invoice_files.id"))
    supplier_name_raw = Column(String)
    paying_entity_raw = Column(String)
    paying_entity_id = Column(Integer, ForeignKey("entities.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    invoice_number = Column(String)
    invoice_date = Column(Date)
    due_date = Column(Date)
    description = Column(Text)
    gross_amount = Column(Numeric(12, 2))
    vat_amount = Column(Numeric(12, 2))
    net_amount = Column(Numeric(12, 2))
    currency = Column(String, default="GBP")
    bank_details_raw = Column(Text)
    ocr_status = Column(String, default="pending")
    extraction_status = Column(String, default="pending")
    review_status = Column(String, default="pending")
    is_paid = Column(Boolean, default=False)
    is_vat_recovered = Column(Boolean, default=False)
    is_approved_to_pay = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    provider_name = Column(String)
    raw_payload = Column(JSON)
    field_confidence = Column(JSON)
    overall_confidence = Column(Numeric(5, 2))
    processed_at = Column(DateTime, server_default=func.now())


class MappingRule(Base):
    __tablename__ = "mapping_rules"

    id = Column(Integer, primary_key=True)
    raw_text_pattern = Column(String, nullable=False)
    mapped_entity_id = Column(Integer, ForeignKey("entities.id"))
    mapped_project_id = Column(Integer, ForeignKey("projects.id"))
    priority = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Override(Base):
    __tablename__ = "overrides"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    changed_by = Column(Integer, ForeignKey("users.id"))
    field_name = Column(String, nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    change_reason = Column(Text)
    changed_at = Column(DateTime, server_default=func.now())


class InvoiceAuditLog(Base):
    __tablename__ = "invoice_audit_log"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    changed_by = Column(Integer, ForeignKey("users.id"))
    field_name = Column(String)
    old_value = Column(Text)
    new_value = Column(Text)
    change_reason = Column(Text)
    changed_at = Column(DateTime, server_default=func.now())


class InvoiceFlag(Base):
    __tablename__ = "invoice_flags"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    duplicate_suspected = Column(Boolean, default=False)
    reconciliation_failed = Column(Boolean, default=False)
    low_confidence = Column(Boolean, default=False)
    missing_required_field = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())