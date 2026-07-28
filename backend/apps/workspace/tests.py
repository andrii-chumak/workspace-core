from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Workspace, WorkspaceMember


User = get_user_model()


class WorkspaceAPITestCase(APITestCase):
    def setUp(self):
        self.owner = self.create_user("owner")
        self.admin = self.create_user("admin")
        self.member = self.create_user("member")
        self.outsider = self.create_user("outsider")

        self.workspace = Workspace.objects.create(
            name="Test workspace",
            description="Workspace used by API tests",
        )
        self.owner_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMember.Role.OWNER,
        )
        self.admin_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.admin,
            role=WorkspaceMember.Role.ADMIN,
        )
        self.member_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMember.Role.MEMBER,
        )

    @staticmethod
    def create_user(username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="StrongTestPassword123!",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def workspace_detail_url(self, workspace=None):
        workspace = workspace or self.workspace
        return reverse(
            "workspace-get-update-delete",
            kwargs={"workspace_pk": workspace.pk},
        )

    def members_url(self, workspace=None):
        workspace = workspace or self.workspace
        return reverse(
            "workspace_members-list-add",
            kwargs={"workspace_pk": workspace.pk},
        )

    def member_detail_url(self, membership):
        return reverse(
            "workspace_member-get-change-delete",
            kwargs={
                "workspace_pk": membership.workspace_id,
                "member_pk": membership.pk,
            },
        )

    def test_unauthenticated_user_cannot_list_workspaces(self):
        response = self.client.get(reverse("workspace-list-create"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_workspace_creates_owner_membership(self):
        self.authenticate(self.outsider)

        response = self.client.post(
            reverse("workspace-list-create"),
            {
                "name": "Created workspace",
                "description": "Created through the API",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_workspace = Workspace.objects.get(pk=response.data["id"])
        membership = WorkspaceMember.objects.get(
            workspace=created_workspace,
            user=self.outsider,
        )
        self.assertEqual(membership.role, WorkspaceMember.Role.OWNER)
        self.assertEqual(
            response.data["current_membership"],
            {"id": membership.pk, "role": WorkspaceMember.Role.OWNER},
        )

    def test_list_returns_only_joined_workspaces_and_current_membership(self):
        hidden_workspace = Workspace.objects.create(name="Hidden workspace")
        WorkspaceMember.objects.create(
            workspace=hidden_workspace,
            user=self.outsider,
            role=WorkspaceMember.Role.OWNER,
        )
        self.authenticate(self.member)

        response = self.client.get(reverse("workspace-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.workspace.pk)
        self.assertEqual(
            response.data[0]["current_membership"],
            {
                "id": self.member_membership.pk,
                "role": WorkspaceMember.Role.MEMBER,
            },
        )

    def test_outsider_cannot_retrieve_workspace(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.workspace_detail_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_retrieve_workspace_with_current_membership(self):
        self.authenticate(self.member)

        response = self.client.get(self.workspace_detail_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.workspace.pk)
        self.assertEqual(
            response.data["current_membership"],
            {
                "id": self.member_membership.pk,
                "role": WorkspaceMember.Role.MEMBER,
            },
        )

    def test_admin_can_update_active_workspace(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.workspace_detail_url(),
            {"name": "Updated by admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, "Updated by admin")
        self.assertEqual(
            response.data["current_membership"]["role"],
            WorkspaceMember.Role.ADMIN,
        )

    def test_member_cannot_update_workspace(self):
        self.authenticate(self.member)

        response = self.client.patch(
            self.workspace_detail_url(),
            {"name": "Forbidden update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_archived_workspace_cannot_be_updated(self):
        self.workspace.status = Workspace.Status.ARCHIVED
        self.workspace.save(update_fields=["status"])
        self.authenticate(self.owner)

        response = self.client.patch(
            self.workspace_detail_url(),
            {"name": "Forbidden archived update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_owner_can_delete_workspace(self):
        self.authenticate(self.admin)
        forbidden_response = self.client.delete(self.workspace_detail_url())

        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.authenticate(self.owner)
        response = self.client.delete(self.workspace_detail_url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Workspace.objects.filter(pk=self.workspace.pk).exists())

    def test_member_can_leave_but_owner_cannot_leave(self):
        leave_url = reverse(
            "workspace_leave",
            kwargs={"workspace_pk": self.workspace.pk},
        )
        self.authenticate(self.owner)
        owner_response = self.client.post(leave_url)

        self.assertEqual(owner_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.authenticate(self.member)
        member_response = self.client.post(leave_url)

        self.assertEqual(member_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            WorkspaceMember.objects.filter(pk=self.member_membership.pk).exists()
        )

    def test_owner_can_transfer_ownership_to_another_member(self):
        self.authenticate(self.owner)
        url = reverse(
            "workspace-transfer-ownership",
            kwargs={"workspace_pk": self.workspace.pk},
        )

        response = self.client.post(
            url,
            {"new_owner_member_id": self.member_membership.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.owner_membership.refresh_from_db()
        self.member_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, WorkspaceMember.Role.ADMIN)
        self.assertEqual(self.member_membership.role, WorkspaceMember.Role.OWNER)
        self.assertEqual(
            response.data["previous_owner"]["id"],
            self.owner_membership.pk,
        )
        self.assertEqual(
            response.data["new_owner"]["id"],
            self.member_membership.pk,
        )
        self.assertEqual(
            WorkspaceMember.objects.filter(
                workspace=self.workspace,
                role=WorkspaceMember.Role.OWNER,
            ).count(),
            1,
        )

    def test_database_prevents_two_owners_in_one_workspace(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.member_membership.role = WorkspaceMember.Role.OWNER
                self.member_membership.save(update_fields=["role"])

    def test_non_owner_cannot_transfer_ownership(self):
        self.authenticate(self.admin)
        url = reverse(
            "workspace-transfer-ownership",
            kwargs={"workspace_pk": self.workspace.pk},
        )

        response = self.client.post(
            url,
            {"new_owner_member_id": self.member_membership.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_archive_and_restore_workspace(self):
        self.authenticate(self.owner)
        archive_url = reverse(
            "workspace_archive",
            kwargs={"workspace_pk": self.workspace.pk},
        )
        restore_url = reverse(
            "workspace-restore",
            kwargs={"workspace_pk": self.workspace.pk},
        )

        archive_response = self.client.post(archive_url)

        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(archive_response.data["status"], Workspace.Status.ARCHIVED)
        self.assertEqual(
            archive_response.data["current_membership"]["role"],
            WorkspaceMember.Role.OWNER,
        )
        restore_response = self.client.post(restore_url)

        self.assertEqual(restore_response.status_code, status.HTTP_200_OK)
        self.assertEqual(restore_response.data["status"], Workspace.Status.ACTIVE)

    def test_non_owner_cannot_archive_or_restore_workspace(self):
        self.authenticate(self.admin)
        archive_url = reverse(
            "workspace_archive",
            kwargs={"workspace_pk": self.workspace.pk},
        )

        archive_response = self.client.post(archive_url)

        self.assertEqual(archive_response.status_code, status.HTTP_403_FORBIDDEN)
        self.workspace.status = Workspace.Status.ARCHIVED
        self.workspace.save(update_fields=["status"])
        restore_url = reverse(
            "workspace-restore",
            kwargs={"workspace_pk": self.workspace.pk},
        )

        restore_response = self.client.post(restore_url)

        self.assertEqual(restore_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_add_admin_and_response_contains_user(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.members_url(),
            {"user_id": self.outsider.pk, "role": WorkspaceMember.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = WorkspaceMember.objects.get(
            workspace=self.workspace,
            user=self.outsider,
        )
        self.assertEqual(membership.role, WorkspaceMember.Role.ADMIN)
        self.assertEqual(response.data["user"]["id"], self.outsider.pk)

    def test_workspace_member_can_list_members(self):
        self.authenticate(self.member)

        response = self.client.get(self.members_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        returned_ids = {membership["id"] for membership in response.data}
        self.assertEqual(
            returned_ids,
            {
                self.owner_membership.pk,
                self.admin_membership.pk,
                self.member_membership.pk,
            },
        )
        self.assertIn("user", response.data[0])

    def test_admin_can_only_add_members(self):
        self.authenticate(self.admin)

        forbidden_response = self.client.post(
            self.members_url(),
            {"user_id": self.outsider.pk, "role": WorkspaceMember.Role.ADMIN},
            format="json",
        )

        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        allowed_response = self.client.post(
            self.members_url(),
            {"user_id": self.outsider.pk, "role": WorkspaceMember.Role.MEMBER},
            format="json",
        )

        self.assertEqual(allowed_response.status_code, status.HTTP_201_CREATED)

    def test_cannot_add_member_to_archived_workspace(self):
        self.workspace.status = Workspace.Status.ARCHIVED
        self.workspace.save(update_fields=["status"])
        self.authenticate(self.owner)

        response = self.client.post(
            self.members_url(),
            {"user_id": self.outsider.pk, "role": WorkspaceMember.Role.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_change_member_role_but_cannot_change_owner_role(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.member_detail_url(self.member_membership),
            {"role": WorkspaceMember.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, WorkspaceMember.Role.ADMIN)
        owner_response = self.client.patch(
            self.member_detail_url(self.owner_membership),
            {"role": WorkspaceMember.Role.MEMBER},
            format="json",
        )

        self.assertEqual(owner_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_remove_member_but_not_another_admin(self):
        self.authenticate(self.admin)

        member_response = self.client.delete(
            self.member_detail_url(self.member_membership)
        )

        self.assertEqual(member_response.status_code, status.HTTP_204_NO_CONTENT)
        other_admin = self.create_user("other-admin")
        other_admin_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=other_admin,
            role=WorkspaceMember.Role.ADMIN,
        )
        admin_response = self.client.delete(
            self.member_detail_url(other_admin_membership)
        )

        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_detail_contains_nested_user(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.member_detail_url(self.member_membership)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.member_membership.pk)
        self.assertEqual(response.data["user"]["id"], self.member.pk)
        self.assertEqual(response.data["user"]["username"], self.member.username)
