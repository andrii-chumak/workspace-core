from django.db import models


class Board(models.Model):
    project = models.OneToOneField(
        "project.Project",
        on_delete=models.CASCADE,
        related_name='board',
    )

    class Meta:
        db_table = 'boards'

    def __str__(self):
        return f'Board {self.id} for project {self.project_id}'


