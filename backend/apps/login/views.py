from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from drf_spectacular.utils import extend_schema

@extend_schema(auth=[])
class LoginAPIView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer