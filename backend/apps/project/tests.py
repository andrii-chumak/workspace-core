from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.workspace.models import Workspace, WorkspaceMember

from .models import Kanban, Project, ProjectMember, Scrum, Sprint, SprintEvent

User = get_user_model()


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="Password12345!",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="Password12345!",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="Password12345!",
        )
        self.workspace = Workspace.objects.create(
            name="Engineering",
            description="Workspace for project tests",
        )
        self.owner_wm = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMember.Role.OWNER,
        )
        self.member_wm = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMember.Role.MEMBER,
        )
        self.client.force_authenticate(self.owner)

    def test_create_project_adds_creator_as_product_owner(self):
        response = self.client.post(
            reverse("project-list"),
            {
                "workspace_id": self.workspace.id,
                "name": "Core API",
                "description": "Project backend",
                "methodology": Project.Methodology.SCRUM,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(id=response.data["id"])
        self.assertEqual(project.created_by, self.owner)
        self.assertTrue(
            ProjectMember.objects.filter(
                project=project,
                workspace_member=self.owner_wm,
                role=ProjectMember.Role.PRODUCT_OWNER,
            ).exists()
        )
        self.assertTrue(Scrum.objects.filter(project=project).exists())

    def test_create_kanban_project_adds_kanban_settings(self):
        response = self.client.post(
            reverse("project-list"),
            {
                "workspace_id": self.workspace.id,
                "name": "Support Board",
                "methodology": Project.Methodology.KANBAN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(id=response.data["id"])
        self.assertTrue(Kanban.objects.filter(project=project).exists())

    def test_project_methodology_cannot_be_changed_after_creation(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            methodology=Project.Methodology.SCRUM,
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.patch(
            reverse("project-detail", args=[project.id]),
            {"methodology": Project.Methodology.KANBAN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_can_read_but_not_update_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(project=project, workspace_member=self.member_wm)

        self.client.force_authenticate(self.member)
        detail_url = reverse("project-detail", args=[project.id])

        read_response = self.client.get(detail_url)
        update_response = self.client.patch(detail_url, {"name": "Renamed"}, format="json")

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_read_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )

        self.client.force_authenticate(self.outsider)
        response = self.client.get(reverse("project-detail", args=[project.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_add_and_remove_member(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        members_url = reverse("project-members", args=[project.id])
        add_response = self.client.post(
            members_url,
            {"user_id": self.member.id, "role": ProjectMember.Role.SCRUM_MASTER},
            format="json",
        )

        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(project.members.filter(workspace_member=self.member_wm).exists())

        remove_response = self.client.delete(
            reverse("project-remove-member", args=[project.id, self.member.id])
        )

        self.assertEqual(remove_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(project.members.filter(workspace_member=self.member_wm).exists())

    def test_owner_can_delete_project_completely(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.delete(reverse("project-detail", args=[project.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=project.id).exists())

    def test_member_cannot_delete_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(project=project, workspace_member=self.member_wm, role=ProjectMember.Role.SCRUM_MASTER)

        self.client.force_authenticate(self.member)
        response = self.client.delete(reverse("project-detail", args=[project.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Project.objects.filter(id=project.id).exists())

    def test_archive_and_restore_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        archive_url = reverse("project-archive", args=[project.id])
        response = self.client.post(archive_url)
        project.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(project.status, Project.Status.ARCHIVED)

        restore_url = reverse("project-restore", args=[project.id])
        response = self.client.post(restore_url)
        project.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(project.status, Project.Status.ACTIVE)

    def test_workspace_member_cannot_create_project(self):
        self.client.force_authenticate(self.member)

        response = self.client.post(
            reverse("project-list"),
            {
                "workspace_id": self.workspace.id,
                "name": "Member Project",
                "methodology": Project.Methodology.KANBAN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_member_must_belong_to_workspace(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.post(
            reverse("project-members", args=[project.id]),
            {"user_id": self.outsider.id, "role": ProjectMember.Role.TEAM_MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_update_kanban_settings(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Support Board",
            methodology=Project.Methodology.KANBAN,
            created_by=self.owner,
        )
        kanban = Kanban.objects.create(project=project)
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.patch(
            reverse("kanban-detail", args=[kanban.id]),
            {"wip_limit_enabled": True, "default_column_wip_limit": 4},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kanban.refresh_from_db()
        self.assertTrue(kanban.wip_limit_enabled)
        self.assertEqual(kanban.default_column_wip_limit, 4)

    def test_create_start_complete_and_archive_sprint(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Scrum Project",
            methodology=Project.Methodology.SCRUM,
            created_by=self.owner,
        )
        scrum = Scrum.objects.create(project=project)
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=14)

        create_response = self.client.post(
            reverse("sprint-list"),
            {
                "scrum_id": scrum.id,
                "name": "Sprint 1",
                "goal": "Deliver base API",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        sprint = Sprint.objects.get(id=create_response.data["id"])
        self.assertEqual(sprint.status, Sprint.Status.PLANNED)

        start_response = self.client.post(reverse("sprint-start", args=[sprint.id]))
        sprint.refresh_from_db()
        scrum.refresh_from_db()

        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sprint.status, Sprint.Status.ACTIVE)
        self.assertEqual(scrum.current_sprint_id, sprint.id)

        complete_response = self.client.post(reverse("sprint-complete", args=[sprint.id]))
        sprint.refresh_from_db()
        scrum.refresh_from_db()

        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sprint.status, Sprint.Status.COMPLETED)
        self.assertIsNone(scrum.current_sprint_id)

        archive_response = self.client.delete(reverse("sprint-detail", args=[sprint.id]))
        sprint.refresh_from_db()

        self.assertEqual(archive_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(sprint.status, Sprint.Status.ARCHIVED)

    def test_member_cannot_create_sprint(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Scrum Project",
            methodology=Project.Methodology.SCRUM,
            created_by=self.owner,
        )
        scrum = Scrum.objects.create(project=project)
        ProjectMember.objects.create(project=project, workspace_member=self.member_wm)
        self.client.force_authenticate(self.member)
        start_date = timezone.now()

        response = self.client.post(
            reverse("sprint-list"),
            {
                "scrum_id": scrum.id,
                "name": "Sprint 1",
                "start_date": start_date.isoformat(),
                "end_date": (start_date + timezone.timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_create_sprint_event(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Scrum Project",
            methodology=Project.Methodology.SCRUM,
            created_by=self.owner,
        )
        scrum = Scrum.objects.create(project=project)
        sprint = Sprint.objects.create(
            scrum=scrum,
            name="Sprint 1",
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=14),
        )
        ProjectMember.objects.create(
            project=project,
            workspace_member=self.owner_wm,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.post(
            reverse("sprint-event-list"),
            {
                "sprint_id": sprint.id,
                "type": SprintEvent.EventType.PLANNING,
                "scheduled_at": timezone.now().isoformat(),
                "duration_minutes": 60,
                "notes": "Plan sprint scope",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SprintEvent.objects.filter(sprint=sprint).exists())