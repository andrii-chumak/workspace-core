from dulwich import attrs
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.db import IntegrityError

from models import SocialAccount
from .services import verify_email_verification_token, verify_google_token

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


class GoogleRegisterSerializer(serializers.Serializer):
    google_token = serializers.CharField(write_only=True)


    def validate(self, attrs):
        token = attrs["google_token"]
        payload = verify_google_token(token)

        if payload is None:
            raise serializers.ValidationError({
                "google_token: invalid or expired google token"
            })

        attrs["payload"] = payload
        return attrs

    def create(self, validated_data):
        payload = validated_data["payload"]
        email = payload["email"]
        given_name = payload.get("given_name", "")
        family_name = payload.get("family_name", "")
        provider_user_id = payload["sub"]

        user = User.objects.filter(email__iexact=email).first()

        # Якщо користувача немає
        if user is None:
            username = email.split("@")[0]
            original_username = username
            counter = 1

            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=given_name,
                last_name=family_name,
            )

            user.set_unusable_password()
            user.save(update_fields=["password"])


        # Якщо Google вже прив'язаний
        social_account = SocialAccount.objects.filter(
            provider=SocialAccount.Provider.GOOGLE,
            provider_user_id=provider_user_id,
        ).first()

        if social_account:
            raise serializers.ValidationError({
                "action": "login",
                "detail": "Google account already linked."
            })

        # Якщо користувач є, але Google ще не прив'язаний
        try:
            SocialAccount.objects.create(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
                provider_user_id=provider_user_id,
            )
        except IntegrityError:
            raise serializers.ValidationError({
                "action": "login",
                "detail": "Google account already linked."
            })

        return user
