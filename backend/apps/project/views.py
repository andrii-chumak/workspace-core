from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Project, ProjectMember
from .permissions import IsProjectMember, can_manage_project
from .serializers import ProjectMemberSerializer, ProjectSerializer
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
        queryset = (
            Project.objects.select_related("created_by")
            .prefetch_related("members__user")
            .filter(Q(created_by=self.request.user) | Q(members__user=self.request.user))
            .distinct()
        )

        workspace_id = self.request.query_params.get("workspace_id")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        project_status = self.request.query_params.get("status")
        if project_status:
            queryset = queryset.filter(status=project_status)

        return queryset

    def perform_create(self, serializer):
        project = serializer.save(created_by=self.request.user)
        ProjectMember.objects.get_or_create(
            project=project,
            user=self.request.user,
            defaults={"role": ProjectMember.Role.PRODUCT_OWNER},
        )

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        project = self.get_object()
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if project.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the project creator can permanently delete the project."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        project.archive()
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        project = self.get_object()
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
            serializer = ProjectMemberSerializer(project.members.select_related("user"), many=True)
            return Response(serializer.data)

        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership, created = ProjectMember.objects.update_or_create(
            project=project,
            user=serializer.validated_data["user"],
            defaults={"role": serializer.validated_data["role"]},
        )
        response_serializer = ProjectMemberSerializer(membership)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>\d+)")
    def remove_member(self, request, pk=None, user_id=None):
        project = self.get_object()
        if not can_manage_project(request.user, project):
            return Response(status=status.HTTP_403_FORBIDDEN)
        if int(user_id) == project.created_by_id:
            return Response(
                {"detail": "Project creator cannot be removed from the project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = project.members.filter(user_id=user_id).delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND
        )
