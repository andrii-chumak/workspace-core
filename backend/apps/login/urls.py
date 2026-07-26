from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema
from apps.register.views import GoogleAuthView
from .views import LoginAPIView

PublicTokenRefreshView = extend_schema(auth=[])(TokenRefreshView)

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='api_login'),
    path('login/google/', GoogleAuthView.as_view(), name='api_login_google'),
    path('token/refresh/', PublicTokenRefreshView.as_view(), name='api_token_refresh'),
]