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
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255))          # null until first password set
    role = Column(String(20), nullable=False, default="finance")
    is_active = Column(Boolean, nullable=False, default=True)
    must_reset_password = Column(Boolean, nullable=False, default=True)
    failed_login_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime)
    last_login_at = Column(DateTime)
    password_set_at = Column(DateTime)
    invited_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    group_name = Column(String)
    description = Column(Text, nullable=True)
    source_entity_id = Column(
        Integer,
        ForeignKey("entities.id", use_alter=True, name="fk_projects_source_entity_id"),
        nullable=True,
    )
    created_at = Column(DateTime, server_default=func.now())


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    aliases = Column(JSON)
    project_id_default = Column(Integer, ForeignKey("projects.id"))
    show_as_project = Column(Boolean, nullable=False, default=False)
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
    is_legacy = Column(Boolean, default=False, nullable=False)
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


class InvoiceActivityLog(Base):
    __tablename__ = "invoice_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    event_label = Column(String, nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    session_token = Column(String(128), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    last_active_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    ip_address = Column(String(45))
    user_agent = Column(String(500))


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_type = Column(String(20), nullable=False)  # 'invite' or 'reset'
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50), nullable=False)
    target_type = Column(String(50))
    target_id = Column(String(50))
    event_metadata = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, server_default=func.now())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_at = Column(DateTime, server_default=func.now())
    note = Column(Text)
    status = Column(String(20), nullable=False, default="pending")
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    resolution_note = Column(Text)


class FxRate(Base):
    __tablename__ = "fx_rates"

    id = Column(Integer, primary_key=True)
    from_currency = Column(String(10), nullable=False)
    to_currency = Column(String(10), nullable=False, default="GBP")
    rate = Column(Numeric(18, 6), nullable=False)
    effective_date = Column(Date, nullable=False)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime, server_default=func.now())


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("invoice_files.id"))
    supplier_name_raw = Column(String)
    paying_entity_raw = Column(String)
    paying_entity_id = Column(Integer, ForeignKey("entities.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    credit_number = Column(String)
    credit_date = Column(Date)
    gross_amount = Column(Numeric(12, 2))
    vat_amount = Column(Numeric(12, 2))
    net_amount = Column(Numeric(12, 2))
    currency = Column(String, default="GBP")
    ocr_status = Column(String, default="pending")
    extraction_status = Column(String, default="pending")
    review_status = Column(String, default="pending")
    is_approved_to_pay = Column(Boolean, default=False)
    is_paid = Column(Boolean, default=False)
    is_legacy = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class CreditNoteLink(Base):
    __tablename__ = "credit_note_links"

    id = Column(Integer, primary_key=True)
    credit_note_id = Column(Integer, ForeignKey("credit_notes.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True)
    allocated_amount = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))