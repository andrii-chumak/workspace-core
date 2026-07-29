from django.conf import settings
from django.db import models

from apps.workspace.models import Workspace


class Project(models.Model):
    class Methodology(models.TextChoices):
        SCRUM = "scrum", "Scrum"
        KANBAN = "kanban", "Kanban"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    methodology = models.CharField(
        max_length=20,
        choices=Methodology.choices,
        default=Methodology.KANBAN,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                name="unique_project_name_per_workspace",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.workspace_id})"

    def archive(self):
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["status", "updated_at"])

    def restore(self):
        self.status = self.Status.ACTIVE
        self.save(update_fields=["status", "updated_at"])


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        PRODUCT_OWNER = "product_owner", "Product Owner"
        SCRUM_MASTER = "scrum_master", "Scrum Master"
        TEAM_MEMBER = "team_member", "Team Member"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.TEAM_MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_members"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                name="unique_project_member",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "role"]),
        ]

    def __str__(self):
        return f"{self.user_id} in project {self.project_id}"


class Scrum(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="scrum",
    )
    sprint_duration_weeks = models.PositiveSmallIntegerField(default=2)
    definition_of_done = models.TextField(blank=True)
    current_sprint = models.ForeignKey(
        "Sprint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "scrum"

    def __str__(self):
        return f"Scrum for project {self.project_id}"


class Kanban(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="kanban",
    )
    wip_limit_enabled = models.BooleanField(default=False)
    default_column_wip_limit = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "kanban"

    def __str__(self):
        return f"Kanban for project {self.project_id}"


class Sprint(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    scrum = models.ForeignKey(
        Scrum,
        on_delete=models.CASCADE,
        related_name="sprints",
    )
    name = models.CharField(max_length=120)
    goal = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sprints"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["scrum", "name"],
                name="unique_sprint_name_per_scrum",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="sprint_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["scrum", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.scrum_id})"

    def start(self):
        Sprint.objects.filter(
            scrum=self.scrum,
            status=self.Status.ACTIVE,
        ).exclude(pk=self.pk).update(status=self.Status.PLANNED)
        self.status = self.Status.ACTIVE
        self.save(update_fields=["status", "updated_at"])
        Scrum.objects.filter(pk=self.scrum_id).update(current_sprint=self)

    def complete(self):
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status", "updated_at"])
        Scrum.objects.filter(pk=self.scrum_id, current_sprint=self).update(current_sprint=None)

    def archive(self):
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["status", "updated_at"])
        Scrum.objects.filter(pk=self.scrum_id, current_sprint=self).update(current_sprint=None)


class SprintEvent(models.Model):
    class EventType(models.TextChoices):
        PLANNING = "planning", "Planning"
        DAILY_STANDUP = "daily_standup", "Daily Standup"
        REVIEW = "review", "Review"
        RETROSPECTIVE = "retrospective", "Retrospective"
        BACKLOG_REFINEMENT = "backlog_refinement", "Backlog Refinement"

    sprint = models.ForeignKey(
        Sprint,
        on_delete=models.CASCADE,
        related_name="events",
    )
    type = models.CharField(max_length=30, choices=EventType.choices)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "sprint_events"
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["sprint", "type"]),
        ]

    def __str__(self):
        return f"{self.type} for sprint {self.sprint_id}"
