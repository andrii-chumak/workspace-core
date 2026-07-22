from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.db import IntegrityError

from .services import verify_email_verification_token

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    verification_token = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
            "verification_token",
        )

    def validate_password(self, password):
        password_validation.validate_password(password)
        return password

    def validate(self, attrs):
        token = attrs["verification_token"]

        email = verify_email_verification_token(token)

        if email is None:
            raise serializers.ValidationError({
                "verification_token": "Invalid or expired token."
            })

        attrs["verified_email"] = email

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({
                "email": "Email already exists."
            })

        if User.objects.filter(
            username__iexact=attrs["username"]
        ).exists():
            raise serializers.ValidationError({
                "username": "Username already exists."
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop("verification_token")
        email = validated_data.pop("verified_email")

        try:
            return User.objects.create_user(
                username=validated_data["username"],
                email=email,
                password=validated_data["password"],
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
            )

        except IntegrityError:
            raise serializers.ValidationError({
                "email": "Email already exists."
            })


class CheckEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()