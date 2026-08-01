from rest_framework import permissions

from apps.workspace.models import WorkspaceMember

from .models import ProjectMember


MANAGER_ROLES = {
    ProjectMember.Role.PRODUCT_OWNER,
    ProjectMember.Role.SCRUM_MASTER,
}


def can_manage_project(user, project):
    if not user or not user.is_authenticated:
        return False

    if WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN),
    ).exists():
        return True

    return ProjectMember.objects.filter(
        project=project,
        workspace_member__user=user,
        role__in=MANAGER_ROLES,
    ).exists()


class IsProjectMember(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if obj.workspace.workspace_members.filter(
            user=request.user,
            role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN)
        ).exists():
            return True

        if obj.created_by_id == request.user.id:
            return True

        return obj.members.filter(workspace_member__user=request.user).exists()
