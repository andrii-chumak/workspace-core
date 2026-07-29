from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.workspace.models import Workspace, WorkspaceMember

from .models import Project, ProjectMember

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
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMember.Role.OWNER,
        )
        WorkspaceMember.objects.create(
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
                user=self.owner,
                role=ProjectMember.Role.PRODUCT_OWNER,
            ).exists()
        )

    def test_member_can_read_but_not_update_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(project=project, user=self.member)

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
            user=self.owner,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        members_url = reverse("project-members", args=[project.id])
        add_response = self.client.post(
            members_url,
            {"user_id": self.member.id, "role": ProjectMember.Role.SCRUM_MASTER},
            format="json",
        )

        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(project.members.filter(user=self.member).exists())

        remove_response = self.client.delete(
            reverse("project-remove-member", args=[project.id, self.member.id])
        )

        self.assertEqual(remove_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(project.members.filter(user=self.member).exists())

    def test_owner_can_delete_project_completely(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
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
        ProjectMember.objects.create(project=project, user=self.member, role=ProjectMember.Role.SCRUM_MASTER)

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
            user=self.owner,
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
            user=self.owner,
            role=ProjectMember.Role.PRODUCT_OWNER,
        )

        response = self.client.post(
            reverse("project-members", args=[project.id]),
            {"user_id": self.outsider.id, "role": ProjectMember.Role.TEAM_MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
