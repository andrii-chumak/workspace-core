from django.db import models

class Workspace(models.Model):
    name = models.CharField(max_length = 50, default ="My Workspace")
    description = models.TextField(blank=True)
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"
    status = models.CharField(max_length = 20, choices = Status, default = Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        db_table = "workspaces"
