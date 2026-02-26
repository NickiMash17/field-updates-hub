import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0003_tag_fieldupdate_is_pinned_fieldupdate_tags"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="update_comments", to=settings.AUTH_USER_MODEL)),
                ("update", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="updates.fieldupdate")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="Reaction",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reaction_type", models.CharField(choices=[("ack", "Acknowledge"), ("urgent", "Urgent"), ("support", "Support")], default="ack", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("update", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="updates.fieldupdate")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="update_reactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="reaction",
            constraint=models.UniqueConstraint(fields=("update", "user"), name="unique_reaction_per_user_per_update"),
        ),
    ]
