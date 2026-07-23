from django.urls import path
from .views import RegisterView, CheckEmailView, VerifyEmailView, GoogleRegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register" ),
    path("check-email/", CheckEmailView.as_view(), name="check-email"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("google-register/", GoogleRegisterView.as_view(), name="google-register"),
]