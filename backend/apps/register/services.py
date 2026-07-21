from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail

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
        f"http://localhost:8000/auth/verify-email/"
        f"?token={token}"
    )

    send_mail(
        subject="Email Confirmation",
        message=f"Follow the link:\n\n{link}",
        from_email=None,
        recipient_list=[email],
    )
