from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from apps.workspace.models import Workspace, WorkspaceMember

from .models import Kanban, Project, ProjectMember, Scrum, Sprint, SprintEvent
from .permissions import IsProjectMember, can_manage_project
from .serializers import (
    KanbanSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    ScrumSerializer,
    SprintEventSerializer,
    SprintSerializer,
)
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

@extend_schema(
    parameters=[
        OpenApiParameter(name='workspace_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False, description='Filter by workspace ID'),
        OpenApiParameter(name='status', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False, description='Filter by project status (active/archived)'),
    ]
)
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsProjectMember]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Project.objects.select_related("created_by", "workspace")
            .prefetch_related("members__workspace_member__user")
            .filter(
                Q(workspace__workspace_members__user=user,
                  workspace__workspace_members__role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN])
                | Q(created_by=user)
                | Q(members__workspace_member__user=user)
            )
            .distinct()
        )

        workspace_id = self.request.query_params.get("workspace_id")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        project_status = self.request.query_params.get("status")
        if project_status:
            queryset = queryset.filter(status=project_status)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        project = serializer.save(created_by=self.request.user)

        workspace_member, _ = WorkspaceMember.objects.get_or_create(
            workspace=project.workspace,
            user=self.request.user,
        )

        ProjectMember.objects.get_or_create(
            project=project,
            workspace_member=workspace_member,
            defaults={"role": ProjectMember.Role.PRODUCT_OWNER},
        )
        if project.methodology == Project.Methodology.SCRUM:
            Scrum.objects.get_or_create(project=project)
        if project.methodology == Project.Methodology.KANBAN:
            Kanban.objects.get_or_create(project=project)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})

        is_workspace_owner_or_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=request.user,
            role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN)
        ).exists()

        is_project_po = ProjectMember.objects.filter(
            project=project,
            workspace_member__user=request.user,
            role=ProjectMember.Role.PRODUCT_OWNER
        ).exists()

        if not (is_workspace_owner_or_admin or is_project_po):
            return Response(
                {"detail": "Only Workspace owner/admin or Project Product Owner can permanently delete the project."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        project.archive()
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        project.restore()
        return Response(self.get_serializer(project).data)

    @extend_schema(
        methods=["POST"],
        request=ProjectMemberSerializer,
        responses={201: ProjectMemberSerializer, 200: ProjectMemberSerializer}
    )
    @extend_schema(
        methods=["GET"],
        responses={200: ProjectMemberSerializer(many=True)}
    )
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        project = self.get_object()

        if request.method == "GET":
            serializer = ProjectMemberSerializer(project.members.select_related("workspace_member__user"), many=True)
            return Response(serializer.data)

        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ProjectMemberSerializer(data=request.data, context={"view": self, "request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data.get("user_id")
        workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
        ).first()

        if not workspace_member:
            raise ValidationError({
                "user_id": "User must be a member of the project workspace."
            })

        membership, created = ProjectMember.objects.update_or_create(
            project=project,
            workspace_member=workspace_member,
            defaults={"role": serializer.validated_data.get("role", ProjectMember.Role.TEAM_MEMBER)},
        )
        response_serializer = ProjectMemberSerializer(membership)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>\d+)")
    def remove_member(self, request, pk=None, user_id=None):
        project = self.get_object()
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise ValidationError({"workspace": "Archived workspace cannot be modified."})
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        if int(user_id) == project.created_by_id:
            return Response(
                {"detail": "Project creator cannot be removed from the project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = project.members.filter(workspace_member__user_id=user_id).delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND
        )


def ensure_project_can_be_managed(user, project):
    if project.workspace.status == Workspace.Status.ARCHIVED:
        raise ValidationError({"workspace": "Archived workspace cannot be modified."})
    if project.status == Project.Status.ARCHIVED:
        raise ValidationError({"project": "Archived project cannot be modified."})
    if not can_manage_project(user, project):
        return Response(status=status.HTTP_403_FORBIDDEN)
    return None


class ScrumViewSet(viewsets.ModelViewSet):
    serializer_class = ScrumSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Scrum.objects.select_related(
            "project",
            "project__workspace",
            "current_sprint",
        ).filter(
            Q(project__workspace__workspace_members__user=user, project__workspace__workspace_members__role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN])
            | Q(project__created_by=user)
            | Q(project__members__workspace_member__user=user)
        ).distinct()

        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        denied = ensure_project_can_be_managed(self.request.user, project)
        if denied is not None:
            raise PermissionDenied("You cannot manage this project.")
        serializer.save()

    def update(self, request, *args, **kwargs):
        scrum = self.get_object()
        denied = ensure_project_can_be_managed(request.user, scrum.project)
        if denied is not None:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        scrum = self.get_object()
        denied = ensure_project_can_be_managed(request.user, scrum.project)
        if denied is not None:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Scrum settings cannot be deleted separately from the project."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class KanbanViewSet(viewsets.ModelViewSet):
    serializer_class = KanbanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Kanban.objects.select_related(
            "project",
            "project__workspace",
        ).filter(
            Q(project__workspace__workspace_members__user=user, project__workspace__workspace_members__role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN])
            | Q(project__created_by=user)
            | Q(project__members__workspace_member__user=user)
        ).distinct()

        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        denied = ensure_project_can_be_managed(self.request.user, project)
        if denied is not None:
            raise PermissionDenied("You cannot manage this project.")
        serializer.save()

    def update(self, request, *args, **kwargs):
        kanban = self.get_object()
        denied = ensure_project_can_be_managed(request.user, kanban.project)
        if denied is not None:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kanban = self.get_object()
        denied = ensure_project_can_be_managed(request.user, kanban.project)
        if denied is not None:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Kanban settings cannot be deleted separately from the project."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class SprintViewSet(viewsets.ModelViewSet):
    serializer_class = SprintSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Sprint.objects.select_related(
            "scrum",
            "scrum__project",
            "scrum__project__workspace",
        ).filter(
            Q(scrum__project__workspace__workspace_members__user=user, scrum__project__workspace__workspace_members__role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN])
            | Q(scrum__project__created_by=user)
            | Q(scrum__project__members__workspace_member__user=user)
        ).distinct()

        scrum_id = self.request.query_params.get("scrum_id")
        if scrum_id:
            queryset = queryset.filter(scrum_id=scrum_id)

        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(scrum__project_id=project_id)

        sprint_status = self.request.query_params.get("status")
        if sprint_status:
            queryset = queryset.filter(status=sprint_status)
        return queryset

    def perform_create(self, serializer):
        scrum = serializer.validated_data["scrum"]
        denied = ensure_project_can_be_managed(self.request.user, scrum.project)
        if denied is not None:
            raise PermissionDenied("You cannot manage this project.")
        serializer.save()

    def update(self, request, *args, **kwargs):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        sprint.archive()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        sprint.start()
        return Response(self.get_serializer(sprint).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        sprint.complete()
        return Response(self.get_serializer(sprint).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        sprint = self.get_object()
        denied = ensure_project_can_be_managed(request.user, sprint.scrum.project)
        if denied is not None:
            return denied
        sprint.archive()
        return Response(self.get_serializer(sprint).data)


class SprintEventViewSet(viewsets.ModelViewSet):
    serializer_class = SprintEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = SprintEvent.objects.select_related(
            "sprint",
            "sprint__scrum",
            "sprint__scrum__project",
            "sprint__scrum__project__workspace",
        ).filter(
            Q(sprint__scrum__project__workspace__workspace_members__user=user, sprint__scrum__project__workspace__workspace_members__role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN])
            | Q(sprint__scrum__project__created_by=user)
            | Q(sprint__scrum__project__members__workspace_member__user=user)
        ).distinct()

        sprint_id = self.request.query_params.get("sprint_id")
        if sprint_id:
            queryset = queryset.filter(sprint_id=sprint_id)
        return queryset

    def perform_create(self, serializer):
        sprint = serializer.validated_data["sprint"]
        denied = ensure_project_can_be_managed(self.request.user, sprint.scrum.project)
        if denied is not None:
            raise PermissionDenied("You cannot manage this project.")
        serializer.save()

    def update(self, request, *args, **kwargs):
        event = self.get_object()
        denied = ensure_project_can_be_managed(request.user, event.sprint.scrum.project)
        if denied is not None:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        event = self.get_object()
        denied = ensure_project_can_be_managed(request.user, event.sprint.scrum.project)
        if denied is not None:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        denied = ensure_project_can_be_managed(request.user, event.sprint.scrum.project)
        if denied is not None:
            return denied
        return super().destroy(request, *args, **kwargs)
