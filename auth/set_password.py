import requests
import streamlit as st
from config import API_BASE_URL


def render_set_password(token: str):
    st.title("Set Your Password")

    if not token:
        st.error("Invalid or missing token. Please check your invite link.")
        if st.button("Go to Login"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    with st.form("set_password_form"):
        password = st.text_input("New Password", type="password", placeholder="Enter your new password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your new password")
        submitted = st.form_submit_button("Set Password", type="primary")

        if submitted:
            if not password:
                st.error("Please enter a password")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/auth/set-password",
                        json={"token": token, "new_password": password},
                        timeout=10,
                    )

                    if response.status_code == 200:
                        st.success("Password set successfully!")
                        st.query_params.clear()
                        st.rerun()
                    else:
                        error_data = response.json()
                        st.error(f"Error: {error_data.get('detail', 'Unknown error')}")

                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API. Is the backend running?")
                except requests.exceptions.Timeout:
                    st.error("Request timed out. Please try again.")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

    st.markdown("---")
    st.markdown("Need help? Contact your administrator.")
