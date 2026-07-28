from django.db import models
from .workspace import Workspace
from django.conf import settings
from django.db.models import Q

User = settings.AUTH_USER_MODEL

class WorkspaceMember(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name = "workspace_members")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name = "workspace_member_users"
    )

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
    role = models.CharField(max_length=20, choices=Role, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workspace_members"
        constraints = [
            models.UniqueConstraint(
                fields = ["workspace", "user"],
                name = "unique_workspace_member",
            ),
            models.UniqueConstraint(
                fields = ["workspace"],
                condition=Q(role="owner"),
                name = "unique_workspace_owner",
            ),
        ]