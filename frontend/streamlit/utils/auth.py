import streamlit as st

def require_login():
    """Redirect to login if user is not authenticated."""
    if "session_token" not in st.session_state:
        st.switch_page("pages/0_Login.py")
        st.stop()

def can(permission: str) -> bool:
    """Check if current user has the given permission."""
    return permission in st.session_state.get("permissions", [])