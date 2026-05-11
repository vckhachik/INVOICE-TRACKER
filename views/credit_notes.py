import datetime
import pandas as pd
import streamlit as st

from services.api import get
from services.credit_notes import (
    fetch_credit_notes,
    create_manual_credit_note,
    upload_credit_note,
    update_credit_note,
    update_credit_note_status,
    delete_credit_note,
    fetch_credit_note_links,
    create_credit_note_link,
    delete_credit_note_link,
    get_credit_note_file_url,
)
from utils.formatting import format_currency, format_date, format_status, format_review_status
from utils.auth import can


def render_credit_notes():
    st.title("🧾 Credit Notes")
    st.caption("Browse, manage, and link credit notes to invoices")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📋 Register", "➕ New Credit Note", "📤 Upload PDF"])

    with tab1:
        _render_register()

    with tab2:
        _render_manual_entry()

    with tab3:
        _render_upload()


def _render_register():
    top_col1, top_col2 = st.columns([1, 5])
    with top_col1:
        if st.button("🔄 Refresh", key="cn_refresh"):
            st.rerun()
    with top_col2:
        page_size = st.selectbox("Rows", [25, 50, 100], index=1, key="cn_page_size")

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
            filter_paid = st.selectbox("Payment Status", ["All", "Unpaid", "Paid"], key="cn_filter_paid")
        with col2:
            filter_approved = st.selectbox("Approval Status", ["All", "Not Approved", "Approved"], key="cn_filter_approved")
        with col3:
            filter_review = st.selectbox(
                "Review Status",
                ["All", "pending", "needs_review", "auto_accepted", "failed", "manual"],
                key="cn_filter_review",
            )
        with col4:
            filter_supplier = st.text_input("Supplier search", placeholder="e.g. Acme", key="cn_filter_supplier")

    is_paid = None if filter_paid == "All" else (filter_paid == "Paid")
    is_approved = None if filter_approved == "All" else (filter_approved == "Approved")
    review_status = None if filter_review == "All" else filter_review

    credit_notes = fetch_credit_notes(
        is_paid=is_paid,
        is_approved_to_pay=is_approved,
        supplier=filter_supplier.strip() if filter_supplier.strip() else None,
        review_status=review_status,
        limit=page_size,
        offset=0,
    )

    if not credit_notes:
        st.info("No credit notes found for the selected filters.")
        return

    st.markdown(f"**{len(credit_notes)} credit note(s) loaded**")

    rows = [
        {
            "ID": cn.get("id"),
            "Credit #": cn.get("credit_number") or "-",
            "Supplier": cn.get("supplier_name_raw") or "-",
            "Entity": cn.get("paying_entity_raw") or "-",
            "Project": project_id_to_name.get(cn.get("project_id"), cn.get("project_id") or "-"),
            "Gross": format_currency(cn.get("gross_amount")),
            "VAT": format_currency(cn.get("vat_amount")),
            "Net": format_currency(cn.get("net_amount")),
            "Date": format_date(cn.get("credit_date")),
            "Paid": format_status(cn.get("is_paid")),
            "Approved": format_status(cn.get("is_approved_to_pay")),
            "Legacy": format_status(cn.get("is_legacy")),
            "Review": format_review_status(cn.get("review_status")),
        }
        for cn in credit_notes
    ]

    df = pd.DataFrame(rows)
    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(str)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Credit Note Actions")

    cn_options = {
        f"{cn.get('id')} — {cn.get('credit_number') or 'No number'} — {cn.get('supplier_name_raw') or 'Unknown'}": cn
        for cn in credit_notes
    }

    selected_labels = st.multiselect("Select Credit Note(s)", list(cn_options.keys()), key="cn_selected")
    selected_cns = [cn_options[label] for label in selected_labels]
    selected = selected_cns[0] if selected_cns else None

    if not selected:
        return

    st.caption(f"{len(selected_cns)} credit note(s) selected")
    st.markdown("### Selected Credit Note")

    if selected.get("file_id"):
        st.link_button("📄 Open Credit Note File", get_credit_note_file_url(selected.get("id")), use_container_width=False)

    detail_col1, detail_col2, detail_col3 = st.columns(3)
    with detail_col1:
        st.write(f"**ID:** {selected.get('id')}")
        st.write(f"**Credit #:** {selected.get('credit_number') or '-'}")
        st.write(f"**Supplier:** {selected.get('supplier_name_raw') or '-'}")
        st.write(f"**Entity:** {selected.get('paying_entity_raw') or '-'}")
        st.write(f"**Project:** {project_id_to_name.get(selected.get('project_id'), '-')}")
    with detail_col2:
        st.write(f"**Gross:** {format_currency(selected.get('gross_amount'))}")
        st.write(f"**VAT:** {format_currency(selected.get('vat_amount'))}")
        st.write(f"**Net:** {format_currency(selected.get('net_amount'))}")
        st.write(f"**Currency:** {selected.get('currency') or 'GBP'}")
    with detail_col3:
        st.write(f"**Credit Date:** {format_date(selected.get('credit_date'))}")
        st.write(f"**Paid:** {format_status(selected.get('is_paid'))}")
        st.write(f"**Approved:** {format_status(selected.get('is_approved_to_pay'))}")
        st.write(f"**Legacy:** {format_status(selected.get('is_legacy'))}")
        st.write(f"**Review:** {format_review_status(selected.get('review_status'))}")

    # ── Linked invoices ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Linked Invoices")

    links = fetch_credit_note_links(selected.get("id")) or []
    if links:
        for link in links:
            link_col1, link_col2, link_col3 = st.columns([2, 2, 1])
            with link_col1:
                inv_id = link.get("invoice_id")
                st.write(f"Invoice #{inv_id}" if inv_id else "Parked (no invoice)")
            with link_col2:
                alloc = link.get("allocated_amount")
                st.write(f"Allocated: {format_currency(alloc)}" if alloc else "Full allocation")
            with link_col3:
                if can("edit_invoice") and st.button("Unlink", key=f"unlink_{link.get('id')}"):
                    result = delete_credit_note_link(selected.get("id"), link.get("id"))
                    if result is not None:
                        st.success("Unlinked.")
                        st.rerun()
                    else:
                        st.error("Failed to unlink.")
    else:
        st.info("No linked invoices. This credit note is parked.")

    if can("edit_invoice") and len(selected_cns) == 1:
        with st.expander("🔗 Link to an Invoice", expanded=False):
            with st.form(f"link_invoice_form_{selected.get('id')}"):
                invoice_id_input = st.number_input(
                    "Invoice ID",
                    min_value=1,
                    step=1,
                    help="Enter the numeric ID of the invoice to link",
                )
                alloc_amount = st.number_input(
                    "Allocated Amount (optional)",
                    min_value=0.00,
                    step=0.01,
                    format="%.2f",
                    value=0.00,
                    help="Leave 0 to treat as full credit allocation",
                )
                submit_link = st.form_submit_button("🔗 Link")
            if submit_link:
                result = create_credit_note_link(
                    credit_note_id=selected.get("id"),
                    invoice_id=int(invoice_id_input),
                    allocated_amount=alloc_amount if alloc_amount > 0 else None,
                )
                if result:
                    st.success(f"Linked to invoice #{int(invoice_id_input)}.")
                    st.rerun()
                else:
                    st.error("Failed to link. Check the invoice ID.")

    # ── Status update ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Update Status")

    form_key = f"cn_status_form_{selected.get('id')}"
    with st.form(form_key):
        status_options = ["Keep current", "Set to Yes", "Set to No"]
        col1, col2, col3 = st.columns(3)

        with col1:
            if can("toggle_paid"):
                paid_action = st.selectbox("Paid", status_options, index=0, key=f"cn_paid_{selected.get('id')}")
            else:
                st.write("**Paid:** (No permission)")
                paid_action = "Keep current"
        with col2:
            if can("approve_to_pay"):
                approved_action = st.selectbox("Approved to Pay", status_options, index=0, key=f"cn_approved_{selected.get('id')}")
            else:
                st.write("**Approved to Pay:** (No permission)")
                approved_action = "Keep current"
        with col3:
            if can("edit_invoice"):
                legacy_action = st.selectbox("Legacy", status_options, index=0, key=f"cn_legacy_{selected.get('id')}")
            else:
                st.write("**Legacy:** (No permission)")
                legacy_action = "Keep current"

        submit_status = st.form_submit_button("💾 Save Status")

    if submit_status:
        def _resolve(action, current):
            if action == "Keep current":
                return bool(current)
            return action == "Set to Yes"

        result = update_credit_note_status(
            credit_note_id=selected.get("id"),
            is_paid=_resolve(paid_action, selected.get("is_paid")),
            is_approved_to_pay=_resolve(approved_action, selected.get("is_approved_to_pay")),
            is_legacy=_resolve(legacy_action, selected.get("is_legacy")),
        )
        if result:
            st.success("Status updated.")
            st.rerun()

    # ── Manual edit ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Manual Review, Edit, and Delete")

    if len(selected_cns) == 1 and can("edit_invoice"):
        with st.expander("Open selected credit note for manual review / correction", expanded=False):
            edit_credit_number = st.text_input("Credit Number", value=selected.get("credit_number") or "")
            edit_supplier = st.text_input("Supplier", value=selected.get("supplier_name_raw") or "")
            edit_entity_raw = st.text_input("Entity (raw text)", value=selected.get("paying_entity_raw") or "")

            current_entity_id = selected.get("paying_entity_id")
            current_entity_name = entity_id_to_name.get(current_entity_id, "(unmapped)")
            entity_keys = list(entity_options.keys())
            entity_default = entity_keys.index(current_entity_name) if current_entity_name in entity_keys else 0
            edit_entity_select = st.selectbox("Link to Entity", options=entity_keys, index=entity_default, key=f"cn_edit_entity_{selected.get('id')}")

            current_project_id = selected.get("project_id")
            current_project_name = project_id_to_name.get(current_project_id, "")
            project_keys = list(project_options.keys())
            project_default = project_keys.index(current_project_name) if current_project_name in project_keys else 0
            edit_project_select = st.selectbox("Project", options=project_keys, index=project_default, key=f"cn_edit_project_{selected.get('id')}")

            edit_credit_date = st.text_input("Credit Date (YYYY-MM-DD)", value=str(selected.get("credit_date") or ""))

            st.caption("Amounts accept formats like 88900, 88,900, or £88,900")
            amount_col1, amount_col2, amount_col3 = st.columns(3)
            with amount_col1:
                edit_gross = st.text_input("Gross Amount", value=str(selected.get("gross_amount") or ""))
            with amount_col2:
                edit_vat = st.text_input("VAT Amount", value=str(selected.get("vat_amount") or ""))
            with amount_col3:
                edit_net = st.text_input("Net Amount", value=str(selected.get("net_amount") or ""))

            REVIEW_OPTIONS = ["pending", "needs_review", "auto_accepted", "failed", "manual"]
            current_review = selected.get("review_status") or "pending"
            review_idx = REVIEW_OPTIONS.index(current_review) if current_review in REVIEW_OPTIONS else 0
            edit_review = st.selectbox("Review Status", REVIEW_OPTIONS, index=review_idx, key=f"cn_edit_review_{selected.get('id')}")

            edit_currency = st.selectbox(
                "Currency",
                ["GBP", "EUR", "USD"],
                index=["GBP", "EUR", "USD"].index(selected.get("currency") or "GBP"),
                key=f"cn_edit_currency_{selected.get('id')}",
            )

            if st.button("💾 Save Changes", key=f"cn_save_edit_{selected.get('id')}"):
                payload = {
                    "credit_number": edit_credit_number or None,
                    "supplier_name_raw": edit_supplier or None,
                    "paying_entity_raw": edit_entity_raw or None,
                    "paying_entity_id": entity_options.get(edit_entity_select),
                    "project_id": project_options.get(edit_project_select),
                    "credit_date": edit_credit_date or None,
                    "gross_amount": edit_gross or None,
                    "vat_amount": edit_vat or None,
                    "net_amount": edit_net or None,
                    "review_status": edit_review,
                    "currency": edit_currency,
                }
                result = update_credit_note(selected.get("id"), payload)
                if result:
                    st.success("Credit note updated.")
                    st.rerun()
    elif len(selected_cns) > 1:
        st.info("Manual editing is available only when exactly one credit note is selected.")

    if selected_cns and can("delete_invoice"):
        st.markdown("#### Delete Selected Credit Note(s)")
        confirm_delete = st.checkbox(
            f"I confirm I want to delete {len(selected_cns)} selected credit note(s)",
            key="cn_confirm_delete",
        )
        if st.button("🗑️ Delete Selected Credit Note(s)", key="cn_delete_btn"):
            if not confirm_delete:
                st.warning("Please tick the confirmation box before deleting.")
            else:
                success_count = sum(
                    1 for cn in selected_cns
                    if delete_credit_note(cn.get("id")) is not None
                )
                if success_count:
                    st.success(f"Deleted {success_count} credit note(s).")
                    st.rerun()
    elif not can("delete_invoice"):
        st.info("Delete permission required to delete credit notes.")


def _render_manual_entry():
    st.subheader("Create Credit Note Manually")

    if not can("edit_invoice"):
        st.error("You don't have permission to create credit notes.")
        return

    _projects = get("/projects/") or []
    _entities = get("/entities/") or []
    project_options = {f"{p.get('name')} ({p.get('group_name')})": p.get("id") for p in _projects if p.get("name")}
    entity_options = {"(unmapped)": None}
    entity_options.update({e.get("name"): e.get("id") for e in _entities if e.get("name")})

    with st.form("manual_credit_note_form"):
        st.markdown("**Required**")
        col1, col2 = st.columns(2)
        with col1:
            supplier_name = st.text_input("Supplier Name", placeholder="Enter supplier name")
        with col2:
            credit_number = st.text_input("Credit Number", placeholder="e.g. CN-001")

        col3, col4 = st.columns(2)
        with col3:
            credit_date = st.date_input("Credit Date", value=datetime.date.today())
        with col4:
            project_key = st.selectbox("Project", options=list(project_options.keys()), index=0 if project_options else None)

        st.markdown("**Entity**")
        col5, col6 = st.columns(2)
        with col5:
            paying_entity_raw = st.text_input("Entity Name (Raw)", placeholder="As it appears on the document")
        with col6:
            paying_entity_key = st.selectbox("Link to Existing Entity (Optional)", options=list(entity_options.keys()), index=0)

        st.markdown("**Amounts**")
        col7, col8, col9 = st.columns(3)
        with col7:
            gross_amount = st.number_input("Gross Amount", min_value=0.01, step=0.01, format="%.2f")
        with col8:
            vat_amount = st.number_input("VAT Amount", min_value=0.00, step=0.01, format="%.2f", value=0.00)
        with col9:
            net_amount = st.number_input("Net Amount", min_value=0.00, step=0.01, format="%.2f", value=0.00, help="Auto-calculated if left blank")

        currency = st.selectbox("Currency", ["GBP", "EUR", "USD"], index=0)
        submitted = st.form_submit_button("Create Credit Note", type="primary")

    if submitted:
        errors = []
        if not supplier_name.strip():
            errors.append("Supplier name is required")
        if not credit_number.strip():
            errors.append("Credit number is required")
        if gross_amount <= 0:
            errors.append("Gross amount must be greater than 0")
        if not project_key:
            errors.append("Project selection is required")

        if errors:
            for error in errors:
                st.error(error)
            return

        payload = {
            "supplier_name_raw": supplier_name.strip(),
            "credit_number": credit_number.strip(),
            "gross_amount": gross_amount,
            "credit_date": credit_date.isoformat(),
            "project_id": project_options[project_key],
            "currency": currency,
        }
        if paying_entity_raw.strip():
            payload["paying_entity_raw"] = paying_entity_raw.strip()
        if entity_options.get(paying_entity_key) is not None:
            payload["paying_entity_id"] = entity_options[paying_entity_key]
        if vat_amount > 0:
            payload["vat_amount"] = vat_amount
        if net_amount > 0:
            payload["net_amount"] = net_amount
        elif vat_amount > 0:
            payload["net_amount"] = gross_amount - vat_amount

        with st.spinner("Creating credit note..."):
            result = create_manual_credit_note(payload)

        if result:
            st.success(f"✅ Credit note created! ID: #{result.get('id')}")
            if st.button("Create Another", type="secondary"):
                st.rerun()
        else:
            st.error("Failed to create credit note. Please check the details and try again.")


def _render_upload():
    st.subheader("Upload Credit Note PDF")
    st.caption("Creates a skeleton record with the file attached. OCR and field extraction coming in Phase D.")

    if not can("edit_invoice"):
        st.error("You don't have permission to upload credit notes.")
        return

    uploaded_file = st.file_uploader(
        "Upload PDF, PNG, or JPEG",
        type=["pdf", "png", "jpg", "jpeg"],
        key="cn_upload_file",
    )

    if uploaded_file:
        st.write(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        if st.button("📤 Upload Credit Note", type="primary"):
            with st.spinner("Uploading..."):
                result = upload_credit_note(uploaded_file)
            if result:
                st.success(f"✅ Uploaded. Credit note ID: #{result.get('id')} — go to the Register tab to fill in details.")
            else:
                st.error("Upload failed. Please try again.")
