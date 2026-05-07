import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from services.api import get
from utils.formatting import format_currency, CURRENCY_SYMBOLS
from utils.auth import require_login

require_login()

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
# ----------------------------
# Header (Logo + Title)
# ----------------------------

logo_path = Path(__file__).resolve().parents[1] / "assets" / "valpre_logo.png"

if logo_path.exists():
    st.markdown("<div style='margin-top: 10px; margin-bottom: 8px;'></div>", unsafe_allow_html=True)
    st.image(str(logo_path), width=200)
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

st.markdown(
    """
    <div style="margin-left: 12px; margin-top: 0px;">
        <h1 style="margin-bottom: 0;">Dashboard</h1>
        <p style="margin-top: 4px; color: grey;">
            Portfolio-wide invoice tracking, approvals, and VAT overview
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

top_col1, top_col2 = st.columns([1, 5])
with top_col1:
    if st.button("🔄 Refresh"):
        st.rerun()


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def invoice_matches_filters(
    invoice,
    show_paid=True,
    approved_only=False,
    unrecovered_vat_only=False,
):
    if not show_paid and invoice.get("is_paid"):
        return False

    if approved_only and not invoice.get("is_approved_to_pay"):
        return False

    if unrecovered_vat_only and invoice.get("is_vat_recovered"):
        return False

    return True


def filter_invoices(
    invoices,
    show_paid=True,
    approved_only=False,
    unrecovered_vat_only=False,
):
    return [
        inv
        for inv in (invoices or [])
        if invoice_matches_filters(
            inv,
            show_paid=show_paid,
            approved_only=approved_only,
            unrecovered_vat_only=unrecovered_vat_only,
        )
    ]


DEFAULT_RATE_MAP = {
    "GBP": 1.0,
    "EUR": 0.88,
    "USD": 0.79,
    "SAR": 0.21,
    "AED": 0.22,
    "CHF": 0.90,
}


def build_rate_map(rates):
    if not rates:
        return DEFAULT_RATE_MAP.copy()

    rate_map = {"GBP": 1.0}
    for rate in rates:
        currency = (rate.get("from_currency") or "").upper().strip()
        if currency:
            rate_map[currency] = safe_float(rate.get("rate"))

    for currency, value in DEFAULT_RATE_MAP.items():
        rate_map.setdefault(currency, value)

    return rate_map


def convert_amount(amount, invoice_currency, display_currency, rate_map):
    amount = safe_float(amount)
    invoice_currency = (invoice_currency or "GBP").upper()
    display_currency = (display_currency or "GBP").upper()

    if invoice_currency == display_currency:
        return amount

    if invoice_currency == "GBP":
        rate_to = rate_map.get(display_currency)
        return amount / rate_to if rate_to else amount

    if display_currency == "GBP":
        rate_from = rate_map.get(invoice_currency)
        return amount * rate_from if rate_from else amount

    rate_from = rate_map.get(invoice_currency)
    rate_to = rate_map.get(display_currency)
    if rate_from and rate_to:
        return amount * rate_from / rate_to

    return amount


def normalize_invoice_amounts(invoice, display_currency, rate_map):
    converted = invoice.copy()
    invoice_currency = (invoice.get("currency") or "GBP").upper()

    converted["gross_amount"] = convert_amount(
        invoice.get("gross_amount"),
        invoice_currency,
        display_currency,
        rate_map,
    )
    converted["vat_amount"] = convert_amount(
        invoice.get("vat_amount"),
        invoice_currency,
        display_currency,
        rate_map,
    )
    converted["net_amount"] = convert_amount(
        invoice.get("net_amount"),
        invoice_currency,
        display_currency,
        rate_map,
    )
    converted["currency"] = display_currency
    return converted


def aggregate_invoices(invoices):
    return {
        "count": len(invoices),
        "total": sum(safe_float(i.get("gross_amount")) for i in invoices),
        "unpaid_total": sum(
            safe_float(i.get("gross_amount"))
            for i in invoices
            if not i.get("is_paid")
        ),
        "paid_total": sum(
            safe_float(i.get("gross_amount"))
            for i in invoices
            if i.get("is_paid")
        ),
        "approved_to_pay_total": sum(
            safe_float(i.get("gross_amount"))
            for i in invoices
            if i.get("is_approved_to_pay")
        ),
        "unrecovered_vat_total": sum(
            safe_float(i.get("vat_amount"))
            for i in invoices
            if not i.get("is_vat_recovered")
        ),
    }


def build_project_rows(invoices, project_map, entity_map):
    grouped = {}
    for inv in invoices:
        project_id = inv.get("project_id")
        grouped.setdefault(project_id, []).append(inv)

    rows = []
    for project_id, project_invoices in grouped.items():
        entity_grouped = {}
        for inv in project_invoices:
            entity_id = inv.get("paying_entity_id")
            entity_grouped.setdefault(entity_id, []).append(inv)

        entity_rows = []
        for entity_id, entity_invoices in entity_grouped.items():
            entity_totals = aggregate_invoices(entity_invoices)
            entity_rows.append(
                {
                    "entity_id": entity_id,
                    "entity": entity_map.get(entity_id, "Unassigned"),
                    "count": entity_totals["count"],
                    "total": entity_totals["total"],
                    "paid_total": entity_totals["paid_total"],
                    "unpaid_total": entity_totals["unpaid_total"],
                    "approved_to_pay_total": entity_totals["approved_to_pay_total"],
                    "unrecovered_vat_total": entity_totals["unrecovered_vat_total"],
                }
            )

        project_totals = aggregate_invoices(project_invoices)

        rows.append(
            {
                "project_id": project_id,
                "project": project_map.get(project_id, "Unassigned Project"),
                "count": project_totals["count"],
                "total": project_totals["total"],
                "paid_total": project_totals["paid_total"],
                "unpaid_total": project_totals["unpaid_total"],
                "approved_to_pay_total": project_totals["approved_to_pay_total"],
                "unrecovered_vat_total": project_totals["unrecovered_vat_total"],
                "entities": sorted(
                    entity_rows,
                    key=lambda x: x.get("total", 0),
                    reverse=True,
                ),
            }
        )

    return sorted(rows, key=lambda x: x.get("total", 0), reverse=True)


def build_entity_rows(invoices, entity_map):
    grouped = {}
    for inv in invoices:
        entity_id = inv.get("paying_entity_id")
        grouped.setdefault(entity_id, []).append(inv)

    rows = []
    for entity_id, entity_invoices in grouped.items():
        totals = aggregate_invoices(entity_invoices)
        rows.append(
            {
                "entity_id": entity_id,
                "entity": entity_map.get(entity_id, "Unassigned"),
                "count": totals["count"],
                "total": totals["total"],
                "paid_total": totals["paid_total"],
                "unpaid_total": totals["unpaid_total"],
                "approved_to_pay_total": totals["approved_to_pay_total"],
                "unrecovered_vat_total": totals["unrecovered_vat_total"],
            }
        )

    return sorted(rows, key=lambda x: x.get("total", 0), reverse=True)


# Fetch raw data
all_invoices = get("/invoices/?limit=10000&offset=0") or []
projects = get("/projects/") or []
entities = get("/entities/") or []
activity = get("/dashboard/activity/") or []
fx_rates = get("/fx/rates/") or []

if not fx_rates:
    st.warning(
        "No FX rates are available from the backend. "
        "Using fallback exchange rates for display only."
    )

project_map = {
    p.get("id"): p.get("name")
    for p in projects
    if p.get("id") is not None
}
entity_map = {
    e.get("id"): e.get("name")
    for e in entities
    if e.get("id") is not None
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#001F54"),
    margin=dict(l=160, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#e5e7eb"),
    yaxis=dict(gridcolor="rgba(0,0,0,0)"),
)

COLOURS = {
    "paid": "#22c55e",
    "unpaid": "#f97316",
    "approved": "#3b82f6",
    "vat": "#ef4444",
    "project": "#6366f1",
    "entity": "#8b5cf6",
}

# ----------------------------
# Dashboard-level filters
# ----------------------------
st.subheader("Dashboard Filters")

gcol1, gcol2, gcol3, gcol4 = st.columns(4)

with gcol1:
    g_show_paid = st.toggle(
        "Show paid invoices",
        value=True,
        key="g_show_paid",
    )

with gcol2:
    g_approved_only = st.toggle(
        "Show only approved to pay invoices",
        value=False,
        key="g_approved_only",
    )

with gcol3:
    g_unrecovered_vat_only = st.toggle(
        "Only unrecovered VAT invoices",
        value=False,
        key="g_unrecovered_vat_only",
    )

with gcol4:
    display_currency = st.selectbox(
        "Display currency",
        options=sorted(CURRENCY_SYMBOLS.keys()),
        index=0,
        key="display_currency",
    )

rate_map = build_rate_map(fx_rates)
currency_symbol = CURRENCY_SYMBOLS.get(display_currency, display_currency + " ")

display_all_invoices = [
    normalize_invoice_amounts(inv, display_currency, rate_map)
    for inv in all_invoices
]

global_filtered_invoices = filter_invoices(
    display_all_invoices,
    show_paid=g_show_paid,
    approved_only=g_approved_only,
    unrecovered_vat_only=g_unrecovered_vat_only,
)

global_summary = aggregate_invoices(global_filtered_invoices)
global_project_rows = build_project_rows(
    global_filtered_invoices,
    project_map,
    entity_map,
)
global_entity_rows = build_entity_rows(
    global_filtered_invoices,
    entity_map,
)

st.markdown("---")

# ----------------------------
# Summary KPI cards
# ----------------------------
st.subheader("Summary")

if all_invoices:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Invoices", global_summary["count"])
    with col2:
        st.metric("Total Unpaid", format_currency(global_summary["unpaid_total"], currency_symbol))
    with col3:
        st.metric("Total Paid", format_currency(global_summary["paid_total"], currency_symbol))
    with col4:
        st.metric(
            "Total Unrecovered VAT",
            format_currency(global_summary["unrecovered_vat_total"], currency_symbol),
        )
else:
    st.info("No summary data available yet.")

st.markdown("---")

# ----------------------------
# Breakdown by project and entity
# ----------------------------
st.subheader("Breakdown by Project and Entity")

all_project_rows = build_project_rows(display_all_invoices, project_map, entity_map)

if all_project_rows:
    for project in all_project_rows:
        project_name = project.get("project") or "Unassigned Project"
        project_id = project.get("project_id")
        project_key = project_id if project_id is not None else project_name

        project_invoices = [
            inv for inv in display_all_invoices
            if inv.get("project_id") == project_id
        ]

        with st.expander(f"{project_name}", expanded=False):
            st.caption("Project View Filters")

            pcol1, pcol2, pcol3 = st.columns(3)

            with pcol1:
                p_show_paid = st.toggle(
                    "Show paid invoices",
                    value=True,
                    key=f"p_show_paid_{project_key}",
                )

            with pcol2:
                p_approved_only = st.toggle(
                    "Show only approved to pay invoices",
                    value=False,
                    key=f"p_approved_only_{project_key}",
                )

            with pcol3:
                p_unrecovered_vat_only = st.toggle(
                    "Only unrecovered VAT invoices",
                    value=False,
                    key=f"p_unrecovered_vat_only_{project_key}",
                )

            filtered_project_invoices = filter_invoices(
                project_invoices,
                show_paid=p_show_paid,
                approved_only=p_approved_only,
                unrecovered_vat_only=p_unrecovered_vat_only,
            )

            filtered_project_rows = build_project_rows(
                filtered_project_invoices,
                project_map,
                entity_map,
            )

            if filtered_project_rows:
                display_project = filtered_project_rows[0]
            else:
                display_project = {
                    "count": 0,
                    "total": 0,
                    "paid_total": 0,
                    "unpaid_total": 0,
                    "approved_to_pay_total": 0,
                    "unrecovered_vat_total": 0,
                    "entities": [],
                }

            top1, top2, top3, top4 = st.columns(4)

            with top1:
                st.metric("Invoices", display_project.get("count", 0))
            with top2:
                st.metric(
                    "Total Unpaid",
                    format_currency(display_project.get("unpaid_total"), currency_symbol),
                )
            with top3:
                st.metric(
                    "Total Paid",
                    format_currency(display_project.get("paid_total"), currency_symbol),
                )
            with top4:
                st.metric(
                    "Unrecovered VAT",
                    format_currency(display_project.get("unrecovered_vat_total"), currency_symbol),
                )

            st.caption(
                f"Project total: {format_currency(display_project.get('total'), currency_symbol)}"
            )

            project_entities = display_project.get("entities", [])
            if project_entities:
                entity_rows = [
                    {
                        "Entity": e.get("entity") or "Unassigned",
                        "Invoices": e.get("count", 0),
                        "Total Unpaid": format_currency(e.get("unpaid_total"), currency_symbol),
                        "Total Paid": format_currency(e.get("paid_total"), currency_symbol),
                        "Unrecovered VAT": format_currency(
                            e.get("unrecovered_vat_total"), currency_symbol
                        ),
                        "Total": format_currency(e.get("total"), currency_symbol),
                    }
                    for e in project_entities
                ]
                st.dataframe(
                    pd.DataFrame(entity_rows),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info(
                    "No entity breakdown available for this filtered project view yet."
                )

            # --- Invoice table for this project ---
            st.markdown("##### Invoices")
            if filtered_project_invoices:
                invoice_rows = []
                for inv in filtered_project_invoices:
                    invoice_rows.append({
                        "ID": inv.get("id"),
                        "Invoice #": inv.get("invoice_number") or "—",
                        "Supplier": inv.get("supplier_name_raw") or "—",
                        "Entity": entity_map.get(inv.get("paying_entity_id"), "—"),
                        "Gross": format_currency(inv.get("gross_amount"), currency_symbol),
                        "VAT": format_currency(inv.get("vat_amount"), currency_symbol),
                        "Net": format_currency(inv.get("net_amount"), currency_symbol),
                        "Date": inv.get("invoice_date") or "—",
                        "Due": inv.get("due_date") or "—",
                        "Paid": "✅" if inv.get("is_paid") else "❌",
                        "Approved": "✅" if inv.get("is_approved_to_pay") else "❌",
                        "VAT Rec.": "✅" if inv.get("is_vat_recovered") else "❌",
                        "Status": inv.get("review_status") or "—",
                    })
                st.dataframe(
                    pd.DataFrame(invoice_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No invoices match the current filters.")
else:
    st.info("No project data yet.")

st.markdown("---")

# ----------------------------
# Visual summary
# ----------------------------
st.subheader("Visual Summary")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### By Invoice Status")

    if all_invoices:
        status_labels = [
            "Paid",
            "Unpaid",
            "Approved to Pay",
            "Unrecovered VAT",
        ]
        status_values = [
            global_summary["paid_total"],
            global_summary["unpaid_total"],
            global_summary["approved_to_pay_total"],
            global_summary["unrecovered_vat_total"],
        ]
        status_colours = [
            COLOURS["paid"],
            COLOURS["unpaid"],
            COLOURS["approved"],
            COLOURS["vat"],
        ]

        fig = go.Figure(
            go.Bar(
                x=status_labels,
                y=status_values,
                marker_color=status_colours,
                hovertemplate="£%{y:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            title="Invoice Value by Status",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="sans-serif", size=12),
            margin=dict(l=40, r=20, t=40, b=40),
            yaxis=dict(gridcolor="#e5e7eb"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No status data available yet.")

with chart_col2:
    st.markdown("#### By Project")

    if global_project_rows:
        names = [i.get("project") or "Unassigned" for i in global_project_rows]
        totals = [safe_float(i.get("total")) for i in global_project_rows]

        fig = go.Figure(
            go.Bar(
                x=totals,
                y=names,
                orientation="h",
                marker_color=COLOURS["project"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(title="Invoice Value by Project", **CHART_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No project chart data yet.")

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("#### By Entity")

    if global_entity_rows:
        names = [i.get("entity") or "Unassigned" for i in global_entity_rows]
        totals = [safe_float(i.get("total")) for i in global_entity_rows]

        fig = go.Figure(
            go.Bar(
                x=totals,
                y=names,
                orientation="h",
                marker_color=COLOURS["entity"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(title="Invoice Value by Entity", **CHART_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No entity chart data yet.")

with chart_col4:
    st.markdown("#### Unpaid by Project")

    if global_project_rows:
        names = [i.get("project") or "Unassigned" for i in global_project_rows]
        unpaid = [safe_float(i.get("unpaid_total")) for i in global_project_rows]

        fig = go.Figure(
            go.Bar(
                x=unpaid,
                y=names,
                orientation="h",
                marker_color=COLOURS["unpaid"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(title="Unpaid Value by Project", **CHART_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No unpaid-by-project data yet.")

st.markdown("---")

# ----------------------------
# Recent activity
# ----------------------------
st.subheader("Recent Invoice Activity")

if activity:
    activity_rows = []
    for item in activity:
        project_id = item.get("project_id")
        entity_id = item.get("entity_id")

        activity_rows.append(
            {
                "When": item.get("created_at", ""),
                "User": item.get("actor_name", "—"),
                "Event": item.get("event_label", ""),
                "Invoice ID": item.get("invoice_id", ""),
                "Project": project_map.get(
                    project_id,
                    "—" if project_id is None else str(project_id),
                ),
                "Entity": entity_map.get(
                    entity_id,
                    "—" if entity_id is None else str(entity_id),
                ),
            }
        )

    activity_df = pd.DataFrame(activity_rows)
    st.dataframe(activity_df, width="stretch", hide_index=True)
else:
    st.info("No recent activity yet.")