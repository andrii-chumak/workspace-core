from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()
from .models import Workspace, WorkspaceMember

class CurrentWorkspaceMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceMember
        fields = (
            "id",
            "role",
        )
        read_only_fields = fields

class WorkspaceSerializer(serializers.ModelSerializer):
    current_membership = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            "id",
            "name",
            "description",
            "status",
            "created_at",
            "current_membership",

        )
        read_only_fields = (
            "id",
            "status",
            "created_at",
            "current_membership",
        )

    def get_current_membership(self, workspace):
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return None

        membership = workspace.workspace_members.filter(
            user=request.user
        ).first()

        if membership is None:
            return None

        serializer = CurrentWorkspaceMembershipSerializer(
            membership
        )
        return serializer.data


    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user

        workspace = Workspace.objects.create(**validated_data)

        WorkspaceMember.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMember.Role.OWNER,
        )
        return workspace


class WorkspaceUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
        )
        read_only_fields = fields

class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = WorkspaceUserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = (
            "id",
            "role",
            "joined_at",
            "user",
        )
        read_only_fields = fields

class AddMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=(
            WorkspaceMember.Role.ADMIN,
            WorkspaceMember.Role.MEMBER,
        ),
         default = WorkspaceMember.Role.MEMBER,
    )

class ChangeMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=(
            WorkspaceMember.Role.ADMIN,
            WorkspaceMember.Role.MEMBER,
        )
    )

class TransferOwnershipSerializer(serializers.Serializer):
    new_owner_member_id = serializers.IntegerField()



class TransferOwnershipResponseSerializer(serializers.Serializer):
    previous_owner = WorkspaceMemberSerializer(read_only=True)
    new_owner = WorkspaceMemberSerializer(read_only=True)
