import requests
import streamlit as st
from streamlit_cookies_controller import CookieController
from config import API_BASE_URL

SESSION_COOKIE_NAME = "invoice_session_token"


def _cookie_manager():
    return CookieController()


def set_session_cookie(token: str):
    cm = _cookie_manager()
    cm.set(SESSION_COOKIE_NAME, token, path="/")


def clear_session_cookie():
    cm = _cookie_manager()
    cm.remove(SESSION_COOKIE_NAME, path="/")


def restore_session_from_cookie():
    if "session_token" in st.session_state:
        return

    cm = _cookie_manager()
    try:
        cm.refresh()
    except Exception:
        return

    try:
        token = cm.get(SESSION_COOKIE_NAME)
    except (KeyError, Exception):
        return

    if not token:
        return

    try:
        response = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state["session_token"] = token
            st.session_state["user"] = data.get("user", {})
            st.session_state["permissions"] = data.get("permissions", [])
        elif response.status_code == 401:
            clear_session_cookie()
    except requests.exceptions.RequestException:
        pass


def require_login():
    restore_session_from_cookie()
    if "session_token" not in st.session_state:
        st.stop()


def can(permission: str) -> bool:
    """Check if current user has the given permission."""
    return permission in st.session_state.get("permissions", [])