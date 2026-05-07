import requests
import streamlit as st
from config import API_BASE_URL
from utils.auth import restore_session_from_cookie, set_session_cookie, clear_session_cookie

st.set_page_config(page_title="Login", page_icon="🔐", layout="centered")
restore_session_from_cookie()

# If we just logged in on a previous render, write the cookie now (before any cookie-reading widget is instantiated)
if "_pending_cookie_write" in st.session_state:
    set_session_cookie(st.session_state["_pending_cookie_write"])
    del st.session_state["_pending_cookie_write"]
    st.switch_page("app.py")

# Check if already logged in
if "session_token" in st.session_state:
    st.success("You are already logged in!")
    st.write(f"Welcome back, {st.session_state.get('user', {}).get('full_name', 'User')}")

    if st.button("Logout"):
        st.session_state.clear()
        clear_session_cookie()
        st.rerun()

    st.stop()

# Login form
st.title("Login to Invoice Tracker")

with st.form("login_form"):
    email = st.text_input("Email", placeholder="your.email@company.com")
    password = st.text_input("Password", type="password", placeholder="Enter your password")

    submitted = st.form_submit_button("Login", type="primary")

    if submitted:
        if not email or not password:
            st.error("Please enter both email and password")
        else:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/auth/login",
                    json={"email": email, "password": password},
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    token = data["session_token"]

                    # Fetch permissions BEFORE writing anything to session_state or cookie
                    permissions = []
                    try:
                        me_response = requests.get(
                            f"{API_BASE_URL}/auth/me",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10
                        )
                        if me_response.status_code == 200:
                            permissions = me_response.json().get("permissions", [])
                    except Exception:
                        pass

                    # Stage everything in session_state
                    st.session_state["session_token"] = token
                    st.session_state["user"] = data["user"]
                    st.session_state["permissions"] = permissions
                    st.session_state["_pending_cookie_write"] = token

                    # Rerun — the cookie will be written on the next render BEFORE any read happens
                    st.rerun()
                else:
                    error_data = response.json()
                    st.error(f"Login failed: {error_data.get('detail', 'Unknown error')}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to API. Is the backend running?")
            except requests.exceptions.Timeout:
                st.error("Request timed out. Please try again.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

st.markdown("---")
st.markdown("Forgot your password? Contact your administrator.")