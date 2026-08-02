from django.db import models

from .board import Board

class BoardColumn(models.Model):
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='columns',
    )
    name = models.CharField(max_length=40)

    class ColumnType(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        IN_REVIEW = "in_review", "In Review"
        DONE = "done", "Done"

    column_type = models.CharField(max_length=20, choices=ColumnType)
    position = models.PositiveIntegerField()
    wip_limit = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'board_columns'

        ordering = ("position", "id")

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "board",
                    "position",
                ),
                name="unique_board_column_position",
            ),
            models.UniqueConstraint(
                fields=(
                    "board",
                    "name",
                ),
                name="unique_board_column_name",
            ),
            models.CheckConstraint(
                condition= (
                    models.Q(wip_limit__isnull=True)
                    | models.Q(wip_limit__gt=0)
                ),
                name = "board_column_wip_limit_positive"
            ),
        ]

    def __str__(self):
        return f'{self.name} (board {self.board_id})'


