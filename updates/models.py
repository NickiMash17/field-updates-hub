from django.db import models
from django.contrib.auth.models import User


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
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.title} by {self.author.username}"
