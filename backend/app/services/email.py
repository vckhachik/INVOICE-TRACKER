import os
from dotenv import load_dotenv

load_dotenv()

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")
ENV = os.getenv("ENV", "development")


def _set_password_link(raw_token: str) -> str:
    return f"{APP_BASE_URL}/Set_Password?token={raw_token}"


def send_invite_email(email: str, full_name: str, raw_token: str) -> None:
    link = _set_password_link(raw_token)
    subject = "You've been invited to the Invoice Portal"
    body = (
        f"Hi {full_name},\n\n"
        f"You've been added to the Invoice Portal. "
        f"Click the link below to set your password:\n\n"
        f"{link}\n\n"
        f"This link expires in 7 days."
    )
    _send(email, subject, body)


def send_password_reset_email(email: str, full_name: str, raw_token: str) -> None:
    link = _set_password_link(raw_token)
    subject = "Invoice Portal — password reset"
    body = (
        f"Hi {full_name},\n\n"
        f"Click the link below to reset your password:\n\n"
        f"{link}\n\n"
        f"This link expires in 1 hour."
    )
    _send(email, subject, body)


def _send(to: str, subject: str, body: str) -> None:
    if ENV == "development":
        print("\n" + "=" * 60)
        print(f"[DEV EMAIL] To: {to}")
        print(f"Subject: {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n")
    else:
        raise NotImplementedError("Production email provider not yet configured")