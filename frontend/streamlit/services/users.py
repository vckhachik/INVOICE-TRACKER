from .api import get, post, patch


def fetch_users():
    return get("/users/")


def invite_user(email: str, full_name: str, role: str):
    return post("/users/", {"email": email, "full_name": full_name, "role": role})


def update_user(user_id: int, full_name: str = None, role: str = None):
    data = {}
    if full_name is not None:
        data["full_name"] = full_name
    if role is not None:
        data["role"] = role
    return patch(f"/users/{user_id}", data)


def deactivate_user(user_id: int):
    return post(f"/users/{user_id}/deactivate")


def reactivate_user(user_id: int):
    return post(f"/users/{user_id}/reactivate")


def resend_invite(user_id: int):
    return post(f"/users/{user_id}/resend-invite")