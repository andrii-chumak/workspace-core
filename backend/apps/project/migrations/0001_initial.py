# Generated manually for the project module.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("workspace_id", models.PositiveBigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
                ("methodology", models.CharField(choices=[("scrum", "Scrum"), ("kanban", "Kanban")], default="kanban", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("archived", "Archived")], db_index=True, default="active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "projects",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProjectMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("product_owner", "Product Owner"), ("scrum_master", "Scrum Master"), ("team_member", "Team Member")], default="team_member", max_length=30)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="project.project")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "project_members",
            },
        ),
        migrations.AddIndex(
            model_name="project",
            index=models.Index(fields=["workspace_id", "status"], name="projects_workspa_6f3405_idx"),
        ),
        migrations.AddIndex(
            model_name="projectmember",
            index=models.Index(fields=["project", "role"], name="project_mem_project_797e6f_idx"),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(fields=("workspace_id", "name"), name="unique_project_name_per_workspace"),
        ),
        migrations.AddConstraint(
            model_name="projectmember",
            constraint=models.UniqueConstraint(fields=("project", "user"), name="unique_project_member"),
        ),
    ]
