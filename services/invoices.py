from urllib.parse import quote

from .api import get, post, patch, delete, EXTRACTION_TIMEOUT


def fetch_invoices(
    is_paid=None,
    is_approved_to_pay=None,
    is_vat_recovered=None,
    review_status=None,
    expense_nature=None,
    aging_bucket=None,
    project_id=None,
    paying_entity_id=None,
    search=None,
    sort_by=None,
    sort_dir="desc",
    limit=100,
    offset=0,
):
    """Returns {"items": [...], "total": N}. All filtering, sorting, and
    pagination happens server-side — this only forwards the selected
    controls as query params."""
    params = []

    if is_paid is not None:
        params.append(f"is_paid={str(is_paid).lower()}")

    if is_approved_to_pay is not None:
        params.append(f"is_approved_to_pay={str(is_approved_to_pay).lower()}")

    if is_vat_recovered is not None:
        params.append(f"is_vat_recovered={str(is_vat_recovered).lower()}")

    if review_status:
        params.append(f"review_status={review_status}")

    if expense_nature:
        params.append(f"expense_nature={expense_nature}")

    if aging_bucket:
        params.append(f"aging_bucket={quote(aging_bucket, safe='')}")

    if project_id is not None:
        params.append(f"project_id={project_id}")

    if paying_entity_id is not None:
        params.append(f"paying_entity_id={paying_entity_id}")

    if search and search.strip():
        params.append(f"search={quote(search.strip(), safe='')}")

    if sort_by:
        params.append(f"sort_by={sort_by}")

    params.append(f"sort_dir={sort_dir}")
    params.append(f"limit={limit}")
    params.append(f"offset={offset}")

    query = "?" + "&".join(params) if params else ""
    path = f"/invoices/{query}"
    if path == "/invoices":
        path = "/invoices/"

    result = get(path)
    if not result:
        return {"items": [], "total": 0}
    return result


def fetch_invoice(invoice_id: int):
    return get(f"/invoices/{invoice_id}")


def upload_invoice(file):
    file.seek(0)
    return post(
        "/invoices/upload",
        files={"file": (file.name, file, file.type)},
    )


def upload_invoices_batch(files):
    file_payload = []

    for file in files:
        file.seek(0)
        file_payload.append(
            ("files", (file.name, file, file.type))
        )

    return post("/invoices/upload-batch", files=file_payload)


def trigger_invoice_extraction(invoice_id: int):
    return post(f"/invoices/{invoice_id}/extract", timeout=EXTRACTION_TIMEOUT)


def update_status(
    invoice_id: int,
    is_paid=None,
    is_approved_to_pay=None,
    is_vat_recovered=None,
):
    data = {}

    if is_paid is not None:
        data["is_paid"] = is_paid

    if is_approved_to_pay is not None:
        data["is_approved_to_pay"] = is_approved_to_pay

    if is_vat_recovered is not None:
        data["is_vat_recovered"] = is_vat_recovered

    if not data:
        return None

    return patch(f"/invoices/{invoice_id}/status", data=data)


def update_invoice(invoice_id: int, data: dict):
    return patch(f"/invoices/{invoice_id}", data=data)


def delete_invoice(invoice_id: int):
    return delete(f"/invoices/{invoice_id}")

def get_invoice_file_url(invoice_id: int):
    import streamlit as st
    from config import API_BASE_URL
    token = st.session_state.get("session_token", "")
    return f"{API_BASE_URL}/invoices/{invoice_id}/file?token={token}"


def create_manual_invoice(payload: dict):
    return post("/invoices/manual", payload)


def create_recurring_invoice(payload: dict):
    return post("/invoices/recurring", payload)


def fetch_recurring_invoices(active_only: bool = False):
    qs = "?active_only=true" if active_only else ""
    return get(f"/invoices/recurring{qs}") or []


def update_recurring_invoice(recurring_id: int, payload: dict):
    return patch(f"/invoices/recurring/{recurring_id}", data=payload)


def delete_recurring_invoice(recurring_id: int):
    return delete(f"/invoices/recurring/{recurring_id}")

