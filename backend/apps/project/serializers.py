from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import serializers

from apps.workspace.models import Workspace, WorkspaceMember

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
    workspace_id = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(),
        source="workspace",
    )
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

    def validate_workspace_id(self, workspace):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        membership = WorkspaceMember.objects.filter(
            workspace=workspace,
            user=request.user,
        ).first()
        if membership is None:
            raise serializers.ValidationError("You are not a member of this workspace.")
        if membership.role == WorkspaceMember.Role.MEMBER:
            raise serializers.ValidationError("Only workspace owners and admins can create projects.")
        if workspace.status == Workspace.Status.ARCHIVED:
            raise serializers.ValidationError("Archived workspace cannot be modified.")
        return workspace

    def validate(self, attrs):
        if self.instance is not None and "workspace" in attrs:
            if attrs["workspace"].id != self.instance.workspace_id:
                raise serializers.ValidationError({
                    "workspace_id": "Project workspace cannot be changed."
                })
        return attrs

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
