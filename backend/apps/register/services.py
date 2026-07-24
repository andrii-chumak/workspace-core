import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from google.oauth2 import id_token
from google.auth.transport import requests
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage



User = get_user_model()


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
        f"http://localhost:8000/api/v1/auth/verify-email/"
        f"?token={token}"
    )

    html = render_to_string("emails/verify_email.html", {"verification_link": link})
    message = EmailMultiAlternatives(
        subject = "Verify your email address",
        body=f"Here's your verification link:\n{link}",
        from_email = None,
        to = [email],
    )
    message.attach_alternative(html, "text/html")
    image_path = os.path.join (settings.BASE_DIR, "apps", "register", "templates", "emails", "images", "Verify_email.png")
    with open(image_path, "rb") as f:
        image = MIMEImage(f.read())

    image.add_header(
        "Content-ID",
        "<verify_image>",
    )

    image.add_header(
        "Content-Disposition",
        "inline",
        filename="verify_image.png"
    )
    message.attach(image)
    message.send()


def send_welcome_email(user):
    homepage = "http://localhost:8000"
    html = render_to_string("emails/welcome_email.html", {
        "homepage": homepage,
        "username": user.username,
    })
    message = EmailMultiAlternatives(
        subject = "Welcome to Workspace",
        body=(
            f"Hi {user.username},\n\n"
            "Welcome to Workspace!\n\n"
            "Your account has been successfully created and your email "
            "has been verified.\n\n"
            "You can now sign in and start using all Workspace features.\n\n"
            "If you did not create this account, please contact our support "
            "team immediately."
        ),
        from_email = None,
        to = [user.email]
    )

    message.attach_alternative(html, "text/html")
    image_path = os.path.join (settings.BASE_DIR, "apps", "register", "templates", "emails", "images", "Welcome_email.png")

    with open(image_path, "rb") as f:
        image = MIMEImage(f.read())

    image.add_header(
        "Content-ID",
        "<welcome_email>",
    )
    image.add_header(
        "Content-Disposition",
        "inline",
        filename="welcome_email.png"
    )
    message.attach(image)
    message.send()



def verify_google_token(token):
    try:
        payload = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

        payload_info = {
            "sub": payload["sub"],
            "email": payload["email"],
            "email_verified": payload.get("email_verified"),
            "given_name": payload.get("given_name", ""),
            "family_name": payload.get("family_name", ""),
            "picture": payload.get("picture", ""),
        }

        if not payload.get("email_verified", False):
            return None

        return payload_info

    except ValueError:
        return None


def generate_unique_username(email):
    username = email.split("@")[0]
    original = username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{original}{counter}"
        counter += 1

    return username