from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework import status

from apps.workspace.models import Workspace, WorkspaceMember
from apps.project.models import Project

from .models import Board, BoardColumn
from .serializers import BoardSerializer, BoardColumnSerializer, BoardColumnReorderSerializer

def ensure_board_can_be_modified(board):
    if board.project.workspace.status == Workspace.Status.ARCHIVED:
        raise ValidationError({"workspace": "Archived workspace cannot be modified"})
    if board.project.status == Project.Status.ARCHIVED:
        raise ValidationError({"project": "Archived project cannot be modified"})


class BoardView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Get project board",
        description="Returns the project board with its columns.",
        responses={200: BoardSerializer},
        tags=["Boards"],
    )

    def get(self, request, project_pk):

        board = get_object_or_404(
            Board.objects.prefetch_related("columns").filter(
            Q(project__workspace__workspace_members__user=request.user,
               project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN))
            | Q(project__members__workspace_member__user = request.user)).distinct(),
            project_id = project_pk,
        )

        serializer = BoardSerializer(board)
        return Response(serializer.data, status=status.HTTP_200_OK)



class BoardColumnCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Create a new column",
        description="Creates a new column",
        request=BoardColumnSerializer,
        responses={201: BoardColumnSerializer},
        tags=["Boards"]
    )
    def post(self, request, board_pk):
        serializer = BoardColumnSerializer(data=request.data)

        board = get_object_or_404(
            Board.objects.filter(
                Q(project__workspace__workspace_members__user=request.user,
                  project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER,
                                                                   WorkspaceMember.Role.ADMIN))
                | Q(project__members__workspace_member__user=request.user)
            ).distinct(),
            id=board_pk,
        )
        ensure_board_can_be_modified(board)

        last_column = board.columns.order_by("-position").first()
        if last_column:
            next_position = last_column.position + 1
        else:
            next_position = 1

        serializer.is_valid(raise_exception=True)
        serializer.save(
            board=board,
            position=next_position,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BoardColumnView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary = "Get a board column",
        description = "Returns the board column",
        responses={200: BoardColumnSerializer},
        tags=["Boards"]
    )

    def get(self, request, board_pk, column_pk):
        board = get_object_or_404(
            Board.objects.filter(
                Q(project__workspace__workspace_members__user=request.user,
                  project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER,WorkspaceMember.Role.ADMIN))
                | Q(project__members__workspace_member__user=request.user)
            ).distinct(),
            id = board_pk,
        )

        board_column =  get_object_or_404(
            BoardColumn,
            id = column_pk,
            board=board
        )
        serializer = BoardColumnSerializer(board_column)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @extend_schema(
        summary="Change a column settings",
        description="Change a column settings",
        request= BoardColumnSerializer,
        responses={200: BoardColumnSerializer},
        tags=["Boards"]
    )

    def patch(self, request, board_pk, column_pk):
        board = get_object_or_404(
            Board.objects.filter(
                Q(project__workspace__workspace_members__user=request.user,
                  project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN))
                | Q(project__members__workspace_member__user=request.user)
            ).distinct(),
            id = board_pk,
        )
        ensure_board_can_be_modified(board)

        board_column = get_object_or_404(
            BoardColumn,
            id=column_pk,
            board=board,
        )

        serializer = BoardColumnSerializer(board_column, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


    @extend_schema(
        summary="Delete a  column",
        description = "Deletes a  column",
        responses={204: None},
        tags=["Boards"]
    )

    def delete(self, request, board_pk, column_pk):
        board = get_object_or_404(
            Board.objects.filter(
                Q(project__workspace__workspace_members__user=request.user,
                  project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN))
                | Q(project__members__workspace_member__user=request.user)
            ).distinct(),
            id = board_pk
        )
        ensure_board_can_be_modified(board)

        board_column = get_object_or_404(
            BoardColumn,
            id=column_pk,
            board=board,
        )
        board_column.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BoardColumnsReorderView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Reorder columns",
        description="Changes the order of all columns on a board.",
        request=BoardColumnReorderSerializer,
        responses={200: BoardColumnSerializer(many=True)},
        tags=["Boards"],
    )

    @transaction.atomic
    def patch(self, request, board_pk):
        board = get_object_or_404(
            Board.objects.filter(
                Q(project__workspace__workspace_members__user=request.user,
                  project__workspace__workspace_members__role__in=(WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN))
                | Q(project__members__workspace_member__user=request.user)
            ).distinct(),
            id = board_pk,
        )
        ensure_board_can_be_modified(board)

        serializer = BoardColumnReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        column_ids = serializer.validated_data['column_ids']
        columns = list(board.columns.filter(id__in=column_ids))

        total_columns = board.columns.count()

        if (
            len(columns) != len(column_ids)
            or len(column_ids) != total_columns
        ):
            raise ValidationError({
                "column_ids": "The list must contain every column of this board once."
            })

        columns_by_id = {}
        for column in columns:
            columns_by_id[column.id] = column

        last_column = board.columns.order_by("-position").first()
        temporary_position = last_column.position + 1

        for column in columns:
            column.position = temporary_position
            column.save(update_fields=("position",))
            temporary_position += 1

        for new_position, column_id in enumerate(
            column_ids,
            start=1,
        ):
            column = columns_by_id[column_id]
            column.position = new_position
            column.save(update_fields=("position", "updated_at"))

        ordered_columns = board.columns.all()
        response_serializer = BoardColumnSerializer(
            ordered_columns,
            many=True,
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )
