from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.conf import settings

signer = TimestampSigner(salt="password-change-reset")

def generate_password_change_token(user_id: int) -> str:
    return signer.sign(str(user_id))


def verify_password_change_token(token: str, max_age_in_seconds: int = 60 * 15) -> int | None:
    try:
        user_id_str = signer.unsign(token, max_age=max_age_in_seconds)
        return int(user_id_str)
    except (SignatureExpired, BadSignature, ValueError):
        return None


def send_password_change_email(email: str, token: str):
    link = f"http://localhost:8000/api/v1/profile/change-password/confirm/?token={token}"

    send_mail(
        subject="Request to Change Password",
        message=f"You requested a password change. Use the token below or click the link:\n\n{token}\n\nLink: {link}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[email],
    )