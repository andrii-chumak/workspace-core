from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import serializers

from apps.workspace.models import Workspace, WorkspaceMember

from .models import Kanban, Project, ProjectMember, Scrum, Sprint, SprintEvent

User = get_user_model()


class ProjectUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "avatar_url")
        read_only_fields = fields


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = ProjectUserSerializer(source="workspace_member.user", read_only=True)

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
    )

    class Meta:
        model = ProjectMember
        fields = ("id", "user", "user_id", "role", "joined_at")
        read_only_fields = ("id", "user", "joined_at")

    def create(self, validated_data):
        user = validated_data.pop("user_id")
        project = validated_data.pop("project", None)

        if not project and "view" in self.context:
            project = self.context["view"].get_object()

        workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user
        ).first()

        if not workspace_member:
            raise serializers.ValidationError({
                "user_id": "User must be a member of the project workspace."
            })

        membership, _ = ProjectMember.objects.update_or_create(
            project=project,
            workspace_member=workspace_member,
            defaults={"role": validated_data.get("role", ProjectMember.Role.TEAM_MEMBER)}
        )
        return membership


class ProjectSerializer(serializers.ModelSerializer):
    workspace_id = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(),
        source="workspace",
    )
    members = ProjectMemberSerializer(many=True, read_only=True)
    created_by = ProjectUserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "workspace_id",
            "name",
            "description",
            "methodology",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "members",
        )
        read_only_fields = ("id", "status", "created_by", "created_at", "updated_at", "members")

    def validate_workspace_id(self, workspace):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        membership = WorkspaceMember.objects.filter(
            workspace=workspace,
            user=request.user,
        ).first()
        if membership is None:
            raise serializers.ValidationError("You are not a member of this workspace.")
        if membership.role == WorkspaceMember.Role.MEMBER:
            raise serializers.ValidationError("Only workspace owners and admins can create projects.")
        if workspace.status == Workspace.Status.ARCHIVED:
            raise serializers.ValidationError("Archived workspace cannot be modified.")
        return workspace

    def validate(self, attrs):
        if self.instance is not None and "workspace" in attrs:
            if attrs["workspace"].id != self.instance.workspace_id:
                raise serializers.ValidationError({
                    "workspace_id": "Project workspace cannot be changed."
                })
        if self.instance is not None and "methodology" in attrs:
            if attrs["methodology"] != self.instance.methodology:
                raise serializers.ValidationError({
                    "methodology": "Project methodology cannot be changed after creation."
                })
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({
                "name": "Project with this name already exists in this workspace."
            })


class ScrumSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        source="project",
    )
    current_sprint_id = serializers.PrimaryKeyRelatedField(
        queryset=Sprint.objects.all(),
        source="current_sprint",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Scrum
        fields = (
            "id",
            "project_id",
            "sprint_duration_weeks",
            "definition_of_done",
            "current_sprint_id",
        )
        read_only_fields = ("id",)

    def validate_project_id(self, project):
        if project.methodology != Project.Methodology.SCRUM:
            raise serializers.ValidationError("Scrum settings can be created only for Scrum projects.")
        return project

    def validate_current_sprint_id(self, sprint):
        project = self.initial_data.get("project_id")
        scrum = self.instance
        if scrum is None and project:
            scrum = Scrum.objects.filter(project_id=project).first()
        if sprint is not None and scrum is not None and sprint.scrum_id != scrum.id:
            raise serializers.ValidationError("Current sprint must belong to this Scrum configuration.")
        return sprint


class KanbanSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        source="project",
    )

    class Meta:
        model = Kanban
        fields = (
            "id",
            "project_id",
            "wip_limit_enabled",
            "default_column_wip_limit",
        )
        read_only_fields = ("id",)

    def validate_project_id(self, project):
        if project.methodology != Project.Methodology.KANBAN:
            raise serializers.ValidationError("Kanban settings can be created only for Kanban projects.")
        return project

    def validate(self, attrs):
        wip_enabled = attrs.get(
            "wip_limit_enabled",
            self.instance.wip_limit_enabled if self.instance else False,
        )
        limit = attrs.get(
            "default_column_wip_limit",
            self.instance.default_column_wip_limit if self.instance else None,
        )
        if wip_enabled and limit is None:
            raise serializers.ValidationError({
                "default_column_wip_limit": "Default WIP limit is required when WIP limits are enabled."
            })
        return attrs


class SprintSerializer(serializers.ModelSerializer):
    scrum_id = serializers.PrimaryKeyRelatedField(
        queryset=Scrum.objects.select_related("project"),
        source="scrum",
    )

    class Meta:
        model = Sprint
        fields = (
            "id",
            "scrum_id",
            "name",
            "goal",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def validate_scrum_id(self, scrum):
        if scrum.project.status == Project.Status.ARCHIVED:
            raise serializers.ValidationError("Archived project cannot be modified.")
        if scrum.project.workspace.status == Workspace.Status.ARCHIVED:
            raise serializers.ValidationError("Archived workspace cannot be modified.")
        return scrum

    def validate(self, attrs):
        start_date = attrs.get("start_date", self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date", self.instance.end_date if self.instance else None)
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({
                "end_date": "Sprint end date must be later than start date."
            })
        return attrs


class SprintEventSerializer(serializers.ModelSerializer):
    sprint_id = serializers.PrimaryKeyRelatedField(
        queryset=Sprint.objects.select_related("scrum__project__workspace"),
        source="sprint",
    )

    class Meta:
        model = SprintEvent
        fields = (
            "id",
            "sprint_id",
            "type",
            "scheduled_at",
            "duration_minutes",
            "notes",
        )
        read_only_fields = ("id",)

    def validate_sprint_id(self, sprint):
        project = sprint.scrum.project
        if project.status == Project.Status.ARCHIVED:
            raise serializers.ValidationError("Archived project cannot be modified.")
        if project.workspace.status == Workspace.Status.ARCHIVED:
            raise serializers.ValidationError("Archived workspace cannot be modified.")
        if sprint.status == Sprint.Status.ARCHIVED:
            raise serializers.ValidationError("Archived sprint cannot be modified.")
        return sprint

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError:
            raise serializers.ValidationError({
                "name": "Project with this name already exists in this workspace."
            })
