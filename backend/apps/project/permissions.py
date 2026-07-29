from rest_framework import permissions

from .models import ProjectMember


MANAGER_ROLES = {
    ProjectMember.Role.PRODUCT_OWNER,
    ProjectMember.Role.SCRUM_MASTER,
}


def can_manage_project(user, project):
    if not user or not user.is_authenticated:
        return False
    if project.created_by_id == user.id:
        return True
    return ProjectMember.objects.filter(
        project=project,
        user=user,
        role__in=MANAGER_ROLES,
    ).exists()


class IsProjectMember(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.created_by_id == request.user.id:
            return True
        return obj.members.filter(user=request.user).exists()
