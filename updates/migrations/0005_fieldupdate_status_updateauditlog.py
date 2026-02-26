import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0004_comment_reaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldupdate",
            name="status",
            field=models.CharField(
                choices=[("open", "Open"), ("in_progress", "In Progress"), ("resolved", "Resolved")],
                default="open",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="UpdateAuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("create", "Create"), ("edit", "Edit"), ("delete", "Delete"), ("comment_add", "Comment Added"), ("reaction_toggle", "Reaction Toggled"), ("status_change", "Status Changed")], max_length=30)),
                ("metadata", models.TextField(blank=True)),
                ("update_title_snapshot", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="update_audit_logs", to=settings.AUTH_USER_MODEL)),
                ("field_update", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="updates.fieldupdate")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
