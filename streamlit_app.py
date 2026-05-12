from pathlib import Path
import streamlit as st

from utils.auth import restore_session_from_cookie, set_session_cookie, clear_session_cookie
from auth.login import render_login
from auth.set_password import render_set_password
from views.dashboard import render_dashboard
from views.invoices import render_invoice_register
from views.credit_notes import render_credit_notes
from views.users import render_users

st.set_page_config(
    page_title="Invoice Tracking",
    page_icon="🧾",
    layout="wide",
)

# Write pending session cookie before any cookie-reading widget is instantiated
if "_pending_cookie_write" in st.session_state:
    set_session_cookie(st.session_state.pop("_pending_cookie_write"))

# Restore session from cookie if not already in session_state
restore_session_from_cookie()

# Invite / password-reset flow — token arrives as a URL query param
token = st.query_params.get("token")
if token:
    render_set_password(token)
    st.stop()

# Auth gate
if "session_token" not in st.session_state:
    render_login()
    st.stop()

# ── Authenticated app ──────────────────────────────────────────────────────────
user = st.session_state.get("user", {})
role = user.get("role", "")
user_name = user.get("full_name", "User")

logo_path = Path(__file__).parent / "assets" / "valpre_logo.png"

with st.sidebar:
    if logo_path.exists():
        st.image(str(logo_path), width=160)
    st.markdown(f"**{user_name}**")
    st.caption(role.capitalize())
    st.markdown("---")

    nav_options = ["Dashboard", "Invoice Register", "Credit Notes"]
    if role == "admin":
        nav_options.append("Users")

    page = st.sidebar.radio("Navigation", nav_options, label_visibility="collapsed")

    st.markdown("---")
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        clear_session_cookie()
        st.rerun()

# ── Route ──────────────────────────────────────────────────────────────────────
if page == "Dashboard":
    render_dashboard()
elif page == "Invoice Register":
    render_invoice_register()
elif page == "Credit Notes":
    render_credit_notes()
elif page == "Users":
    render_users()
