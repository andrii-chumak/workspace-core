from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny

@extend_schema(auth=[])
class LoginAPIView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer