import pandas as pd
import streamlit as st

from services.api import get
from services.invoices import fetch_invoices, update_status, delete_invoice, update_invoice, get_invoice_file_url
from services.mapping import map_invoice
from services.credit_notes import delete_credit_note_link, create_credit_note_link, get_credit_note_file_url
from utils.formatting import format_currency, format_date, format_status, format_review_status
from utils.auth import can


def render_invoice_register():
    st.title("📋 Invoice Register")
    st.caption("Browse, filter, review, and update invoices")
    st.markdown("---")

    top_col1, top_col2 = st.columns([1, 5])
    with top_col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    with top_col2:
        page_size = st.selectbox("Rows", [25, 50, 100], index=1)

    # Reference data
    _projects = get("/projects/") or []
    _entities = get("/entities/") or []
    project_id_to_name = {p["id"]: p["name"] for p in _projects if p.get("id")}
    entity_id_to_name = {e["id"]: e["name"] for e in _entities if e.get("id")}
    project_options = {p["name"]: p["id"] for p in _projects if p.get("name")}
    entity_options = {"(unmapped)": None}
    entity_options.update({e["name"]: e["id"] for e in _entities if e.get("name")})

    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_paid = st.selectbox("Payment Status", ["All", "Unpaid", "Paid"])
        with col2:
            filter_approved = st.selectbox("Approval Status", ["All", "Not Approved", "Approved"])
        with col3:
            filter_vat = st.selectbox("VAT Status", ["All", "Unrecovered", "Recovered"])
        with col4:
            filter_review = st.selectbox("Review Status", ["All", "pending", "needs_review", "auto_accepted", "failed"])

    is_paid = None if filter_paid == "All" else (filter_paid == "Paid")
    is_approved = None if filter_approved == "All" else (filter_approved == "Approved")
    is_vat = None if filter_vat == "All" else (filter_vat == "Recovered")
    review_status = None if filter_review == "All" else filter_review

    invoices = fetch_invoices(
        is_paid=is_paid, is_approved_to_pay=is_approved,
        is_vat_recovered=is_vat, review_status=review_status,
        limit=page_size, offset=0,
    )

    if not invoices:
        st.info("No invoices found for the selected filters.")
        return

    st.markdown(f"**{len(invoices)} invoice(s) loaded**")

    rows = [
        {
            "ID": inv.get("id"),
            "Invoice #": inv.get("invoice_number") or "-",
            "Supplier": inv.get("supplier_name_raw") or "-",
            "Entity": inv.get("paying_entity_raw") or "-",
            "Project": project_id_to_name.get(inv.get("project_id"), inv.get("project_id") or "-"),
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
        for inv in invoices
    ]

    df = pd.DataFrame(rows)
    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(str)
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

    if not selected:
        return

    st.caption(f"{len(selected_invoices)} invoice(s) selected")
    st.markdown("### Selected Invoice")

    selected_file_url = get_invoice_file_url(selected.get("id"))
    st.link_button("📄 Open Invoice in New Tab", selected_file_url, use_container_width=False)

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

    # ── Linked credit notes ────────────────────────────────────────────────────
    if len(selected_invoices) == 1:
        st.markdown("---")
        st.markdown("### Linked Credit Notes")

        inv_id = selected.get("id")
        inv_links = get(f"/invoices/{inv_id}/credit-note-links") or []

        if inv_links:
            total_allocated = sum(
                float(lk.get("allocated_amount") or lk.get("gross_amount") or 0)
                for lk in inv_links
            )
            st.caption(f"{len(inv_links)} linked credit note(s) — total credit: {format_currency(total_allocated)}")
            for lk in inv_links:
                lk_col1, lk_col2, lk_col3, lk_col4 = st.columns([2, 2, 2, 1])
                with lk_col1:
                    st.write(f"CN #{lk.get('credit_note_id')} — {lk.get('credit_number') or '-'}")
                with lk_col2:
                    st.write(lk.get("supplier_name_raw") or "-")
                with lk_col3:
                    alloc = lk.get("allocated_amount")
                    gross = lk.get("gross_amount")
                    st.write(f"Credit: {format_currency(alloc if alloc is not None else gross)}")
                with lk_col4:
                    if lk.get("file_id"):
                        st.link_button("📄", get_credit_note_file_url(lk.get("credit_note_id")), use_container_width=True)
                if can("edit_invoice") and st.button("Unlink", key=f"inv_unlink_{lk.get('link_id')}"):
                    result = delete_credit_note_link(lk.get("credit_note_id"), lk.get("link_id"))
                    if result is not None:
                        st.success("Unlinked.")
                        st.rerun()
                    else:
                        st.error("Failed to unlink.")
        else:
            st.info("No credit notes linked to this invoice.")

    st.markdown("---")
    st.markdown("### Update Status")

    form_key = f"status_form_{selected.get('id')}"
    with st.form(form_key):
        col1, col2, col3 = st.columns(3)
        status_options = ["Keep current", "Set to Yes", "Set to No"]

        with col1:
            if can("toggle_paid"):
                paid_action = st.selectbox("Paid", status_options, index=0)
            else:
                st.write("**Paid:** (No permission)")
                paid_action = "Keep current"
        with col2:
            if can("approve_to_pay"):
                approved_action = st.selectbox("Approved to Pay", status_options, index=0)
            else:
                st.write("**Approved to Pay:** (No permission)")
                approved_action = "Keep current"
        with col3:
            if can("toggle_vat_recovered"):
                vat_action = st.selectbox("VAT Recovered", status_options, index=0)
            else:
                st.write("**VAT Recovered:** (No permission)")
                vat_action = "Keep current"

        submit_status = st.form_submit_button("💾 Save Status Changes")

    if submit_status:
        success_count = 0
        for invoice in selected_invoices:
            new_paid = bool(invoice.get("is_paid", False)) if paid_action == "Keep current" else (paid_action == "Set to Yes")
            new_approved = bool(invoice.get("is_approved_to_pay", False)) if approved_action == "Keep current" else (approved_action == "Set to Yes")
            new_vat = bool(invoice.get("is_vat_recovered", False)) if vat_action == "Keep current" else (vat_action == "Set to Yes")
            result = update_status(invoice.get("id"), is_paid=new_paid, is_approved_to_pay=new_approved, is_vat_recovered=new_vat)
            if result:
                success_count += 1
        if success_count:
            st.success(f"Updated {success_count} invoice(s) successfully.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Manual Review, Edit, and Delete")

    if len(selected_invoices) == 1 and can("edit_invoice"):
        with st.expander("Open selected invoice for manual review / correction", expanded=False):
            edit_invoice_number = st.text_input("Invoice Number", value=selected.get("invoice_number") or "")
            edit_supplier = st.text_input("Supplier", value=selected.get("supplier_name_raw") or "")
            edit_entity = st.text_input("Entity (raw text)", value=selected.get("paying_entity_raw") or "")

            # Entity dropdown
            current_entity_id = selected.get("paying_entity_id")
            current_entity_name = entity_id_to_name.get(current_entity_id, "(unmapped)")
            entity_keys = list(entity_options.keys())
            entity_default = entity_keys.index(current_entity_name) if current_entity_name in entity_keys else 0
            edit_entity_select = st.selectbox("Link to Entity", options=entity_keys, index=entity_default)

            # Project dropdown
            current_project_id = selected.get("project_id")
            current_project_name = project_id_to_name.get(current_project_id, "")
            project_keys = list(project_options.keys())
            project_default = project_keys.index(current_project_name) if current_project_name in project_keys else 0
            edit_project_select = st.selectbox("Project", options=project_keys, index=project_default)

            date_col1, date_col2 = st.columns(2)
            with date_col1:
                edit_invoice_date = st.text_input("Invoice Date (YYYY-MM-DD)", value=str(selected.get("invoice_date") or ""))
            with date_col2:
                edit_due_date = st.text_input("Due Date (YYYY-MM-DD)", value=str(selected.get("due_date") or ""))

            st.caption("Amounts accept formats like 88900, 88,900, or £88,900")
            amount_col1, amount_col2, amount_col3 = st.columns(3)
            with amount_col1:
                edit_gross_amount = st.text_input("Gross Amount", value=str(selected.get("gross_amount") or ""))
            with amount_col2:
                edit_vat_amount = st.text_input("VAT Amount", value=str(selected.get("vat_amount") or ""))
            with amount_col3:
                edit_net_amount = st.text_input("Net Amount", value=str(selected.get("net_amount") or ""))

            REVIEW_STATUS_OPTIONS = ["pending", "needs_review", "auto_accepted", "failed"]
            current_review_status = selected.get("review_status") or "pending"
            review_status_index = REVIEW_STATUS_OPTIONS.index(current_review_status) if current_review_status in REVIEW_STATUS_OPTIONS else 0
            edit_review_status = st.selectbox("Review Status", REVIEW_STATUS_OPTIONS, index=review_status_index)

            if st.button("💾 Save Manual Changes", key=f"save_edit_{selected.get('id')}"):
                payload = {
                    "invoice_number": edit_invoice_number or None,
                    "supplier_name_raw": edit_supplier or None,
                    "paying_entity_raw": edit_entity or None,
                    "paying_entity_id": entity_options.get(edit_entity_select),
                    "project_id": project_options.get(edit_project_select),
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

    if selected_invoices and can("delete_invoice"):
        st.markdown("#### Delete Selected Invoice(s)")
        confirm_delete = st.checkbox(f"I confirm I want to delete {len(selected_invoices)} selected invoice(s)", key="confirm_delete_multiple_invoices")
        if st.button("🗑️ Delete Selected Invoice(s)", key="delete_multiple_invoices"):
            if not confirm_delete:
                st.warning("Please tick the confirmation box before deleting.")
            else:
                success_count = sum(1 for inv in selected_invoices if delete_invoice(inv.get("id")) is not None)
                if success_count:
                    st.success(f"Deleted {success_count} invoice(s) successfully.")
                    st.rerun()
    elif not can("delete_invoice"):
        st.info("Delete permission required to delete invoices.")

    st.markdown("---")
    st.markdown("### Mapping")

    if can("manage_mappings"):
        if st.button(f"🗺️ Run Mapping ({len(selected_invoices)} invoice(s))", key="map_selected"):
            results = []
            failed = []
            for inv in selected_invoices:
                result = map_invoice(inv.get("id"))
                if result:
                    results.append((inv.get("id"), result))
                else:
                    failed.append(inv.get("id"))
            for inv_id, result in results:
                entity_name = (result.get("entity") or {}).get("name", "Unknown")
                project_name = (result.get("project") or {}).get("name", "Unknown")
                st.success(
                    f"#{inv_id} → {entity_name} / {project_name} | "
                    f"{result.get('match_type') or '-'} | confidence: {result.get('confidence') or '-'}"
                )
            if failed:
                st.error(f"Mapping failed for invoice(s): {', '.join(f'#{i}' for i in failed)}")
            if results:
                st.rerun()
