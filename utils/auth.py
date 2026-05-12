import datetime
import requests
import streamlit as st
from streamlit_cookies_controller import CookieController
from config import API_BASE_URL

SESSION_COOKIE_NAME = "invoice_session_token"
_COOKIE_EXPIRY_DAYS = 30


def _cookie_manager() -> CookieController:
    # Reuse a single instance per session to avoid rendering duplicate
    # components with the same key in the same script run.
    if "_cm" not in st.session_state:
        # After st.session_state.clear() (logout), Streamlit preserves
        # widget-owned keys like 'cookies' even though _cm is gone.
        # CookieController.__init__ would then try to manually write to
        # session_state['cookies'], which Streamlit forbids after a widget
        # with that key has been instantiated. Deleting it first forces
        # __init__ into the clean render path instead.
        if "cookies" in st.session_state:
            del st.session_state["cookies"]
        st.session_state["_cm"] = CookieController()
    return st.session_state["_cm"]


def set_session_cookie(token: str):
    cm = _cookie_manager()
    cm.set(
        SESSION_COOKIE_NAME,
        token,
        path="/",
        expires=datetime.datetime.now() + datetime.timedelta(days=_COOKIE_EXPIRY_DAYS),
    )


def clear_session_cookie():
    cm = _cookie_manager()
    cm.remove(SESSION_COOKIE_NAME, path="/")


def restore_session_from_cookie():
    if "session_token" in st.session_state:
        return

    cm = _cookie_manager()
    # Do NOT call cm.refresh() here — it renders a second component with the
    # same key in the same script run, causing a DuplicateWidgetID error and
    # silently wiping cookie data on Chrome.
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