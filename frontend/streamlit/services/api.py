import requests
import streamlit as st
from typing import Any
from config import API_BASE_URL
from utils.auth import clear_session_cookie


TIMEOUT = 10
EXTRACTION_TIMEOUT = 120  # Azure OCR can take up to 2 minutes


def _get_headers():
    headers = {}
    token = st.session_state.get("session_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_response(response):
    if response.status_code == 401:
        # Clear session and redirect to login
        st.session_state.pop("session_token", None)
        st.session_state.pop("user", None)
        st.session_state.pop("permissions", None)
        clear_session_cookie()
        st.switch_page("pages/0_Login.py")
        return None
    response.raise_for_status()
    return response.json()


def get(path: str) -> Any:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", headers=_get_headers(), timeout=TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Is the backend running?")
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except requests.exceptions.Timeout:
        st.error("Request timed out.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def post(path: str, data: dict = None, files=None, timeout: int = TIMEOUT) -> Any:
    try:
        headers = _get_headers()
        if files:
            # For file uploads, don't set Content-Type (let requests handle it)
            response = requests.post(
                f"{API_BASE_URL}{path}",
                files=files,
                data=data,
                headers=headers,
                timeout=timeout
            )
        else:
            headers["Content-Type"] = "application/json"
            response = requests.post(
                f"{API_BASE_URL}{path}",
                json=data,
                headers=headers,
                timeout=timeout
            )
        return _handle_response(response)
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Is the backend running?")
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except requests.exceptions.Timeout:
        st.error("Request timed out. Extraction may be taking too long.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def patch(path: str, data: dict = None) -> Any:
    try:
        headers = _get_headers()
        headers["Content-Type"] = "application/json"
        response = requests.patch(
            f"{API_BASE_URL}{path}",
            json=data,
            headers=headers,
            timeout=TIMEOUT
        )
        return _handle_response(response)
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def delete(path: str) -> Any:
    try:
        response = requests.delete(f"{API_BASE_URL}{path}", headers=_get_headers(), timeout=TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None