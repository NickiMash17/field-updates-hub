from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0002_alter_fieldupdate_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="fieldupdate",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="fieldupdate",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="updates", to="updates.tag"),
        ),
    ]
