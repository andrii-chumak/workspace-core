from django.urls import path
from .views import (
    UserProfileView,
    RequestPasswordChangeView,
    ConfirmPasswordChangeView,
)

urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user_profile"),
    path(
        "change-password/request/",
        RequestPasswordChangeView.as_view(),
        name="request_password_change",
    ),
    path(
        "change-password/confirm/",
        ConfirmPasswordChangeView.as_view(),
        name="confirm_password_change",
    ),
]