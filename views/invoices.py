import datetime
import pandas as pd
import streamlit as st

from services.api import get
from services.invoices import (
    fetch_invoices, update_status, delete_invoice, update_invoice,
    get_invoice_file_url, upload_invoices_batch, trigger_invoice_extraction,
)
from services.mapping import map_invoice, fetch_mapping_rules, test_match, create_mapping_rule, create_project, create_entity
from services.credit_notes import delete_credit_note_link, create_credit_note_link, get_credit_note_file_url
from utils.formatting import format_currency, format_date, format_status, format_review_status
from utils.auth import can


def render_invoice_register():
    st.title("📋 Invoice Register")
    st.caption("Browse, upload, enter, and map invoices — all in one place")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Register", "📤 Upload", "➕ Manual Entry", "🗺️ Mapping"])

    with tab1:
        _render_register()

    with tab2:
        _render_upload()

    with tab3:
        _render_manual_entry()

    with tab4:
        _render_mapping()


# ── Tab 1: Register ────────────────────────────────────────────────────────────

def _render_register():
    top_col1, top_col2 = st.columns([1, 5])
    with top_col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    with top_col2:
        page_size = st.selectbox("Rows", [25, 50, 100], index=1)

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

            current_entity_id = selected.get("paying_entity_id")
            current_entity_name = entity_id_to_name.get(current_entity_id, "(unmapped)")
            entity_keys = list(entity_options.keys())
            entity_default = entity_keys.index(current_entity_name) if current_entity_name in entity_keys else 0
            edit_entity_select = st.selectbox("Link to Entity", options=entity_keys, index=entity_default)

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


# ── Tab 2: Upload ──────────────────────────────────────────────────────────────

def _render_upload():
    st.subheader("Upload Invoices")
    st.caption("Upload one or more invoices, then run extraction and mapping")

    if can("edit_invoice"):
        if "uploaded_batch_results" not in st.session_state:
            st.session_state["uploaded_batch_results"] = []
        if "batch_extraction_results" not in st.session_state:
            st.session_state["batch_extraction_results"] = {}
        if "batch_mapping_results" not in st.session_state:
            st.session_state["batch_mapping_results"] = {}

        uploaded_files = st.file_uploader(
            "Choose invoice files",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            help="Supported formats: PDF, PNG, JPG, JPEG",
        )

        if uploaded_files:
            st.markdown(f"**{len(uploaded_files)} file(s) selected**")
            for file in uploaded_files:
                st.write(f"- {file.name} ({file.size / 1024:.1f} KB, {file.type or 'unknown type'})")

            if st.button("📤 Upload Invoices", type="primary"):
                with st.spinner("Uploading invoices..."):
                    result = upload_invoices_batch(uploaded_files)
                if result:
                    st.session_state["uploaded_batch_results"] = result.get("uploaded", [])
                    st.session_state["batch_extraction_results"] = {}
                    st.session_state["batch_mapping_results"] = {}
                    uploaded_count = result.get("uploaded_count", 0)
                    failed_count = result.get("failed_count", 0)
                    if uploaded_count:
                        st.success(f"{uploaded_count} invoice(s) uploaded successfully.")
                    if failed_count:
                        st.warning(f"{failed_count} file(s) failed to upload.")
                    if result.get("failed"):
                        with st.expander("Failed uploads"):
                            st.json(result["failed"])
    else:
        st.error("Upload permission required to upload invoices.")

    uploaded_results = st.session_state.get("uploaded_batch_results", [])
    extraction_results = st.session_state.get("batch_extraction_results", {})
    mapping_results = st.session_state.get("batch_mapping_results", {})

    if not uploaded_results:
        return

    st.markdown("---")
    st.subheader("Uploaded Invoices")
    for item in uploaded_results:
        st.write(f"**{item.get('file_name', '-')}** → Invoice ID: `{item.get('invoice_id', '-')}`")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 Run Extraction for All"):
            success_count = 0
            progress_bar = st.progress(0)
            status_text = st.empty()
            for idx, item in enumerate(uploaded_results, start=1):
                invoice_id = item.get("invoice_id")
                status_text.write(f"Extracting {idx} of {len(uploaded_results)}: {item.get('file_name', f'Invoice {invoice_id}')}")
                result = trigger_invoice_extraction(invoice_id)
                if result:
                    extraction_results[invoice_id] = result
                    success_count += 1
                progress_bar.progress(idx / len(uploaded_results))
            st.session_state["batch_extraction_results"] = extraction_results
            st.success(f"Extraction completed for {success_count} invoice(s).")

    with col2:
        if st.button("🗺️ Run Mapping for All"):
            success_count = 0
            progress_bar = st.progress(0)
            status_text = st.empty()
            for idx, item in enumerate(uploaded_results, start=1):
                invoice_id = item.get("invoice_id")
                status_text.write(f"Mapping {idx} of {len(uploaded_results)}: {item.get('file_name', f'Invoice {invoice_id}')}")
                result = map_invoice(invoice_id)
                if result:
                    mapping_results[invoice_id] = result
                    success_count += 1
                progress_bar.progress(idx / len(uploaded_results))
            st.session_state["batch_mapping_results"] = mapping_results
            st.success(f"Mapping completed for {success_count} invoice(s).")

    with col3:
        if st.button("🗑️ Clear Batch"):
            st.session_state["uploaded_batch_results"] = []
            st.session_state["batch_extraction_results"] = {}
            st.session_state["batch_mapping_results"] = {}
            st.rerun()

    st.markdown("---")
    st.subheader("Batch Results")
    for item in uploaded_results:
        invoice_id = item.get("invoice_id")
        extraction = extraction_results.get(invoice_id)
        mapping = mapping_results.get(invoice_id)
        with st.expander(f"{item.get('file_name', '-')} — Invoice ID {invoice_id}"):
            left, right = st.columns(2)
            with left:
                st.markdown("**Upload**")
                st.write("Status: uploaded")
                st.markdown("**Extraction**")
                if extraction:
                    fields = extraction.get("extracted_fields", {})
                    st.write(f"Review Status: {format_review_status(extraction.get('review_status'))}")
                    st.write(f"Supplier: {fields.get('supplier_name_raw') or '-'}")
                    st.write(f"Entity: {fields.get('paying_entity_raw') or '-'}")
                    st.write(f"Invoice #: {fields.get('invoice_number') or '-'}")
                    st.write(f"Entity Source: {extraction.get('entity_source') or '-'}")
                else:
                    st.write("Not extracted yet.")
            with right:
                st.markdown("**Mapping**")
                if mapping:
                    entity = mapping.get("entity") or {}
                    project = mapping.get("project") or {}
                    st.write(f"Matched: {'Yes' if mapping.get('matched') else 'No'}")
                    st.write(f"Match Type: {mapping.get('match_type') or '-'}")
                    st.write(f"Confidence: {mapping.get('confidence') or '-'}")
                    st.write(f"Mapped Entity: {entity.get('name') or 'No match'}")
                    st.write(f"Mapped Project: {project.get('name') or 'No match'}")
                else:
                    st.write("Not mapped yet.")


# ── Tab 3: Manual Entry ────────────────────────────────────────────────────────

def _render_manual_entry():
    st.subheader("Create Invoice Manually")
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
        st.markdown("**Required Information**")
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

        st.markdown("**Entity Information**")
        col5, col6 = st.columns(2)
        with col5:
            paying_entity_raw = st.text_input("Entity Name (Raw)", placeholder="Enter entity name as it appears on invoice")
        with col6:
            paying_entity_key = st.selectbox("Link to Existing Entity (Optional)", options=list(entity_options.keys()), index=0)

        st.markdown("**Amount Information**")
        col7, col8, col9 = st.columns(3)
        with col7:
            gross_amount = st.number_input("Gross Amount", min_value=0.01, step=0.01, format="%.2f")
        with col8:
            vat_amount = st.number_input("VAT Amount", min_value=0.00, step=0.01, format="%.2f", value=0.00)
        with col9:
            net_amount = st.number_input("Net Amount", min_value=0.00, step=0.01, format="%.2f", help="Auto-calculated if left blank (Gross - VAT)")

        st.markdown("**Optional Details**")
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

        from services.invoices import create_manual_invoice
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


# ── Tab 4: Mapping ─────────────────────────────────────────────────────────────

def _render_mapping():
    from collections import defaultdict

    entities = get("/entities/") or []
    projects = get("/projects/") or []
    rules = fetch_mapping_rules() or []

    entity_options = {e.get("name"): e.get("id") for e in entities if e.get("name")}
    project_options = {p.get("name"): p.get("id") for p in projects if p.get("name")}

    tab_a, tab_b, tab_c = st.tabs(["🔍 Match Test", "📋 Mapping Rules", "🏢 Entities & Projects"])

    with tab_a:
        st.subheader("Test Entity Match")
        st.write("Enter raw text to test how the matching engine maps it to an entity and project.")
        with st.form("match_test_form"):
            raw_text = st.text_input("Raw entity name", placeholder="e.g. VC PCL1 Limited")
            run_match = st.form_submit_button("🔍 Test Match")

        if run_match:
            if not raw_text or not raw_text.strip():
                st.warning("Please enter some raw text to test.")
            else:
                with st.spinner("Matching..."):
                    result = test_match(raw_text.strip())
                if result:
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    with metric_col1:
                        st.metric("Matched", "Yes" if result.get("matched") else "No")
                    with metric_col2:
                        st.metric("Match Type", result.get("match_type") or "-")
                    with metric_col3:
                        st.metric("Confidence", result.get("confidence") or "-")
                    st.markdown("---")
                    entity = result.get("entity") or {}
                    project = result.get("project") or {}
                    detail_col1, detail_col2 = st.columns(2)
                    with detail_col1:
                        st.write(f"**Raw Text:** {result.get('raw_text') or raw_text}")
                        st.write(f"**Matched Entity:** {entity.get('name') or 'No match'}")
                        st.write(f"**Entity ID:** {entity.get('id') or '-'}")
                    with detail_col2:
                        st.write(f"**Matched Project:** {project.get('name') or 'No match'}")
                        st.write(f"**Project ID:** {project.get('id') or '-'}")
                else:
                    st.error("Match test failed.")

    with tab_b:
        st.subheader("Mapping Rules")
        if rules:
            st.markdown(f"**{len(rules)} active rule(s)**")
            for rule in rules:
                with st.container():
                    st.markdown(
                        f"**Pattern:** `{rule.get('raw_text_pattern') or '-'}`  \n"
                        f"**Entity ID:** {rule.get('mapped_entity_id') or '-'}  \n"
                        f"**Project ID:** {rule.get('mapped_project_id') or '-'}  \n"
                        f"**Priority:** {rule.get('priority', 0)}"
                    )
                    st.markdown("---")
        else:
            st.info("No mapping rules yet.")

        st.subheader("Create New Rule")
        if not entities:
            st.warning("No entities available. Seed entities first before creating rules.")
        elif not projects:
            st.warning("No projects available. Seed projects first before creating rules.")
        else:
            with st.form("create_rule_form"):
                rule_text = st.text_input("Raw text pattern", placeholder="e.g. ROC Club Holdings Ltd")
                selected_entity = st.selectbox("Map to Entity", options=list(entity_options.keys()))
                selected_project = st.selectbox("Map to Project", options=list(project_options.keys()))
                priority = st.number_input("Priority (higher = checked first)", min_value=0, value=0, step=1)
                submit_rule = st.form_submit_button("💾 Save Rule")

            if submit_rule:
                if not rule_text or not rule_text.strip():
                    st.warning("Please enter a raw text pattern.")
                else:
                    result = create_mapping_rule(
                        raw_text=rule_text.strip(),
                        entity_id=entity_options[selected_entity],
                        project_id=project_options[selected_project],
                        priority=int(priority),
                    )
                    if result:
                        st.success(f"Rule created: '{rule_text}' → {selected_entity}")
                        st.rerun()
                    else:
                        st.error("Could not create rule.")

    with tab_c:
        st.subheader("Entities & Projects")

        if can("manage_mappings"):
            col_proj, col_ent = st.columns(2)

            with col_proj:
                st.markdown("**➕ Add Project**")
                with st.form("add_project_form"):
                    new_proj_name = st.text_input("Name *", placeholder="e.g. VCUK Fund I")
                    new_proj_group = st.text_input("Group (optional)", placeholder="e.g. VCUK")
                    submit_proj = st.form_submit_button("Create Project", use_container_width=True)
                if submit_proj:
                    if not new_proj_name or not new_proj_name.strip():
                        st.warning("Project name is required.")
                    else:
                        result = create_project(
                            name=new_proj_name.strip(),
                            group_name=new_proj_group.strip() or None,
                        )
                        if result:
                            st.success(f"'{result.get('name')}' created.")
                            st.rerun()
                        else:
                            st.error("Could not create project.")

            with col_ent:
                st.markdown("**➕ Add Entity**")
                with st.form("add_entity_form"):
                    new_ent_name = st.text_input("Name *", placeholder="e.g. Valpre Capital UK Limited")
                    project_choices = ["(none)"] + sorted(project_options.keys())
                    selected_default_proj = st.selectbox("Default project (optional)", options=project_choices)
                    new_ent_aliases = st.text_input(
                        "Aliases (comma-separated)",
                        placeholder="e.g. VCUK, Valpre UK",
                    )
                    new_ent_show_as_proj = st.checkbox(
                        "Show as project",
                        help="Auto-creates a paired project with the same name (e.g. for VCUK, VCI).",
                    )
                    submit_ent = st.form_submit_button("Create Entity", use_container_width=True)
                if submit_ent:
                    if not new_ent_name or not new_ent_name.strip():
                        st.warning("Entity name is required.")
                    else:
                        aliases = (
                            [a.strip() for a in new_ent_aliases.split(",") if a.strip()]
                            if new_ent_aliases
                            else None
                        )
                        default_pid = (
                            project_options.get(selected_default_proj)
                            if selected_default_proj != "(none)"
                            else None
                        )
                        result = create_entity(
                            name=new_ent_name.strip(),
                            project_id_default=default_pid,
                            aliases=aliases,
                            show_as_project=new_ent_show_as_proj,
                        )
                        if result:
                            extra = " (paired project auto-created)" if new_ent_show_as_proj else ""
                            st.success(f"'{result.get('name')}' created.{extra}")
                            st.rerun()
                        else:
                            st.error("Could not create entity.")

            st.markdown("---")

        if not projects and not entities:
            st.info("No projects or entities found.")
            return

        project_id_to_name = {p["id"]: p["name"] for p in projects if p.get("id")}

        entities_by_project = defaultdict(list)
        unassigned = []
        for e in entities:
            pid = e.get("project_id_default")
            if pid and pid in project_id_to_name:
                entities_by_project[pid].append(e)
            else:
                unassigned.append(e)

        for project in sorted(projects, key=lambda p: p.get("name", "")):
            pid = project.get("id")
            pname = project.get("name", "-")
            project_entities = entities_by_project.get(pid, [])
            count = len(project_entities)
            with st.expander(f"**{pname}** — {count} entit{'y' if count == 1 else 'ies'}", expanded=False):
                if project_entities:
                    for e in sorted(project_entities, key=lambda x: x.get("name", "")):
                        aliases = e.get("aliases") or []
                        alias_str = f"  *(aliases: {', '.join(aliases)})*" if aliases else ""
                        show_tag = " 🏷 show_as_project" if e.get("show_as_project") else ""
                        st.write(f"• {e['name']}{alias_str}{show_tag}")
                else:
                    st.caption("No entities assigned to this project.")

        if unassigned:
            with st.expander(f"**Unassigned entities** — {len(unassigned)}", expanded=False):
                for e in sorted(unassigned, key=lambda x: x.get("name", "")):
                    st.write(f"• {e['name']}")
