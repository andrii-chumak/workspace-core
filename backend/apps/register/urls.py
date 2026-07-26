from django.urls import path
from .views import RegisterView, CheckEmailView, VerifyEmailView, GoogleAuthView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register" ),
    path("check-email/", CheckEmailView.as_view(), name="check-email"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("google-auth/", GoogleAuthView.as_view(), name="google-auth"),
]