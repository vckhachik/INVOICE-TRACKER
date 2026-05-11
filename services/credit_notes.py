from .api import get, post, patch, delete
from config import API_BASE_URL


def fetch_credit_notes(
    is_paid=None,
    is_approved_to_pay=None,
    supplier=None,
    review_status=None,
    limit=100,
    offset=0,
):
    params = []
    if is_paid is not None:
        params.append(f"is_paid={str(is_paid).lower()}")
    if is_approved_to_pay is not None:
        params.append(f"is_approved_to_pay={str(is_approved_to_pay).lower()}")
    if supplier:
        params.append(f"supplier={supplier}")
    if review_status:
        params.append(f"review_status={review_status}")
    params.append(f"limit={limit}")
    params.append(f"offset={offset}")
    query = "?" + "&".join(params) if params else ""
    return get(f"/credit-notes/{query}")


def fetch_credit_note(credit_note_id: int):
    return get(f"/credit-notes/{credit_note_id}")


def create_manual_credit_note(payload: dict):
    return post("/credit-notes/manual", payload)


def upload_credit_note(file):
    file.seek(0)
    return post("/credit-notes/upload", files={"file": (file.name, file, file.type)})


def update_credit_note(credit_note_id: int, data: dict):
    return patch(f"/credit-notes/{credit_note_id}", data=data)


def update_credit_note_status(
    credit_note_id: int,
    is_paid=None,
    is_approved_to_pay=None,
    is_legacy=None,
):
    data = {}
    if is_paid is not None:
        data["is_paid"] = is_paid
    if is_approved_to_pay is not None:
        data["is_approved_to_pay"] = is_approved_to_pay
    if is_legacy is not None:
        data["is_legacy"] = is_legacy
    if not data:
        return None
    return patch(f"/credit-notes/{credit_note_id}/status", data=data)


def delete_credit_note(credit_note_id: int):
    return delete(f"/credit-notes/{credit_note_id}")


def fetch_credit_note_links(credit_note_id: int):
    return get(f"/credit-notes/{credit_note_id}/links")


def create_credit_note_link(credit_note_id: int, invoice_id: int = None, allocated_amount=None):
    data = {}
    if invoice_id is not None:
        data["invoice_id"] = invoice_id
    if allocated_amount is not None:
        data["allocated_amount"] = float(allocated_amount)
    return post(f"/credit-notes/{credit_note_id}/links", data)


def delete_credit_note_link(credit_note_id: int, link_id: int):
    return delete(f"/credit-notes/{credit_note_id}/links/{link_id}")


def get_credit_note_file_url(credit_note_id: int):
    import streamlit as st
    token = st.session_state.get("session_token", "")
    return f"{API_BASE_URL}/credit-notes/{credit_note_id}/file?token={token}"
