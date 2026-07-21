from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password')

    def validate_password(self, password):
        password_validation.validate_password(password)
        return password

    def create(self, validated_data):
        user = User.objects.create_user(
            username = validated_data['username'],
            email = validated_data['email'],
            password=validated_data['password'],
            first_name = validated_data.get('first_name', ""),
            last_name = validated_data.get('last_name', ""),
        )
        return user
