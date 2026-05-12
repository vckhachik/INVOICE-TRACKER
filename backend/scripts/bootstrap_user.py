"""
Create a user account with a specified role (admin, finance, or partner).

Run from the backend folder:
    cd backend
    export DATABASE_URL="<railway-DATABASE_PUBLIC_URL>"
    python scripts/bootstrap_user.py
    unset DATABASE_URL

The script will prompt for email, full name, role, and password.
"""

import sys
from datetime import datetime, timezone
from getpass import getpass

sys.path.append(".")
from app.db.database import SessionLocal
from app.models.models import User
from app.core.security.passwords import hash_password
from app.core.security.password_policy import validate_password


VALID_ROLES = ["admin", "finance", "partner"]


def main():
    db = SessionLocal()
    try:
        print("\n— Create user account —")

        email = input("Email: ").strip().lower()
        if not email or "@" not in email:
            print("❌ Invalid email.")
            return

        full_name = input("Full name: ").strip()
        if not full_name:
            print("❌ Name required.")
            return

        print(f"\nValid roles: {', '.join(VALID_ROLES)}")
        role = input("Role: ").strip().lower()
        if role not in VALID_ROLES:
            print(f"❌ Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
            return

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"❌ Email already in use: {email}")
            return

        password = getpass("Temporary password: ")
        confirm_pw = getpass("Confirm password: ")
        if password != confirm_pw:
            print("❌ Passwords do not match.")
            return

        try:
            validate_password(password, user_context=[email, full_name])
        except ValueError as e:
            print(f"❌ {e}")
            return

        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
            must_reset_password=False,
            password_set_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        print(f"\n✅ User created: {user.email} (role={user.role}, id={user.id})")
        print("Share their credentials manually and remind them to change their password after first login.")

    finally:
        db.close()


if __name__ == "__main__":
    main()