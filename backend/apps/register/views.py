from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .services import generate_email_verification_token, verify_email_verification_token, send_verification_email



from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, CheckEmailSerializer

class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

