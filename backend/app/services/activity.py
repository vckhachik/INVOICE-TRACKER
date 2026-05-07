from app.models.models import InvoiceActivityLog


def log_invoice_activity(
    db,
    event_type: str,
    event_label: str,
    invoice_id: int = None,
    changed_by: int = None,
    old_values: dict = None,
    new_values: dict = None,
    project_id: int = None,
    entity_id: int = None,
):
    log = InvoiceActivityLog(
        invoice_id=invoice_id,
        event_type=event_type,
        event_label=event_label,
        changed_by=changed_by,
        old_values=old_values,
        new_values=new_values,
        project_id=project_id,
        entity_id=entity_id,
    )
    db.add(log)