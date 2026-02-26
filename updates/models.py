import re

from django.contrib.auth.models import User
from django.db import models


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"


class FieldUpdate(models.Model):
    CATEGORY_CHOICES = [
        ('pest', 'Pest'),
        ('weather', 'Weather'),
        ('crop', 'Crop'),
        ('fertilizer', 'Fertilizer'),
        ('general', 'General'),
    ]
    
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="updates"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
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
