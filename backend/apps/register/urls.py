from django.urls import path
from .views import RegisterView, CheckEmailView, VerifyEmailView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register" ),
    path("check-email/", CheckEmailView.as_view(), name="check-email"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
]