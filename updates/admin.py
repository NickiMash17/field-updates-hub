from django.contrib import admin

from .models import Comment, FieldUpdate, Reaction, Tag, UpdateAuditLog, UserProfile


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "team_name", "created_at"]
    list_filter = ["role", "team_name"]
    search_fields = ["user__username", "team_name"]


@admin.register(FieldUpdate)
class FieldUpdateAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'status', 'visibility', 'is_pinned', 'created_at']
    list_filter = ['category', 'status', 'visibility', 'is_pinned', 'created_at']
    search_fields = ['title', 'content', 'author__username', 'tags__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['tags']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "update", "author", "created_at"]
    search_fields = ["content", "author__username", "update__title"]
    list_filter = ["created_at"]


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ["id", "update", "user", "reaction_type", "created_at"]
    list_filter = ["reaction_type", "created_at"]
    search_fields = ["user__username", "update__title"]


@admin.register(UpdateAuditLog)
class UpdateAuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action", "actor", "field_update", "update_title_snapshot", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["actor__username", "update_title_snapshot", "metadata"]
    readonly_fields = ["created_at"]
