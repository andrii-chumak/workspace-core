from rest_framework import serializers
from django.contrib.auth import authenticate

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required = True,
        label = "Username or Email",
        error_messages = {"blank": "Enter username or email"}
    )
    password = serializers.CharField(
        required = True,
        write_only = True,
        error_messages = {"blank": "Enter password"}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(
            request=self.context.get('request'),
            username=username,
            password=password
        )

        if not user:
            raise serializers.ValidationError(
                'Incorrect username/email or password.'
            )

        attrs['user'] = user
        return attrs