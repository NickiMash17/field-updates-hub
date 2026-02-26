import re

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("field_agent", "Field Agent"),
        ("manager", "Manager"),
        ("admin", "Admin"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="field_agent")
    team_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class FieldUpdate(models.Model):
    CATEGORY_CHOICES = [
        ('pest', 'Pest'),
        ('weather', 'Weather'),
        ('crop', 'Crop'),
        ('fertilizer', 'Fertilizer'),
        ('general', 'General'),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("team", "Team Only"),
        ("private", "Private"),
    ]
    
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="updates"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="public")
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="updates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_hashtags()

    def sync_hashtags(self):
        raw_text = f"{self.title} {self.content}"
        tag_names = sorted({match.group(1).lower() for match in HASHTAG_PATTERN.finditer(raw_text)})
        if not tag_names:
            self.tags.clear()
            return

        existing_tags = {tag.name: tag for tag in Tag.objects.filter(name__in=tag_names)}
        tags_to_set = []
        for name in tag_names:
            tag = existing_tags.get(name)
            if tag is None:
                tag = Tag.objects.create(name=name)
                existing_tags[name] = tag
            tags_to_set.append(tag)
        self.tags.set(tags_to_set)

    def __str__(self):
        return f"{self.title} by {self.author.username}"


class Comment(models.Model):
    update = models.ForeignKey(FieldUpdate, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="update_comments")
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.update_id}"


class Reaction(models.Model):
    REACTION_CHOICES = [
        ("ack", "Acknowledge"),
        ("urgent", "Urgent"),
        ("support", "Support"),
    ]

    update = models.ForeignKey(FieldUpdate, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="update_reactions")
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES, default="ack")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["update", "user"], name="unique_reaction_per_user_per_update"),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.update_id} ({self.reaction_type})"


class UpdateAuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "Create"),
        ("edit", "Edit"),
        ("delete", "Delete"),
        ("comment_add", "Comment Added"),
        ("reaction_toggle", "Reaction Toggled"),
        ("status_change", "Status Changed"),
    ]

    field_update = models.ForeignKey(
        FieldUpdate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="update_audit_logs")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    metadata = models.TextField(blank=True)
    update_title_snapshot = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor.username} {self.action} ({self.update_title_snapshot or self.field_update_id})"


class SavedSearch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_searches")
    name = models.CharField(max_length=100)
    query_params = models.TextField(help_text="URL-encoded query parameters")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_saved_search_per_user"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Attachment(models.Model):
    update = models.ForeignKey(FieldUpdate, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="attachments/%Y/%m/%d/")
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.file_name} for {self.update_id}"

    @property
    def is_image(self):
        return self.content_type.startswith("image/")


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
