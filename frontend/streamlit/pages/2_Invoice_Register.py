import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import quote

from services.invoices import fetch_invoices, update_status, delete_invoice, update_invoice, get_invoice_file_url
from services.mapping import map_invoice
from utils.formatting import (
    format_currency,
    format_date,
    format_status,
    format_review_status,
)

st.set_page_config(page_title="Invoice Register", page_icon="📋", layout="wide")
st.title("📋 Invoice Register")
st.caption("Browse, filter, review, and update invoices")

st.markdown("---")

top_col1, top_col2, top_col3 = st.columns([1, 1, 4])

with top_col1:
    if st.button("🔄 Refresh"):
        st.rerun()

with top_col2:
    page_size = st.selectbox("Rows", [25, 50, 100], index=1)

offset = 0

# Filters
with st.expander("🔍 Filters", expanded=True):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        filter_paid = st.selectbox("Payment Status", ["All", "Unpaid", "Paid"])

    with col2:
        filter_approved = st.selectbox("Approval Status", ["All", "Not Approved", "Approved"])

    with col3:
        filter_vat = st.selectbox("VAT Status", ["All", "Unrecovered", "Recovered"])

    with col4:
        filter_review = st.selectbox(
            "Review Status",
            ["All", "pending", "needs_review", "auto_accepted", "failed"],
        )

# Build filter params
is_paid = None if filter_paid == "All" else (filter_paid == "Paid")
is_approved = None if filter_approved == "All" else (filter_approved == "Approved")
is_vat = None if filter_vat == "All" else (filter_vat == "Recovered")
review_status = None if filter_review == "All" else filter_review

# Fetch invoices
invoices = fetch_invoices(
    is_paid=is_paid,
    is_approved_to_pay=is_approved,
    is_vat_recovered=is_vat,
    review_status=review_status,
    limit=page_size,
    offset=offset,
)

if not invoices:
    st.info("No invoices found for the selected filters.")
    st.stop()

st.markdown(f"**{len(invoices)} invoice(s) loaded**")

# Build table
rows = []
for inv in invoices:
    rows.append(
        {
            "ID": inv.get("id"),
            "Invoice #": inv.get("invoice_number") or "-",
            "Supplier": inv.get("supplier_name_raw") or "-",
            "Entity": inv.get("paying_entity_raw") or "-",
            "Project ID": inv.get("project_id") or "-",
            "Gross": format_currency(inv.get("gross_amount")),
            "VAT": format_currency(inv.get("vat_amount")),
            "Net": format_currency(inv.get("net_amount")),
            "Date": format_date(inv.get("invoice_date")),
            "Due": format_date(inv.get("due_date")),
            "Paid": format_status(inv.get("is_paid")),
            "Approved": format_status(inv.get("is_approved_to_pay")),
            "VAT Rec.": format_status(inv.get("is_vat_recovered")),
            "Review": format_review_status(inv.get("review_status")),
        }
    )

df = pd.DataFrame(rows)
for col in ["ID", "Project ID"]:
    if col in df.columns:
        df[col] = df[col].astype(str)
st.dataframe(df, width="stretch", hide_index=True)

st.markdown("---")
st.subheader("Invoice Actions")

invoice_options = {
    f"{inv.get('id')} — {inv.get('invoice_number') or 'No invoice number'} — {inv.get('supplier_name_raw') or 'Unknown supplier'}": inv
    for inv in invoices
}

selected_labels = st.multiselect("Select Invoice(s)", list(invoice_options.keys()))
selected_invoices = [invoice_options[label] for label in selected_labels]
selected = selected_invoices[0] if selected_invoices else None

if selected:
    st.caption(f"{len(selected_invoices)} invoice(s) selected")
    st.markdown("### Selected Invoice")

    selected_file_url = get_invoice_file_url(selected.get("id"))

    st.link_button(
    "📄 Open Invoice in New Tab",
    selected_file_url,
    use_container_width=False,
)


    detail_col1, detail_col2, detail_col3 = st.columns(3)

    with detail_col1:
        st.write(f"**ID:** {selected.get('id')}")
        st.write(f"**Invoice #:** {selected.get('invoice_number') or '-'}")
        st.write(f"**Supplier:** {selected.get('supplier_name_raw') or '-'}")
        st.write(f"**Entity:** {selected.get('paying_entity_raw') or '-'}")

    with detail_col2:
        st.write(f"**Gross:** {format_currency(selected.get('gross_amount'))}")
        st.write(f"**VAT:** {format_currency(selected.get('vat_amount'))}")
        st.write(f"**Net:** {format_currency(selected.get('net_amount'))}")
        st.write(f"**Review:** {format_review_status(selected.get('review_status'))}")

    with detail_col3:
        st.write(f"**Invoice Date:** {format_date(selected.get('invoice_date'))}")
        st.write(f"**Due Date:** {format_date(selected.get('due_date'))}")
        st.write(f"**Paid:** {format_status(selected.get('is_paid'))}")
        st.write(f"**Approved:** {format_status(selected.get('is_approved_to_pay'))}")


    st.markdown("---")
    st.markdown("### Update Status")

    form_key = f"status_form_{selected.get('id')}"
    with st.form(form_key):
        col1, col2, col3 = st.columns(3)
        status_options = ["Keep current", "Set to Yes", "Set to No"]

        with col1:
            paid_action = st.selectbox("Paid", status_options, index=0)

        with col2:
            approved_action = st.selectbox("Approved to Pay", status_options, index=0)

        with col3:
            vat_action = st.selectbox("VAT Recovered", status_options, index=0)

        submit_status = st.form_submit_button("💾 Save Status Changes")

    if submit_status:
        success_count = 0

        for invoice in selected_invoices:
            current_paid = bool(invoice.get("is_paid", False))
            current_approved = bool(invoice.get("is_approved_to_pay", False))
            current_vat = bool(invoice.get("is_vat_recovered", False))

            new_paid = current_paid if paid_action == "Keep current" else (paid_action == "Set to Yes")
            new_approved = current_approved if approved_action == "Keep current" else (approved_action == "Set to Yes")
            new_vat = current_vat if vat_action == "Keep current" else (vat_action == "Set to Yes")

            result = update_status(
                invoice.get("id"),
                is_paid=new_paid,
                is_approved_to_pay=new_approved,
                is_vat_recovered=new_vat,
            )
            if result:
                success_count += 1

        if success_count:
            st.success(f"Updated {success_count} invoice(s) successfully.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Manual Review, Edit, and Delete")

    if len(selected_invoices) == 1:
        with st.expander("Open selected invoice for manual review / correction", expanded=False):
            edit_invoice_number = st.text_input(
                "Invoice Number",
                value=selected.get("invoice_number") or "",
            )
            edit_supplier = st.text_input(
                "Supplier",
                value=selected.get("supplier_name_raw") or "",
            )
            edit_entity = st.text_input(
                "Entity",
                value=selected.get("paying_entity_raw") or "",
            )
            edit_entity_id = st.text_input(
                "Entity ID",
                value=str(selected.get("paying_entity_id") or ""),
            )
            edit_project_id = st.text_input(
                "Project ID",
                value=str(selected.get("project_id") or ""),
            )

            date_col1, date_col2 = st.columns(2)
            with date_col1:
                edit_invoice_date = st.text_input(
                    "Invoice Date (YYYY-MM-DD)",
                    value=str(selected.get("invoice_date") or ""),
                )
            with date_col2:
                edit_due_date = st.text_input(
                    "Due Date (YYYY-MM-DD)",
                    value=str(selected.get("due_date") or ""),
                )

            st.caption("Amounts accept formats like 88900, 88,900, or £88,900")
            amount_col1, amount_col2, amount_col3 = st.columns(3)
            with amount_col1:
                edit_gross_amount = st.text_input(
                    "Gross Amount",
                    value=str(selected.get("gross_amount") or ""),
                )
            with amount_col2:
                edit_vat_amount = st.text_input(
                    "VAT Amount",
                    value=str(selected.get("vat_amount") or ""),
                )
            with amount_col3:
                edit_net_amount = st.text_input(
                    "Net Amount",
                    value=str(selected.get("net_amount") or ""),
                )

            # Selectbox prevents invalid enum values reaching the backend
            REVIEW_STATUS_OPTIONS = ["pending", "needs_review", "auto_accepted", "failed"]
            current_review_status = selected.get("review_status") or "pending"
            review_status_index = (
                REVIEW_STATUS_OPTIONS.index(current_review_status)
                if current_review_status in REVIEW_STATUS_OPTIONS
                else 0
            )
            edit_review_status = st.selectbox(
                "Review Status",
                REVIEW_STATUS_OPTIONS,
                index=review_status_index,
            )

            if st.button("💾 Save Manual Changes", key=f"save_edit_{selected.get('id')}"):
                payload = {
                    "invoice_number": edit_invoice_number or None,
                    "supplier_name_raw": edit_supplier or None,
                    "paying_entity_raw": edit_entity or None,
                    "paying_entity_id": int(edit_entity_id) if str(edit_entity_id).strip().isdigit() else None,
                    "project_id": int(edit_project_id) if str(edit_project_id).strip().isdigit() else None,
                    "invoice_date": edit_invoice_date or None,
                    "due_date": edit_due_date or None,
                    "gross_amount": edit_gross_amount or None,
                    "vat_amount": edit_vat_amount or None,
                    "net_amount": edit_net_amount or None,
                    "review_status": edit_review_status,
                }
                result = update_invoice(selected.get("id"), payload)
                if result:
                    st.success("Invoice updated successfully.")
                    st.rerun()
    elif len(selected_invoices) > 1:
        st.info("Manual editing is available only when exactly one invoice is selected.")

    if selected_invoices:
        st.markdown("#### Delete Selected Invoice(s)")
        confirm_delete_multiple = st.checkbox(
            f"I confirm I want to delete {len(selected_invoices)} selected invoice(s)",
            key="confirm_delete_multiple_invoices",
        )

        if st.button("🗑️ Delete Selected Invoice(s)", key="delete_multiple_invoices"):
            if not confirm_delete_multiple:
                st.warning("Please tick the confirmation box before deleting the invoice(s).")
            else:
                success_count = 0

                for invoice in selected_invoices:
                    result = delete_invoice(invoice.get("id"))
                    if result is not None:
                        success_count += 1

                if success_count:
                    st.success(f"Deleted {success_count} invoice(s) successfully.")
                    st.rerun()
    else:
        st.info("Select at least one invoice to enable deletion.")

    st.markdown("---")
    st.markdown("### Mapping")

    if len(selected_invoices) == 1:
        if st.button("🗺️ Run Mapping", key=f"map_{selected.get('id')}"):
            result = map_invoice(selected.get("id"))
            if result:
                entity_name = (result.get("entity") or {}).get("name", "Unknown")
                project_name = (result.get("project") or {}).get("name", "Unknown")
                match_type = result.get("match_type") or "-"
                confidence = result.get("confidence") or "-"

                st.success(
                    f"Mapped entity: {entity_name} | Project: {project_name} | "
                    f"Match type: {match_type} | Confidence: {confidence}"
                )
                st.rerun()
    else:
        st.info("Run Mapping is available only when exactly one invoice is selected.")