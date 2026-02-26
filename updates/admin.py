from django.contrib import admin

from .models import Comment, FieldUpdate, Reaction, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(FieldUpdate)
class FieldUpdateAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'is_pinned', 'created_at']
    list_filter = ['category', 'is_pinned', 'created_at']
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
