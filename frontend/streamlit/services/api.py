import requests
import streamlit as st
from typing import Any
from config import API_BASE_URL


TIMEOUT = 10
EXTRACTION_TIMEOUT = 120  # Azure OCR can take up to 2 minutes


def get(path: str) -> Any:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
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
        if files:
            response = requests.post(
                f"{API_BASE_URL}{path}",
                files=files,
                data=data,
                timeout=timeout
            )
        else:
            response = requests.post(
                f"{API_BASE_URL}{path}",
                json=data,
                timeout=timeout
            )
        response.raise_for_status()
        return response.json()
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
        response = requests.patch(
            f"{API_BASE_URL}{path}",
            json=data,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None


def delete(path: str) -> Any:
    try:
        response = requests.delete(f"{API_BASE_URL}{path}", timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None