import datetime
import streamlit as st

from services.api import get
from services.invoices import create_manual_invoice
from utils.auth import can


def render_manual_entry():
    st.title("📝 Manual Invoice Entry")
    st.caption("Create an invoice by entering details manually")

    if not can("edit_invoice"):
        st.error("You don't have permission to create invoices.")
        return

    projects = get("/projects/") or []
    entities = get("/entities/") or []

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
            project_key = st.selectbox("Project", options=list(project_options.keys()), index=0 if project_options else None)

        st.subheader("Entity Information")
        col5, col6 = st.columns(2)
        with col5:
            paying_entity_raw = st.text_input("Entity Name (Raw)", placeholder="Enter entity name as it appears on invoice")
        with col6:
            paying_entity_key = st.selectbox("Link to Existing Entity (Optional)", options=list(entity_options.keys()), index=0)

        st.subheader("Amount Information")
        col7, col8, col9 = st.columns(3)
        with col7:
            gross_amount = st.number_input("Gross Amount", min_value=0.01, step=0.01, format="%.2f")
        with col8:
            vat_amount = st.number_input("VAT Amount", min_value=0.00, step=0.01, format="%.2f", value=0.00)
        with col9:
            net_amount = st.number_input("Net Amount", min_value=0.00, step=0.01, format="%.2f", help="Auto-calculated if left blank (Gross - VAT)")

        st.subheader("Optional Details")
        col10, col11 = st.columns(2)
        with col10:
            due_date = st.date_input("Due Date (Optional)", value=None)
        with col11:
            currency = st.selectbox("Currency", options=["GBP", "EUR", "USD"], index=0)

        description = st.text_area("Description (Optional)", placeholder="Additional notes or description")
        submitted = st.form_submit_button("Create Invoice", type="primary")

    if submitted:
        errors = []
        if not supplier_name.strip():
            errors.append("Supplier name is required")
        if not invoice_number.strip():
            errors.append("Invoice number is required")
        if gross_amount <= 0:
            errors.append("Gross amount must be greater than 0")
        if not project_key:
            errors.append("Project selection is required")
        if not paying_entity_raw.strip() and entity_options.get(paying_entity_key) is None:
            errors.append("Either entity name or linked entity must be provided")

        if errors:
            for error in errors:
                st.error(error)
            return

        payload = {
            "supplier_name_raw": supplier_name.strip(),
            "invoice_number": invoice_number.strip(),
            "gross_amount": gross_amount,
            "invoice_date": invoice_date.isoformat(),
            "project_id": project_options[project_key],
            "vat_amount": vat_amount if vat_amount > 0 else None,
            "currency": currency,
        }
        if paying_entity_raw.strip():
            payload["paying_entity_raw"] = paying_entity_raw.strip()
        if entity_options.get(paying_entity_key) is not None:
            payload["paying_entity_id"] = entity_options[paying_entity_key]
        if net_amount > 0:
            payload["net_amount"] = net_amount
        elif vat_amount > 0:
            payload["net_amount"] = gross_amount - vat_amount
        if due_date:
            payload["due_date"] = due_date.isoformat()
        if description.strip():
            payload["description"] = description.strip()

        with st.spinner("Creating invoice..."):
            result = create_manual_invoice(payload)

        if result:
            st.success(f"✅ Invoice created successfully! ID: #{result.get('id')}")
            if st.button("Create Another Invoice", type="secondary"):
                st.rerun()
        else:
            st.error("Failed to create invoice. Please check the details and try again.")
