import streamlit as st

from services.invoices import upload_invoices_batch, trigger_invoice_extraction
from services.mapping import map_invoice
from utils.formatting import format_review_status
from utils.auth import require_login, can

require_login()

st.set_page_config(page_title="Upload Invoice", page_icon="📤", layout="wide")
st.title("📤 Upload Invoices")
st.caption("Upload one or more invoices, then run extraction and mapping")

st.markdown("---")

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
            file_size_kb = file.size / 1024
            st.write(
                f"- {file.name} ({file_size_kb:.1f} KB, {file.type or 'unknown type'})"
            )

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

                failed = result.get("failed", [])
                if failed:
                    with st.expander("Failed uploads"):
                        st.json(failed)

else:
    st.error("Upload permission required to upload invoices.")

uploaded_results = st.session_state.get("uploaded_batch_results", [])
extraction_results = st.session_state.get("batch_extraction_results", {})
mapping_results = st.session_state.get("batch_mapping_results", {})

if uploaded_results:
    st.markdown("---")
    st.subheader("Uploaded Invoices")

    for item in uploaded_results:
        st.write(
            f"**{item.get('file_name', '-')}** → Invoice ID: `{item.get('invoice_id', '-')}`"
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔍 Run Extraction for All"):
            success_count = 0
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, item in enumerate(uploaded_results, start=1):
                invoice_id = item.get("invoice_id")
                file_name = item.get("file_name", f"Invoice {invoice_id}")

                status_text.write(
                    f"Extracting {idx} of {len(uploaded_results)}: {file_name}"
                )

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
                file_name = item.get("file_name", f"Invoice {invoice_id}")

                status_text.write(
                    f"Mapping {idx} of {len(uploaded_results)}: {file_name}"
                )

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
        file_name = item.get("file_name", "-")

        extraction = extraction_results.get(invoice_id)
        mapping = mapping_results.get(invoice_id)

        with st.expander(f"{file_name} — Invoice ID {invoice_id}"):
            left, right = st.columns(2)

            with left:
                st.markdown("### Upload")
                st.write("**Status:** uploaded")

                st.markdown("### Extraction")
                if extraction:
                    fields = extraction.get("extracted_fields", {})
                    st.write(
                        f"**Review Status:** "
                        f"{format_review_status(extraction.get('review_status'))}"
                    )
                    st.write(f"**Supplier:** {fields.get('supplier_name_raw') or '-'}")
                    st.write(f"**Entity:** {fields.get('paying_entity_raw') or '-'}")
                    st.write(f"**Invoice #:** {fields.get('invoice_number') or '-'}")
                    st.write(
                        f"**Entity Source:** {extraction.get('entity_source') or '-'}"
                    )
                else:
                    st.write("Not extracted yet.")

            with right:
                st.markdown("### Mapping")
                if mapping:
                    entity = mapping.get("entity") or {}
                    project = mapping.get("project") or {}

                    st.write(
                        f"**Matched:** {'Yes' if mapping.get('matched') else 'No'}"
                    )
                    st.write(f"**Match Type:** {mapping.get('match_type') or '-'}")
                    st.write(f"**Confidence:** {mapping.get('confidence') or '-'}")
                    st.write(f"**Mapped Entity:** {entity.get('name') or 'No match'}")
                    st.write(
                        f"**Mapped Project:** {project.get('name') or 'No match'}"
                    )
                else:
                    st.write("Not mapped yet.")