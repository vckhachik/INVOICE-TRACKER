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

    # After an explicit logout, st.context.cookies still reflects the cookies
    # present at WebSocket-connection time (before the browser deletes the cookie).
    # Skip restore until the user opens a fresh page/connection.
    if st.session_state.get("_logged_out"):
        return

    # st.context.cookies reads directly from the HTTP request's Cookie header —
    # synchronous and rerun-independent. CookieController.get() was unreliable
    # here because CookieController needs a React round-trip (an extra rerun) to
    # populate its internal cache, so the first call always returned None.
    token = st.context.cookies.get(SESSION_COOKIE_NAME)
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
            # Token in cookie is invalid; clear it and mark session as logged-out
            # to prevent an infinite retry loop (st.context.cookies doesn't update
            # mid-session even after the cookie is deleted).
            clear_session_cookie()
            st.session_state["_logged_out"] = True
    except requests.exceptions.RequestException:
        pass


def require_login():
    restore_session_from_cookie()
    if "session_token" not in st.session_state:
        st.stop()


def can(permission: str) -> bool:
    """Check if current user has the given permission."""
    return permission in st.session_state.get("permissions", [])