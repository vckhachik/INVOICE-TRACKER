import pandas as pd
import streamlit as st

from services.users import fetch_users, invite_user, update_user, deactivate_user, reactivate_user, resend_invite
from utils.auth import can


def render_users():
    if not can("manage_users"):
        st.error("Admin access required.")
        return

    st.title("👥 User Management")
    st.caption("Manage users, send invites, and control access")
    st.markdown("---")

    users = fetch_users() or []

    st.subheader("Users")
    if users:
        df_data = [
            {
                "ID": user["id"],
                "Email": user["email"],
                "Full Name": user["full_name"] or "-",
                "Role": user["role"],
                "Active": "Yes" if user["is_active"] else "No",
                "Last Login": user["last_login_at"] or "-",
                "Created": user["created_at"],
            }
            for user in users
        ]
        st.dataframe(pd.DataFrame(df_data), hide_index=True, use_container_width=True)
    else:
        st.info("No users found.")

    st.markdown("---")
    st.subheader("Invite New User")

    with st.form("invite_user_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            invite_email = st.text_input("Email", placeholder="user@company.com")
        with col2:
            invite_full_name = st.text_input("Full Name", placeholder="John Doe")
        with col3:
            invite_role = st.selectbox("Role", ["partner", "finance"])
        invite_submitted = st.form_submit_button("Send Invite", type="primary")

    if invite_submitted:
        if not invite_email or not invite_full_name:
            st.error("Please fill in all fields.")
        else:
            result = invite_user(invite_email, invite_full_name, invite_role)
            if result:
                st.success("User invited successfully!")
                st.info("Check your backend terminal for the invite link, then send it to the user manually.")
                st.rerun()
            else:
                st.error("Failed to invite user.")

    if not users:
        return

    st.markdown("---")
    st.subheader("User Actions")

    current_user_id = st.session_state.get("user", {}).get("id")

    for user in users:
        user_id = user["id"]
        user_email = user["email"]
        user_full_name = user["full_name"] or user_email
        user_role = user["role"]
        user_active = user["is_active"]

        with st.expander(f"{user_full_name} ({user_email}) - {user_role}"):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("Resend Invite", key=f"resend_{user_id}"):
                    result = resend_invite(user_id)
                    if result:
                        st.success("Invite resent!")
                        st.info("Check your backend terminal for the new invite link.")
                    else:
                        st.error("Failed to resend invite.")

            with col2:
                if user_id != current_user_id:
                    if user_active:
                        confirm_deactivate = st.checkbox("Confirm deactivation", key=f"confirm_deactivate_{user_id}")
                        if st.button("Deactivate", key=f"deactivate_{user_id}"):
                            if confirm_deactivate:
                                result = deactivate_user(user_id)
                                if result:
                                    st.success("User deactivated!")
                                    st.rerun()
                                else:
                                    st.error("Failed to deactivate user.")
                            else:
                                st.warning("Please confirm deactivation.")
                    else:
                        if st.button("Reactivate", key=f"reactivate_{user_id}"):
                            result = reactivate_user(user_id)
                            if result:
                                st.success("User reactivated!")
                                st.rerun()
                            else:
                                st.error("Failed to reactivate user.")
                else:
                    st.info("Cannot modify your own account.")

            with col3:
                if user_id != current_user_id:
                    new_role = st.selectbox(
                        "Change Role", ["partner", "finance"],
                        index=0 if user_role == "partner" else 1,
                        key=f"role_{user_id}",
                    )
                    confirm_role_change = st.checkbox(f"Confirm change to {new_role}", key=f"confirm_role_{user_id}")
                    if st.button("Update Role", key=f"update_role_{user_id}"):
                        if confirm_role_change:
                            result = update_user(user_id, role=new_role)
                            if result:
                                st.success("Role updated!")
                                st.rerun()
                            else:
                                st.error("Failed to update role.")
                        else:
                            st.warning("Please confirm role change.")
                else:
                    st.info("Cannot change your own role.")
