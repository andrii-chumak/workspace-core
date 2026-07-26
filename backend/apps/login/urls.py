from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.register.views import GoogleAuthView
from .views import LoginAPIView

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='api_login'),
    path('login/google/', GoogleAuthView.as_view(), name='api_login_google'),
    path('token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
]