import sys
from datetime import datetime, timezone
from getpass import getpass

sys.path.append(".")

from app.db.database import SessionLocal
from app.models.models import User
from app.core.security.passwords import hash_password
from app.core.security.password_policy import validate_password


def main():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == "admin").first()
        if existing:
            print(f"⚠️  Admin already exists: {existing.email}")
            confirm = input("Create another? (y/N): ").strip().lower()
            if confirm != "y":
                print("Cancelled.")
                return

        print("\n— Create admin account —")
        email = input("Email: ").strip().lower()
        if not email or "@" not in email:
            print("❌ Invalid email.")
            return

        full_name = input("Full name: ").strip()
        if not full_name:
            print("❌ Name required.")
            return

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"❌ Email already in use.")
            return

        password = getpass("Password: ")
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
            role="admin",
            password_hash=hash_password(password),
            is_active=True,
            must_reset_password=False,
            password_set_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()

        print(f"\n✅ Admin created: {user.email} (id={user.id})")
        print("You can now log in at /auth/login")

    finally:
        db.close()


if __name__ == "__main__":
    main()