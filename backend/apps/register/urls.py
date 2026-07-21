from django.urls import path
from .views import RegisterView, CheckEmailView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register" ),
    path("check-email/", CheckEmailView.as_view(), name="check-email"),
]