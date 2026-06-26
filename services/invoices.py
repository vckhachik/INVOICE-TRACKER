from .api import get, post, patch, delete, EXTRACTION_TIMEOUT


def fetch_invoices(
    is_paid=None,
    is_approved_to_pay=None,
    is_vat_recovered=None,
    review_status=None,
    limit=100,
    offset=0,
):
    params = []

    if is_paid is not None:
        params.append(f"is_paid={str(is_paid).lower()}")

    if is_approved_to_pay is not None:
        params.append(f"is_approved_to_pay={str(is_approved_to_pay).lower()}")

    if is_vat_recovered is not None:
        params.append(f"is_vat_recovered={str(is_vat_recovered).lower()}")

    if review_status:
        params.append(f"review_status={review_status}")

    params.append(f"limit={limit}")
    params.append(f"offset={offset}")

    query = "?" + "&".join(params) if params else ""
    path = f"/invoices/{query}"
    if path == "/invoices":
        path = "/invoices/"
    return get(path)


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

