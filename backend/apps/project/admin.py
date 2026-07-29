from django.contrib import admin

from .models import Project, ProjectMember


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
    list_display = ("id", "project", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("project__name", "user__username", "user__email")
