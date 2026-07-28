from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction

User = get_user_model()

from .serializers import (
    WorkspaceSerializer,
    WorkspaceMemberSerializer,
    AddMemberSerializer,
    ChangeMemberRoleSerializer,
    TransferOwnershipSerializer,
    TransferOwnershipResponseSerializer,
)
from .models import Workspace, WorkspaceMember


def ensure_workspace_is_active(workspace):
    if workspace.status == Workspace.Status.ARCHIVED:
        raise ValidationError({
            "workspace": "Archived workspace cannot be modified."
        })


class WorkspacesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List user workspaces",
        description="Returns all workspaces where the authenticated user is a member.",
        responses={200: WorkspaceSerializer(many=True)},
        tags=["Workspaces"],
    )

    def get(self, request):
        workspaces = Workspace.objects.filter(
            workspace_members__user=request.user,
        )
        serializer = WorkspaceSerializer(
            workspaces,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create workspace",
        description="Creates a workspace and assigns the authenticated user as its owner.",
        request=WorkspaceSerializer,
        responses={201: WorkspaceSerializer},
        tags=["Workspaces"],
    )

    def post (self, request):
        serializer = WorkspaceSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get workspace",
        description="Returns a workspace where the authenticated user is a member.",
        responses={200: WorkspaceSerializer},
        tags=["Workspaces"],
    )

    def get (self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            workspace_members__user=request.user,
            id = workspace_pk,
        )

        serializer = WorkspaceSerializer(
            workspace,
            many=False,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update workspace",
        request=WorkspaceSerializer,
        responses={200: WorkspaceSerializer},
        tags=["Workspaces"],
    )

    def patch(self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )
        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        ensure_workspace_is_active(workspace)

        if actor_membership.role == WorkspaceMember.Role.MEMBER:
            raise PermissionDenied(
                "Members cannot update Workspace"
            )
        serializer = WorkspaceSerializer(
            workspace,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete workspace",
        request=None,
        responses={204: None},
        tags=["Workspaces"],
    )
    def delete(self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )
        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        if actor_membership.role != WorkspaceMember.Role.OWNER:
            raise PermissionDenied(
                "Only Owner can delete workspace"
            )

        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class LeaveWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Leave workspace",
        description="Removes the authenticated user's workspace membership.",
        request=None,
        responses={204: None},
        tags=["Workspaces"],
    )
    def post(self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            workspace_members__user=request.user,
            id = workspace_pk,
        )
        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        if actor_membership.role == WorkspaceMember.Role.OWNER:
            raise ValidationError({
                "member": "Transfer ownership before leaving the workspace."
            })
        actor_membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class TransferOwnershipView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Transfer workspace ownership",
        description="Transfers ownership to another workspace member.",
        request=TransferOwnershipSerializer,
        responses={200: TransferOwnershipResponseSerializer},
        tags=["Workspaces"]
    )

    @transaction.atomic
    def post(self, request, workspace_pk):
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = get_object_or_404(
            Workspace.objects.select_for_update(),
            id=workspace_pk,
        )
        current_owner = get_object_or_404(
            WorkspaceMember.objects.select_related("user"),
            workspace=workspace,
            role=WorkspaceMember.Role.OWNER,
        )

        if current_owner.user_id != request.user.id:
            raise PermissionDenied(
                "Only the owner can transfer ownership"
            )

        new_owner_member_id = serializer.validated_data["new_owner_member_id"]
        new_owner = get_object_or_404(
            WorkspaceMember.objects.select_related("user"),
            workspace=workspace,
            id=new_owner_member_id,
        )

        if current_owner.id == new_owner.id:
            raise ValidationError({
                "new_owner_member_id": "You are already the workspace owner."
            })

        current_owner.role = WorkspaceMember.Role.ADMIN
        current_owner.save(update_fields=["role"])

        new_owner.role = WorkspaceMember.Role.OWNER
        new_owner.save(update_fields=["role"])

        response_serializer = TransferOwnershipResponseSerializer({
            "previous_owner": current_owner,
            "new_owner": new_owner,
        })

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


class WorkspaceArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Archive workspace",
        request=None,
        responses={200: WorkspaceSerializer},
        tags=["Workspaces"],
    )

    def post(self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )

        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        if actor_membership.role != WorkspaceMember.Role.OWNER:
            raise PermissionDenied(
                "Only the owner can archive the workspace."
            )

        if workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({
                "status": "Workspace is already archived."
            })

        workspace.status = Workspace.Status.ARCHIVED
        workspace.save(update_fields=["status"])

        serializer = WorkspaceSerializer(
            workspace,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

class WorkspaceRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Restore workspace",
        request=None,
        responses={200: WorkspaceSerializer},
        tags=["Workspaces"],
    )
    def post(self, request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )

        membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        if membership.role != WorkspaceMember.Role.OWNER:
            raise PermissionDenied(
                "Only the owner can restore the workspace."
            )

        if workspace.status == Workspace.Status.ACTIVE:
            raise ValidationError({
                "status": "Workspace is already active."
            })

        workspace.status = Workspace.Status.ACTIVE
        workspace.save(update_fields=["status"])

        serializer = WorkspaceSerializer(
            workspace,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )



class WorkspaceMembersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List workspace members",
        description = "Returns a list of workspace members.",
        responses={200: WorkspaceMemberSerializer(many=True)},
        tags=["Workspaces"],
    )

    def get(self,request, workspace_pk):
        workspace = get_object_or_404(
            Workspace,
            workspace_members__user=request.user,
            id = workspace_pk
        )
        members = workspace.workspace_members.select_related("user").all()

        serializer = WorkspaceMemberSerializer(
            members,
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary= "Add workspace member",
        description = "Adds a workspace member to a workspace.",
        request=AddMemberSerializer,
        responses={201: WorkspaceMemberSerializer},
        tags=["Workspaces"],
    )

    def post(self, request, workspace_pk):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = get_object_or_404(
            Workspace,
            workspace_members__user=request.user,
            id = workspace_pk
        )
        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )

        ensure_workspace_is_active(workspace)

        requested_role = serializer.validated_data["role"]

        if actor_membership.role == WorkspaceMember.Role.MEMBER:
            raise PermissionDenied(
                "Members cannot add users to Workspace"
            )
        if(
            actor_membership.role == WorkspaceMember.Role.ADMIN
            and requested_role != WorkspaceMember.Role.MEMBER
        ):
            raise PermissionDenied(
                "Admins can only add users with the member role"
            )

        user = get_object_or_404(
            User,
            id=serializer.validated_data["user_id"],
        )

        if WorkspaceMember.objects.filter(
            workspace=workspace,
            user=user,
        ).exists():
            raise ValidationError(
                {"user_id": "User is already a workspace member"}
            )

        new_member = WorkspaceMember.objects.create(
            workspace=workspace,
            user=user,
            role=requested_role,
        )
        response_serializer = WorkspaceMemberSerializer(new_member)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceMemberView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary= "Get workspace member",
        description = "Gets a workspace member detail.",
        responses={200: WorkspaceMemberSerializer},
        tags=["Workspaces"],
    )
    def get(self, request, workspace_pk, member_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )

        member = get_object_or_404(
            WorkspaceMember.objects.select_related("user"),
            workspace = workspace,
            id=member_pk,
        )

        serializer = WorkspaceMemberSerializer(
            member,
            many=False,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary= "Change workspace member role",
        description = "Change workspace member role",
        request=ChangeMemberRoleSerializer,
        responses={200: WorkspaceMemberSerializer},
        tags=["Workspaces"],
    )

    def patch(self, request, workspace_pk, member_pk):
        serializer = ChangeMemberRoleSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)

        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )

        actor_membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )


        requested_role = serializer.validated_data["role"]

        if actor_membership.role != WorkspaceMember.Role.OWNER:
            raise PermissionDenied(
                "Only Owner can change  member role"
            )

        target = get_object_or_404(
            WorkspaceMember.objects.select_related("user"),
            workspace=workspace,
            id = member_pk,
        )

        if target.role == WorkspaceMember.Role.OWNER:
            raise ValidationError(
                "Owner role can`t be changed"
            )
        if target.role == requested_role:
            raise ValidationError(
                f"User already has the {requested_role} role."
            )
        target.role = requested_role
        target.save(update_fields=["role"])
        response_serializer = WorkspaceMemberSerializer(target)

        return Response(response_serializer.data, status=status.HTTP_200_OK)


    @extend_schema(
        summary="Remove workspace member",
        description="Removes a member from the workspace.",
        request=None,
        responses={204: None},
        tags=["Workspaces"],
    )
    def delete(self, request, workspace_pk, member_pk):
        workspace = get_object_or_404(
            Workspace,
            id=workspace_pk,
            workspace_members__user=request.user,
        )

        actor_membership =get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user,
        )


        target = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            id = member_pk,
        )

        if target.role == WorkspaceMember.Role.OWNER:
            raise PermissionDenied(
                "The owner cannot be removed. Transfer ownership first"
            )

        if target.user_id == request.user.id:
            raise ValidationError({
                "member": "Use the leave workspace endpoint."
            })

        if actor_membership.role == WorkspaceMember.Role.MEMBER:
            raise PermissionDenied(
                "Members cannot remove workspace users"
            )

        if (
            actor_membership.role == WorkspaceMember.Role.ADMIN
            and target.role == WorkspaceMember.Role.ADMIN):
            raise PermissionDenied(
                "Admins cannot remove other admins"
            )

        target.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
