# Generated manually to connect projects to the workspace module.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0002_remove_workspacemember_unique_workspace_owner_and_more"),
        ("project", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="project",
            old_name="workspace_id",
            new_name="workspace",
        ),
        migrations.AlterField(
            model_name="project",
            name="workspace",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="projects",
                to="workspace.workspace",
            ),
        ),
    ]
