import requests
import streamlit as st
from streamlit_cookies_controller import CookieController
from config import API_BASE_URL

SESSION_COOKIE_NAME = "invoice_session_token"


def _cookie_options(
    self,
    path: str = '/',
    expires=None,
    max_age=None,
    domain=None,
    secure=None,
    same_site='strict',
    partitioned=None,
):
    options = {
        "path": path,
        "maxAge": max_age,
        "domain": domain,
        "secure": secure,
        "sameSite": same_site,
        "partitioned": partitioned,
    }
    return {k: v for k, v in options.items() if v is not None}


CookieController._CookieController__getOptions = _cookie_options


def _cookie_manager():
    return CookieController()


def set_session_cookie(token: str):
    cookie_controller = _cookie_manager()
    cookie_controller.set(SESSION_COOKIE_NAME, token, path="/")


def clear_session_cookie():
    cookie_controller = _cookie_manager()
    cookie_controller.remove(SESSION_COOKIE_NAME, path="/")


def restore_session_from_cookie():
    if "session_token" in st.session_state:
        return

    cookie_controller = _cookie_manager()
    cookie_controller.refresh()
    token = cookie_controller.get(SESSION_COOKIE_NAME)
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
        st.switch_page("pages/0_Login.py")
        st.stop()


def can(permission: str) -> bool:
    """Check if current user has the given permission."""
    return permission in st.session_state.get("permissions", [])