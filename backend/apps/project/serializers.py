from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import serializers

from .models import Project, ProjectMember

User = get_user_model()


class ProjectUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "avatar_url")
        read_only_fields = fields


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = ProjectUserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user",
        write_only=True,
    )

    class Meta:
        model = ProjectMember
        fields = ("id", "user", "user_id", "role", "joined_at")
        read_only_fields = ("id", "user", "joined_at")


class ProjectSerializer(serializers.ModelSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)
    created_by = ProjectUserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "workspace_id",
            "name",
            "description",
            "methodology",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "members",
        )
        read_only_fields = ("id", "status", "created_by", "created_at", "updated_at", "members")

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({
                "name": "Project with this name already exists in this workspace."
            })

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError:
            raise serializers.ValidationError({
                "name": "Project with this name already exists in this workspace."
            })
