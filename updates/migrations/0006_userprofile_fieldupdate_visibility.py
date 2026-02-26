import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_profiles_for_existing_users(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("updates", "UserProfile")
    existing_user_ids = set(UserProfile.objects.values_list("user_id", flat=True))
    profiles = [
        UserProfile(user_id=user.id)
        for user in User.objects.all()
        if user.id not in existing_user_ids
    ]
    if profiles:
        UserProfile.objects.bulk_create(profiles)


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0005_fieldupdate_status_updateauditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("field_agent", "Field Agent"), ("manager", "Manager"), ("admin", "Admin")], default="field_agent", max_length=20)),
                ("team_name", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["user__username"]},
        ),
        migrations.AddField(
            model_name="fieldupdate",
            name="visibility",
            field=models.CharField(
                choices=[("public", "Public"), ("team", "Team Only"), ("private", "Private")],
                default="public",
                max_length=20,
            ),
        ),
        migrations.RunPython(create_profiles_for_existing_users, migrations.RunPython.noop),
    ]
