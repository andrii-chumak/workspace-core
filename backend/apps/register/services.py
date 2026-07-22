from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from google.oauth2 import id_token
from google.auth.transport import requests

signer = TimestampSigner(salt="email-verification")

def generate_email_verification_token(email):
    token = signer.sign(str(email))
    return token

def verify_email_verification_token(token, max_age_in_seconds=60*15):
    try :
        email = signer.unsign(token, max_age=max_age_in_seconds)
        return (email)
    except (SignatureExpired, BadSignature):
        return None

def send_verification_email(email, token):

    link = (
        f"http://localhost:8000/api/auth/verify-email/"
        f"?token={token}"
    )

    send_mail(
        subject="Email Confirmation",
        message=f"Follow the link:\n\n{link}",
        from_email=None,
        recipient_list=[email],
    )

def verify_google_token(token):
    try:
        payload = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

        payload_info = {
            "sub": payload["sub"],
            "email": payload["email"],
            "email_verified": payload.get("email_verified"),
            "given_name": payload.get("given_name", ""),
            "family_name": payload.get("family_name", ""),
        }

        if not payload.get("email_verified", False):
            return None
        
        return payload_info

    except ValueError:
        return None