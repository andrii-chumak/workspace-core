from django.contrib import admin

from .models import Kanban, Project, ProjectMember, Scrum, Sprint, SprintEvent


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "workspace_id", "methodology", "status", "created_by", "created_at")
    list_filter = ("methodology", "status", "workspace_id")
    search_fields = ("name", "description")
    inlines = (ProjectMemberInline,)


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "workspace_member", "role", "joined_at")
    list_filter = ("role",)
    search_fields = (
        "project__name",
        "workspace_member__user__username",
        "workspace_member__user__email",
    )


@admin.register(Scrum)
class ScrumAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "sprint_duration_weeks", "current_sprint")
    search_fields = ("project__name",)


@admin.register(Kanban)
class KanbanAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "wip_limit_enabled", "default_column_wip_limit")
    list_filter = ("wip_limit_enabled",)
    search_fields = ("project__name",)


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "scrum", "status", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("name", "scrum__project__name")


@admin.register(SprintEvent)
class SprintEventAdmin(admin.ModelAdmin):
    list_display = ("id", "sprint", "type", "scheduled_at", "duration_minutes")
    list_filter = ("type",)
    search_fields = ("sprint__name", "notes")