from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .services import generate_email_verification_token, verify_email_verification_token, send_verification_email, send_welcome_email



from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, CheckEmailSerializer, GoogleRegisterSerializer

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        send_welcome_email(user)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


User = get_user_model()



class CheckEmailView(APIView):
    def get(self, request):
        serializer = CheckEmailSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        exists = User.objects.filter(email__iexact=email).exists()

        if not exists:
            token = generate_email_verification_token(email)
            send_verification_email(email, token)

        return Response({
            "exists": exists,
            "available": not exists,
            })


class VerifyEmailView(APIView):
    def get(self, request):
        token = request.query_params.get("token")
        if token is None:
            return Response(
                {"detail": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = verify_email_verification_token(token)

        if email is None:
            return Response(
                {"detail": "invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return Response({
            "verified": True,
            "email": email,
            "token": token,
            "message": "Email verified successfully."
            }, status=status.HTTP_200_OK
        )

class GoogleRegisterView(APIView):
    def post(self, request):
        serializer = GoogleRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        action = serializer.action

        if action == "registered":
            send_welcome_email(user)

        refresh = RefreshToken.for_user(user)

        return Response({
            "action": action,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK if action == "login_required" else status.HTTP_201_CREATED)


