import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date
from pathlib import Path

from services.api import get
from services.balances import get_all_latest_balances, post_balance, get_balance_history
from utils.formatting import format_currency, CURRENCY_SYMBOLS
from utils.currency import build_rate_map, convert_amount, safe_float


def invoice_matches_filters(invoice, show_paid=True, approved_only=False, unrecovered_vat_only=False):
    if not show_paid and invoice.get("is_paid"):
        return False
    if approved_only and not invoice.get("is_approved_to_pay"):
        return False
    if unrecovered_vat_only and invoice.get("is_vat_recovered"):
        return False
    return True


def filter_invoices(invoices, show_paid=True, approved_only=False, unrecovered_vat_only=False):
    return [
        inv for inv in (invoices or [])
        if invoice_matches_filters(inv, show_paid=show_paid, approved_only=approved_only,
                                   unrecovered_vat_only=unrecovered_vat_only)
    ]


def normalize_invoice_amounts(invoice, display_currency, rate_map):
    converted = invoice.copy()
    invoice_currency = (invoice.get("currency") or "GBP").upper()
    converted["gross_amount"] = convert_amount(invoice.get("gross_amount"), invoice_currency, display_currency, rate_map)
    converted["vat_amount"] = convert_amount(invoice.get("vat_amount"), invoice_currency, display_currency, rate_map)
    converted["net_amount"] = convert_amount(invoice.get("net_amount"), invoice_currency, display_currency, rate_map)
    converted["currency"] = display_currency
    return converted


def aggregate_invoices(invoices):
    return {
        "count": len(invoices),
        "total": sum(safe_float(i.get("gross_amount")) for i in invoices),
        "unpaid_total": sum(safe_float(i.get("gross_amount")) for i in invoices if not i.get("is_paid")),
        "paid_total": sum(safe_float(i.get("gross_amount")) for i in invoices if i.get("is_paid")),
        "approved_to_pay_total": sum(safe_float(i.get("gross_amount")) for i in invoices if i.get("is_approved_to_pay")),
        "unrecovered_vat_total": sum(safe_float(i.get("vat_amount")) for i in invoices if not i.get("is_vat_recovered")),
    }


def build_project_rows(invoices, project_map, entity_map):
    grouped = {}
    for inv in invoices:
        grouped.setdefault(inv.get("project_id"), []).append(inv)
    rows = []
    for project_id, project_invoices in grouped.items():
        entity_grouped = {}
        for inv in project_invoices:
            entity_grouped.setdefault(inv.get("paying_entity_id"), []).append(inv)
        entity_rows = []
        for entity_id, entity_invoices in entity_grouped.items():
            t = aggregate_invoices(entity_invoices)
            entity_rows.append({
                "entity_id": entity_id, "entity": entity_map.get(entity_id, "Unassigned"),
                **{k: t[k] for k in ("count", "total", "paid_total", "unpaid_total",
                                     "approved_to_pay_total", "unrecovered_vat_total")},
            })
        t = aggregate_invoices(project_invoices)
        rows.append({
            "project_id": project_id, "project": project_map.get(project_id, "Unassigned Project"),
            **{k: t[k] for k in ("count", "total", "paid_total", "unpaid_total",
                                  "approved_to_pay_total", "unrecovered_vat_total")},
            "entities": sorted(entity_rows, key=lambda x: x.get("total", 0), reverse=True),
        })
    return sorted(rows, key=lambda x: x.get("total", 0), reverse=True)


def build_entity_rows(invoices, entity_map):
    grouped = {}
    for inv in invoices:
        grouped.setdefault(inv.get("paying_entity_id"), []).append(inv)
    rows = []
    for entity_id, entity_invoices in grouped.items():
        t = aggregate_invoices(entity_invoices)
        rows.append({
            "entity_id": entity_id, "entity": entity_map.get(entity_id, "Unassigned"),
            **{k: t[k] for k in ("count", "total", "paid_total", "unpaid_total",
                                  "approved_to_pay_total", "unrecovered_vat_total")},
        })
    return sorted(rows, key=lambda x: x.get("total", 0), reverse=True)


CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#001F54"),
    margin=dict(l=160, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#e5e7eb"), yaxis=dict(gridcolor="rgba(0,0,0,0)"),
)

COLOURS = {
    "paid": "#22c55e", "unpaid": "#f97316", "approved": "#3b82f6",
    "vat": "#ef4444", "project": "#6366f1", "entity": "#8b5cf6",
}


@st.dialog("💰 Bank Balance")
def balance_dialog(entity_id: int, entity_name: str, entity_bals: list):
    st.markdown(f"**{entity_name}**")
    st.divider()

    currency_options = ["GBP", "EUR", "USD", "CHF", "AED", "SAR", "LBP"]
    existing_names = [b.get("account_name") or b.get("currency", "Account") for b in entity_bals]
    account_options = existing_names + ["+ New account"]

    if entity_bals:
        selected_acct_label = st.selectbox("Account", account_options)
    else:
        selected_acct_label = "+ New account"

    if selected_acct_label == "+ New account":
        new_currency = st.selectbox("Currency", currency_options)
        default_acct_name = f"{entity_name} {new_currency}"
        new_acct_name = st.text_input("Account name", value=default_acct_name)
        new_amount = st.number_input("Balance amount", value=0.0, step=1000.0, format="%.2f")
        new_date = st.date_input("Balance date", value=date.today())
        new_note = st.text_input("Note (optional)", placeholder="e.g. Per bank statement 01 Jun")
    else:
        idx = existing_names.index(selected_acct_label)
        current_bal = entity_bals[idx]
        new_acct_name = selected_acct_label
        current_amount = float(current_bal.get("balance_amount", 0))
        current_currency = current_bal.get("currency", "GBP")
        curr_idx = currency_options.index(current_currency) if current_currency in currency_options else 0
        bf1, bf2 = st.columns([2, 1])
        new_amount = bf1.number_input("Balance amount", value=current_amount, step=1000.0, format="%.2f")
        new_currency = bf2.selectbox("Currency", currency_options, index=curr_idx)
        new_date = st.date_input("Balance date", value=date.today())
        new_note = st.text_input("Note (optional)", placeholder="e.g. Per bank statement 01 Jun")

    c1, c2 = st.columns(2)
    if c1.button("💾 Save", use_container_width=True, type="primary"):
        result = post_balance(entity_id, new_amount, new_currency, new_date, new_note or None, new_acct_name)
        if result:
            st.rerun()
        else:
            st.error("Failed to save.")

    if c2.button("📋 History", use_container_width=True):
        key = f"dlg_hist_{entity_id}"
        st.session_state[key] = not st.session_state.get(key, False)

    if st.session_state.get(f"dlg_hist_{entity_id}"):
        st.divider()
        history = get_balance_history(entity_id)
        if history:
            for h in history:
                h_date = h.get("balance_date", "—")
                h_curr = h.get("currency", "GBP")
                h_amt = float(h.get("balance_amount", 0))
                h_note = h.get("note") or "—"
                h_acct = h.get("account_name") or h_curr
                st.caption(f"📅 {h_date}  |  {h_acct}  |  {h_curr} {h_amt:,.2f}  |  {h_note}")
        else:
            st.caption("No history yet.")


def render_dashboard():
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

    all_invoices = get("/invoices/?limit=10000&offset=0") or []
    projects = get("/projects/") or []
    entities = get("/entities/") or []
    activity = get("/dashboard/activity") or []
    fx_rates = get("/fx/rates/") or []
    latest_balances = get_all_latest_balances()
    balance_map: dict = {}
    for b in latest_balances:
        eid = b.get("entity_id")
        if eid not in balance_map:
            balance_map[eid] = []
        balance_map[eid].append(b)

    if not fx_rates:
        st.warning("No FX rates available. Using fallback exchange rates for display only.")

    project_map = {p.get("id"): p.get("name") for p in projects if p.get("id") is not None}
    entity_map = {e.get("id"): e.get("name") for e in entities if e.get("id") is not None}

    st.subheader("Dashboard Filters")
    gcol1, gcol2, gcol3, gcol4 = st.columns(4)
    with gcol1:
        g_show_paid = st.toggle("Show paid invoices", value=True, key="g_show_paid")
    with gcol2:
        g_approved_only = st.toggle("Show only approved to pay", value=False, key="g_approved_only")
    with gcol3:
        g_unrecovered_vat_only = st.toggle("Only unrecovered VAT", value=False, key="g_unrecovered_vat_only")
    with gcol4:
        _currency_opts = sorted(CURRENCY_SYMBOLS.keys())
        display_currency = st.selectbox("Display currency", options=_currency_opts, index=_currency_opts.index("GBP"), key="display_currency")

    rate_map = build_rate_map(fx_rates)
    currency_symbol = CURRENCY_SYMBOLS.get(display_currency, display_currency + " ")

    display_all_invoices = [normalize_invoice_amounts(inv, display_currency, rate_map) for inv in all_invoices]
    global_filtered_invoices = filter_invoices(display_all_invoices, show_paid=g_show_paid,
                                               approved_only=g_approved_only, unrecovered_vat_only=g_unrecovered_vat_only)
    global_summary = aggregate_invoices(global_filtered_invoices)
    global_project_rows = build_project_rows(global_filtered_invoices, project_map, entity_map)
    global_entity_rows = build_entity_rows(global_filtered_invoices, entity_map)

    st.markdown("---")
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
            st.metric("Total Unrecovered VAT", format_currency(global_summary["unrecovered_vat_total"], currency_symbol))
    else:
        st.info("No summary data available yet.")

    st.markdown("---")
    st.subheader("Breakdown by Project and Entity")

    all_project_rows = build_project_rows(display_all_invoices, project_map, entity_map)
    if all_project_rows:
        for project in all_project_rows:
            project_name = project.get("project") or "Unassigned Project"
            project_id = project.get("project_id")
            project_key = project_id if project_id is not None else project_name
            project_invoices = [inv for inv in display_all_invoices if inv.get("project_id") == project_id]

            with st.expander(f"{project_name}", expanded=False):
                st.caption("Project View Filters")
                pcol1, pcol2, pcol3 = st.columns(3)
                with pcol1:
                    p_show_paid = st.toggle("Show paid", value=True, key=f"p_show_paid_{project_key}")
                with pcol2:
                    p_approved_only = st.toggle("Approved to pay only", value=False, key=f"p_approved_only_{project_key}")
                with pcol3:
                    p_unrecovered_vat_only = st.toggle("Unrecovered VAT only", value=False, key=f"p_unrecovered_vat_only_{project_key}")

                filtered_project_invoices = filter_invoices(project_invoices, show_paid=p_show_paid,
                                                            approved_only=p_approved_only, unrecovered_vat_only=p_unrecovered_vat_only)
                filtered_project_rows = build_project_rows(filtered_project_invoices, project_map, entity_map)
                display_project = filtered_project_rows[0] if filtered_project_rows else {
                    "count": 0, "total": 0, "paid_total": 0, "unpaid_total": 0,
                    "approved_to_pay_total": 0, "unrecovered_vat_total": 0, "entities": [],
                }

                top1, top2, top3, top4 = st.columns(4)
                with top1:
                    st.metric("Invoices", display_project.get("count", 0))
                with top2:
                    st.metric("Total Unpaid", format_currency(display_project.get("unpaid_total"), currency_symbol))
                with top3:
                    st.metric("Total Paid", format_currency(display_project.get("paid_total"), currency_symbol))
                with top4:
                    st.metric("Unrecovered VAT", format_currency(display_project.get("unrecovered_vat_total"), currency_symbol))
                st.caption(f"Project total: {format_currency(display_project.get('total'), currency_symbol)}")

                project_entities = display_project.get("entities", [])
                if project_entities:
                    hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([3, 1, 2, 2, 2, 2])
                    hc1.caption("Entity"); hc2.caption("Inv."); hc3.caption("Unpaid")
                    hc4.caption("Paid"); hc5.caption("Total"); hc6.caption("Balance")

                    for e in project_entities:
                        entity_id = e.get("entity_id")
                        entity_name = e.get("entity") or "Unassigned"
                        entity_bals = balance_map.get(entity_id, [])
                        ec1, ec2, ec3, ec4, ec5, ec6 = st.columns([3, 1, 2, 2, 2, 2])
                        ec1.markdown(f"**{entity_name}**")
                        ec2.write(str(e.get("count", 0)))
                        ec3.write(format_currency(e.get("unpaid_total"), currency_symbol))
                        ec4.write(format_currency(e.get("paid_total"), currency_symbol))
                        ec5.write(format_currency(e.get("total"), currency_symbol))
                        with ec6:
                            if entity_bals:
                                for bal in entity_bals:
                                    acct = bal.get("account_name") or bal.get("currency", "?")
                                    amt = float(bal.get("balance_amount", 0))
                                    curr = bal.get("currency", "GBP")
                                    btn_key = f"bal_{project_key}_{entity_id}_{acct}"
                                    if st.button(f"💰 {curr} {amt:,.0f}", key=btn_key, use_container_width=True, help=acct):
                                        balance_dialog(entity_id, entity_name, entity_bals)
                            else:
                                if st.button("💰 —", key=f"bal_{project_key}_{entity_id}", use_container_width=True, help="Click to add bank balance"):
                                    balance_dialog(entity_id, entity_name, [])
                else:
                    st.info("No entity breakdown available for this filtered project view yet.")

                st.markdown("##### Invoices")
                entity_filter_options = {"All entities": None}
                for e in project_entities:
                    entity_filter_options[e.get("entity") or "Unassigned"] = e.get("entity_id")
                selected_entity_label = st.selectbox(
                    "Filter by entity",
                    options=list(entity_filter_options.keys()),
                    key=f"entity_filter_{project_key}",
                )
                selected_entity_id = entity_filter_options[selected_entity_label]
                table_invoices = (
                    [inv for inv in filtered_project_invoices if inv.get("paying_entity_id") == selected_entity_id]
                    if selected_entity_id is not None
                    else filtered_project_invoices
                )
                if table_invoices:
                    invoice_rows = [
                        {
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
                        }
                        for inv in table_invoices
                    ]
                    st.dataframe(pd.DataFrame(invoice_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("No invoices match the current filters.")
    else:
        st.info("No project data yet.")

    st.markdown("---")
    st.subheader("Visual Summary")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("#### By Invoice Status")
        if all_invoices:
            fig = go.Figure(go.Bar(
                x=["Paid", "Unpaid", "Approved to Pay", "Unrecovered VAT"],
                y=[global_summary["paid_total"], global_summary["unpaid_total"],
                   global_summary["approved_to_pay_total"], global_summary["unrecovered_vat_total"]],
                marker_color=[COLOURS["paid"], COLOURS["unpaid"], COLOURS["approved"], COLOURS["vat"]],
                hovertemplate="£%{y:,.2f}<extra></extra>",
            ))
            fig.update_layout(title="Invoice Value by Status", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font=dict(family="sans-serif", size=12),
                              margin=dict(l=40, r=20, t=40, b=40), yaxis=dict(gridcolor="#e5e7eb"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No status data available yet.")

    with chart_col2:
        st.markdown("#### By Project")
        if global_project_rows:
            fig = go.Figure(go.Bar(
                x=[safe_float(i.get("total")) for i in global_project_rows],
                y=[i.get("project") or "Unassigned" for i in global_project_rows],
                orientation="h", marker_color=COLOURS["project"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(title="Invoice Value by Project", **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No project chart data yet.")

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        st.markdown("#### By Entity")
        if global_entity_rows:
            fig = go.Figure(go.Bar(
                x=[safe_float(i.get("total")) for i in global_entity_rows],
                y=[i.get("entity") or "Unassigned" for i in global_entity_rows],
                orientation="h", marker_color=COLOURS["entity"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(title="Invoice Value by Entity", **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No entity chart data yet.")

    with chart_col4:
        st.markdown("#### Unpaid by Project")
        if global_project_rows:
            fig = go.Figure(go.Bar(
                x=[safe_float(i.get("unpaid_total")) for i in global_project_rows],
                y=[i.get("project") or "Unassigned" for i in global_project_rows],
                orientation="h", marker_color=COLOURS["unpaid"],
                hovertemplate="£%{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(title="Unpaid Value by Project", **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No unpaid-by-project data yet.")

    st.markdown("---")
    st.subheader("Recent Invoice Activity")
    if activity:
        activity_rows = [
            {
                "When": item.get("created_at", ""),
                "User": item.get("actor_name", "—"),
                "Event": item.get("event_label", ""),
                "Invoice ID": item.get("invoice_id", ""),
                "Project": project_map.get(item.get("project_id"), "—" if item.get("project_id") is None else str(item.get("project_id"))),
                "Entity": entity_map.get(item.get("entity_id"), "—" if item.get("entity_id") is None else str(item.get("entity_id"))),
            }
            for item in activity
        ]
        st.dataframe(pd.DataFrame(activity_rows), width="stretch", hide_index=True)
    else:
        st.info("No recent activity yet.")
