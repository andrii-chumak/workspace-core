from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.project.models import Project, ProjectMember
from apps.workspace.models import Workspace, WorkspaceMember

from .models import Board, BoardColumn
from .services import DEFAULT_COLUMNS, create_default_board


User = get_user_model()


class BoardAPITests(APITestCase):
    def setUp(self):
        self.owner = self.create_user("owner")
        self.member = self.create_user("member")
        self.outsider = self.create_user("outsider")

        self.workspace = Workspace.objects.create(
            name="Engineering",
            description="Workspace used by board tests",
        )
        self.owner_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMember.Role.OWNER,
        )
        self.member_membership = WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMember.Role.MEMBER,
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Core API",
            methodology=Project.Methodology.KANBAN,
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=self.project,
            workspace_member=self.member_membership,
            role=ProjectMember.Role.TEAM_MEMBER,
        )
        self.board = create_default_board(self.project)
        self.client.force_authenticate(self.owner)

    @staticmethod
    def create_user(username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="StrongTestPassword123!",
        )

    def board_url(self):
        return reverse(
            "board:board-detail",
            kwargs={"project_pk": self.project.pk},
        )

    def column_create_url(self):
        return reverse(
            "board:column-create",
            kwargs={"board_pk": self.board.pk},
        )

    def column_detail_url(self, column):
        return reverse(
            "board:column-detail-change-delete",
            kwargs={
                "board_pk": self.board.pk,
                "column_pk": column.pk,
            },
        )

    def reorder_url(self):
        return reverse(
            "board:column-reorder",
            kwargs={"board_pk": self.board.pk},
        )

    def ordered_columns(self):
        return list(self.board.columns.order_by("position", "id"))

    def positions_by_id(self):
        return dict(
            self.board.columns.values_list("id", "position")
        )

    def test_project_creation_creates_board_and_default_columns(self):
        response = self.client.post(
            reverse("project-list"),
            {
                "workspace_id": self.workspace.pk,
                "name": "Second project",
                "methodology": Project.Methodology.KANBAN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data["id"])
        board = Board.objects.get(project=project)
        columns = list(
            board.columns.values_list(
                "name",
                "column_type",
                "position",
            )
        )
        expected_columns = [
            (name, column_type, position)
            for position, (name, column_type) in enumerate(
                DEFAULT_COLUMNS,
                start=1,
            )
        ]
        self.assertEqual(columns, expected_columns)

    def test_owner_can_get_board_with_ordered_columns(self):
        response = self.client.get(self.board_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project_id"], self.project.pk)
        self.assertEqual(
            [column["position"] for column in response.data["columns"]],
            [1, 2, 3, 4],
        )

    def test_project_member_can_get_board(self):
        self.client.force_authenticate(self.member)

        response = self.client.get(self.board_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_outsider_cannot_get_board(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.get(self.board_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_get_board(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.board_url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_get_single_column(self):
        column = self.ordered_columns()[0]

        response = self.client.get(self.column_detail_url(column))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], column.pk)
        self.assertEqual(response.data["board_id"], self.board.pk)

    def test_column_must_belong_to_board_from_url(self):
        second_project = Project.objects.create(
            workspace=self.workspace,
            name="Second project",
            created_by=self.owner,
        )
        second_board = create_default_board(second_project)
        foreign_column = second_board.columns.first()

        response = self.client.get(
            reverse(
                "board:column-detail-change-delete",
                kwargs={
                    "board_pk": self.board.pk,
                    "column_pk": foreign_column.pk,
                },
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_column_assigns_next_position(self):
        response = self.client.post(
            self.column_create_url(),
            {
                "name": "Testing",
                "column_type": BoardColumn.ColumnType.IN_REVIEW,
                "wip_limit": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        column = BoardColumn.objects.get(pk=response.data["id"])
        self.assertEqual(column.board, self.board)
        self.assertEqual(column.position, 5)
        self.assertEqual(column.wip_limit, 2)

    def test_create_column_rejects_non_positive_wip_limit(self):
        response = self.client.post(
            self.column_create_url(),
            {
                "name": "Testing",
                "column_type": BoardColumn.ColumnType.IN_REVIEW,
                "wip_limit": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            self.board.columns.filter(name="Testing").exists()
        )

    def test_patch_column_updates_only_provided_fields(self):
        column = self.ordered_columns()[0]
        original_type = column.column_type
        original_position = column.position

        response = self.client.patch(
            self.column_detail_url(column),
            {
                "name": "Ready",
                "wip_limit": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        column.refresh_from_db()
        self.assertEqual(column.name, "Ready")
        self.assertEqual(column.wip_limit, 3)
        self.assertEqual(column.column_type, original_type)
        self.assertEqual(column.position, original_position)

    def test_delete_column_removes_it(self):
        column = self.ordered_columns()[-1]

        response = self.client.delete(self.column_detail_url(column))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            BoardColumn.objects.filter(pk=column.pk).exists()
        )

    def test_reorder_columns_updates_positions_and_response_order(self):
        columns = self.ordered_columns()
        requested_order = [
            columns[0].pk,
            columns[2].pk,
            columns[1].pk,
            columns[3].pk,
        ]

        response = self.client.patch(
            self.reorder_url(),
            {"column_ids": requested_order},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [column["id"] for column in response.data],
            requested_order,
        )
        self.assertEqual(
            list(
                self.board.columns.order_by("position").values_list(
                    "id",
                    flat=True,
                )
            ),
            requested_order,
        )
        self.assertEqual(
            list(
                self.board.columns.order_by("position").values_list(
                    "position",
                    flat=True,
                )
            ),
            [1, 2, 3, 4],
        )

    def test_reorder_rejects_duplicate_ids_without_changing_positions(self):
        columns = self.ordered_columns()
        original_positions = self.positions_by_id()

        response = self.client.patch(
            self.reorder_url(),
            {
                "column_ids": [
                    columns[0].pk,
                    columns[1].pk,
                    columns[1].pk,
                    columns[3].pk,
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.positions_by_id(), original_positions)

    def test_reorder_rejects_missing_column_without_changing_positions(self):
        columns = self.ordered_columns()
        original_positions = self.positions_by_id()

        response = self.client.patch(
            self.reorder_url(),
            {"column_ids": [column.pk for column in columns[:-1]]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.positions_by_id(), original_positions)

    def test_archived_project_blocks_board_mutations(self):
        self.project.status = Project.Status.ARCHIVED
        self.project.save(update_fields=("status",))
        column = self.ordered_columns()[0]
        column_ids = [item.pk for item in self.ordered_columns()]

        create_response = self.client.post(
            self.column_create_url(),
            {
                "name": "Testing",
                "column_type": BoardColumn.ColumnType.IN_REVIEW,
            },
            format="json",
        )
        patch_response = self.client.patch(
            self.column_detail_url(column),
            {"name": "Changed"},
            format="json",
        )
        delete_response = self.client.delete(
            self.column_detail_url(column)
        )
        reorder_response = self.client.patch(
            self.reorder_url(),
            {"column_ids": list(reversed(column_ids))},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(reorder_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.board.columns.count(), 4)
        column.refresh_from_db()
        self.assertNotEqual(column.name, "Changed")

    def test_archived_workspace_blocks_column_creation(self):
        self.workspace.status = Workspace.Status.ARCHIVED
        self.workspace.save(update_fields=("status",))

        response = self.client.post(
            self.column_create_url(),
            {
                "name": "Testing",
                "column_type": BoardColumn.ColumnType.IN_REVIEW,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            self.board.columns.filter(name="Testing").exists()
        )

    def test_archived_project_board_remains_readable(self):
        self.project.status = Project.Status.ARCHIVED
        self.project.save(update_fields=("status",))

        response = self.client.get(self.board_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
