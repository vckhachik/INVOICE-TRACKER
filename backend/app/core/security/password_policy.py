from zxcvbn import zxcvbn

MIN_LENGTH = 12
MIN_SCORE = 3


def validate_password(password: str, user_context: list = None) -> None:
    if not password:
        raise ValueError("Password cannot be empty.")
    if len(password) < MIN_LENGTH:
        raise ValueError(f"Password must be at least {MIN_LENGTH} characters.")
    if not any(c.isalpha() for c in password):
        raise ValueError("Password must contain at least one letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number.")

    result = zxcvbn(password, user_inputs=user_context or [])
    if result["score"] < MIN_SCORE:
        feedback = result["feedback"]["warning"] or "Password is too easily guessed. Try a longer passphrase."
        raise ValueError(f"Weak password: {feedback}")