from django.contrib import admin

from .models import FieldUpdate, Tag


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
