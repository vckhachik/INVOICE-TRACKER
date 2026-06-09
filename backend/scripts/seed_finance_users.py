"""
One-time script to seed the two finance users into the Railway production database.

Run from the backend folder:
    cd backend
    export DATABASE_URL="<railway-DATABASE_PUBLIC_URL>"
    python scripts/seed_finance_users.py
    unset DATABASE_URL

DO NOT commit this file to git — it contains plain-text passwords.
"""

import sys
from datetime import datetime, timezone

sys.path.append(".")
from app.db.database import SessionLocal
from app.models.models import User
from app.core.security.passwords import hash_password
from app.core.security.password_policy import validate_password


USERS = [
    {
        "email": "snassar@valprecapital.com",
        "full_name": "Salam Nassar",
        "role": "finance",
        "password": "ValpreInvoices.SN2026",
    },
    {
        "email": "arizk@valprecapital.com",
        "full_name": "Amin Rizk",
        "role": "finance",
        "password": "ValpreInvoices.AR2026",
    },
]


def main():
    db = SessionLocal()
    try:
        for u in USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"⚠️  Already exists, skipping: {u['email']}")
                continue

            try:
                validate_password(u["password"], user_context=[u["email"], u["full_name"]])
            except ValueError as e:
                print(f"❌ Password validation failed for {u['email']}: {e}")
                continue

            user = User(
                email=u["email"],
                full_name=u["full_name"],
                role=u["role"],
                password_hash=hash_password(u["password"]),
                is_active=True,
                must_reset_password=True,
                password_set_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.flush()
            print(f"✅ Created: {user.email} (role={user.role}, id={user.id})")

        db.commit()
        print("\nDone. Remind users to change their password on first login.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
