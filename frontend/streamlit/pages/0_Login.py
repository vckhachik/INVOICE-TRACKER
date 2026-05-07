import requests
import streamlit as st
from config import API_BASE_URL

st.set_page_config(page_title="Login", page_icon="🔐", layout="centered")

# Check if already logged in
if "session_token" in st.session_state:
    st.success("You are already logged in!")
    st.write(f"Welcome back, {st.session_state.get('user', {}).get('full_name', 'User')}")

    if st.button("Logout"):
        st.session_state.clear()
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
                    st.session_state["session_token"] = data["session_token"]
                    st.session_state["user"] = data["user"]
                    
                    # Fetch user permissions
                    try:
                        me_response = requests.get(
                            f"{API_BASE_URL}/auth/me",
                            headers={"Authorization": f"Bearer {data['session_token']}"},
                            timeout=10
                        )
                        if me_response.status_code == 200:
                            me_data = me_response.json()
                            st.session_state["permissions"] = me_data.get("permissions", [])
                        else:
                            st.warning("Could not load user permissions. Some features may be limited.")
                            st.session_state["permissions"] = []
                    except Exception:
                        st.warning("Could not load user permissions. Some features may be limited.")
                        st.session_state["permissions"] = []
                    
                    st.success("Login successful! Redirecting...")
                    st.switch_page("app.py")
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