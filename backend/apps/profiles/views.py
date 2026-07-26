from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model

from .serializers import UserProfileSerializer, ConfirmPasswordChangeSerializer
from .services import (
    generate_password_change_token,
    verify_password_change_token,
    send_password_change_email,
)

User = get_user_model()


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class RequestPasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        token = generate_password_change_token(user.id)
        send_password_change_email(user.email, token)

        return Response(
            {"detail": "Verification code sent to your email address."},
            status=status.HTTP_200_OK,
        )


class ConfirmPasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmPasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        user_id = verify_password_change_token(token)

        if user_id is None or user_id != request.user.id:
            return Response(
                {"detail": "Invalid or expired confirmation token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        user.set_password(new_password)
        user.save()

        return Response(
            {"detail": "Password has been successfully changed."},
            status=status.HTTP_200_OK,
        )