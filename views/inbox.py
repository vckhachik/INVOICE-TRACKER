import pandas as pd
import streamlit as st

from services.api import get
from services.invoices import fetch_inbox_summary
from utils.currency import format_native

INBOX_QUEUES = [
    ("needs_manual_check", "Needs manual check"),
    ("unmapped", "Unmapped"),
    ("awaiting_approval", "Awaiting approval to pay"),
    ("approved_unpaid", "Approved to pay, unpaid"),
]

# Only queues expressible as a single existing Register status preset get a
# "View in Register" hand-off. "Needs manual check" (needs_review OR failed)
# and "Unmapped" (no project OR no entity) have no matching Register control
# today — those two show rows only, per design.
INBOX_QUEUE_TO_REGISTER_PRESET = {
    "awaiting_approval": "Awaiting approval",
    "approved_unpaid": "Approved, unpaid",
}


def render_inbox():
    st.title("📥 Inbox")
    st.caption("Invoices that may need a decision. Everything else is tracked in the Invoice Register.")
    st.markdown("---")

    summary = fetch_inbox_summary()
    needs_action_count = summary.get("needs_action_count", 0)
    queues = summary.get("queues", {})

    _projects = get("/projects/") or []
    _entities = get("/entities/") or []
    project_id_to_name = {p["id"]: p["name"] for p in _projects if p.get("id")}
    entity_id_to_name = {e["id"]: e["name"] for e in _entities if e.get("id")}

    st.caption(f"{needs_action_count} invoice(s) need a decision.")

    metric_cols = st.columns(4)
    for col, (queue_key, label) in zip(metric_cols, INBOX_QUEUES):
        with col:
            st.metric(label, queues.get(queue_key, {}).get("total", 0))

    for queue_key, label in INBOX_QUEUES:
        queue = queues.get(queue_key, {"total": 0, "items": []})
        total = queue.get("total", 0)
        items = queue.get("items", [])

        st.markdown("---")
        st.markdown(f"##### {label} ({total})")

        if not items:
            st.caption("Nothing here.")
            continue

        register_preset = INBOX_QUEUE_TO_REGISTER_PRESET.get(queue_key)
        if register_preset:
            if st.button(f"View in Register — {label}", key=f"inbox_view_{queue_key}"):
                st.session_state["register_status_preset"] = register_preset
                st.rerun()
            st.caption("Sets the Register's status filter — click Invoice Register in the left navigation to see it.")

        show_reason = queue_key == "needs_manual_check"
        rows = []
        for inv in items:
            row = {
                "Supplier": inv.get("supplier_name_raw") or "-",
                "Invoice #": inv.get("invoice_number") or "-",
                "Project": project_id_to_name.get(inv.get("project_id"), "(unmapped)"),
                "Entity": entity_id_to_name.get(inv.get("paying_entity_id"), "(unmapped)"),
                "Gross": format_native(inv.get("gross_amount"), inv.get("currency") or "GBP"),
            }
            if show_reason:
                row["Reason"] = inv.get("review_status") or "-"
            rows.append(row)

        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        if total > len(items):
            st.caption(f"{total - len(items)} more not shown — open the Register for the full list.")
