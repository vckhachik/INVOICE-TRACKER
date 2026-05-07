import streamlit as st
import datetime
from services.api import get
from services.invoices import create_manual_invoice
from utils.auth import require_login, can

require_login()

if not can("edit_invoice"):
    st.error("You don't have permission to create invoices.")
    st.stop()

st.set_page_config(page_title="Manual Entry", page_icon="📝", layout="wide")
st.title("📝 Manual Invoice Entry")
st.caption("Create an invoice by entering details manually")

# Load reference data
projects = get("/projects/") or []
entities = get("/entities/") or []

# Prepare dropdown options
project_options = {f"{p.get('name')} ({p.get('group_name')})": p.get("id") for p in projects if p.get("name")}
entity_options = {"(unmapped)": None}
entity_options.update({e.get("name"): e.get("id") for e in entities if e.get("name")})

with st.form("manual_invoice_form"):
    st.subheader("Required Information")

    col1, col2 = st.columns(2)

    with col1:
        supplier_name = st.text_input("Supplier Name", placeholder="Enter supplier name")

    with col2:
        invoice_number = st.text_input("Invoice Number", placeholder="Enter invoice number")

    col3, col4 = st.columns(2)

    with col3:
        invoice_date = st.date_input("Invoice Date", value=datetime.date.today())

    with col4:
        project_id = st.selectbox("Project", options=list(project_options.keys()), index=0 if project_options else None)

    st.subheader("Entity Information")
    col5, col6 = st.columns(2)

    with col5:
        paying_entity_raw = st.text_input("Entity Name (Raw)", placeholder="Enter entity name as it appears on invoice")

    with col6:
        paying_entity_id = st.selectbox(
            "Link to Existing Entity (Optional)",
            options=list(entity_options.keys()),
            index=0,  # Default to "(unmapped)"
            help="Select an existing entity to link this invoice to, or leave as '(unmapped)'"
        )

    st.subheader("Amount Information")
    col7, col8, col9 = st.columns(3)

    with col7:
        gross_amount = st.number_input("Gross Amount", min_value=0.01, step=0.01, format="%.2f")

    with col8:
        vat_amount = st.number_input("VAT Amount", min_value=0.00, step=0.01, format="%.2f", value=0.00)

    with col9:
        net_amount = st.number_input(
            "Net Amount",
            min_value=0.00,
            step=0.01,
            format="%.2f",
            help="Auto-calculated if left blank (Gross - VAT)"
        )

    st.subheader("Optional Details")

    col10, col11 = st.columns(2)

    with col10:
        due_date = st.date_input("Due Date (Optional)", value=None)

    with col11:
        currency = st.selectbox("Currency", options=["GBP", "EUR", "USD"], index=0)

    description = st.text_area("Description (Optional)", placeholder="Additional notes or description")

    submitted = st.form_submit_button("Create Invoice", type="primary")

if submitted:
    # Client-side validation
    errors = []

    if not supplier_name.strip():
        errors.append("Supplier name is required")

    if not invoice_number.strip():
        errors.append("Invoice number is required")

    if gross_amount <= 0:
        errors.append("Gross amount must be greater than 0")

    if not project_id:
        errors.append("Project selection is required")

    if not paying_entity_raw.strip() and paying_entity_id is None:
        errors.append("Either entity name or linked entity must be provided")

    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    # Prepare payload
    payload = {
        "supplier_name_raw": supplier_name.strip(),
        "invoice_number": invoice_number.strip(),
        "gross_amount": gross_amount,
        "invoice_date": invoice_date.isoformat(),
        "project_id": project_options[project_id],
        "vat_amount": vat_amount if vat_amount > 0 else None,
        "currency": currency,
    }

    # Add optional fields
    if paying_entity_raw.strip():
        payload["paying_entity_raw"] = paying_entity_raw.strip()

    if paying_entity_id is not None:
        payload["paying_entity_id"] = entity_options[paying_entity_id]

    if net_amount > 0:
        payload["net_amount"] = net_amount
    elif vat_amount > 0:
        # Auto-calculate net if not provided but VAT is
        payload["net_amount"] = gross_amount - vat_amount

    if due_date:
        payload["due_date"] = due_date.isoformat()

    if description.strip():
        payload["description"] = description.strip()

    # Submit
    with st.spinner("Creating invoice..."):
        result = create_manual_invoice(payload)

    if result:
        invoice_id = result.get("id")
        st.success(f"✅ Invoice created successfully! ID: #{invoice_id}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Create Another Invoice", type="secondary"):
                st.rerun()
        with col2:
            if st.button("View in Invoice Register", type="primary"):
                st.switch_page("pages/2_Invoice_Register.py")
    else:
        st.error("Failed to create invoice. Please check the details and try again.")