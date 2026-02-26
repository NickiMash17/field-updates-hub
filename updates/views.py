from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django import forms
from django.http import HttpResponseForbidden, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils.dateparse import parse_date
from django.utils import timezone
from collections import Counter
from datetime import timedelta
import csv

from .models import Attachment, Comment, FieldUpdate, Reaction, SavedSearch, Tag, UpdateAuditLog, UserProfile
from .forms import FieldUpdateForm


def log_update_event(*, actor, action, update_obj=None, metadata=""):
    UpdateAuditLog.objects.create(
        field_update=update_obj,
        actor=actor,
        action=action,
        metadata=metadata,
        update_title_snapshot=(update_obj.title if update_obj else ""),
    )


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def can_manage_update(user, update):
    if update.author_id == user.id:
        return True
    profile = get_or_create_profile(user)
    return profile.role in {"manager", "admin"}


def can_view_update(user, update):
    if update.visibility == "public":
        return True
    if update.author_id == user.id:
        return True
    if update.visibility == "team":
        viewer_profile = get_or_create_profile(user)
        author_profile = get_or_create_profile(update.author)
        return bool(viewer_profile.team_name and viewer_profile.team_name == author_profile.team_name)
    return False


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")
    
    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return redirect("updates:feed")


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('updates:feed')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def feed(request):
    viewer_profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        action = request.POST.get("action", "create_update")
        if action == "add_comment":
            update = get_object_or_404(FieldUpdate, pk=request.POST.get("update_id"))
            if not can_view_update(request.user, update):
                return HttpResponseForbidden("You don't have permission to comment on this update.")
            comment_text = request.POST.get("comment_content", "").strip()
            if comment_text:
                Comment.objects.create(update=update, author=request.user, content=comment_text)
                log_update_event(
                    actor=request.user,
                    action="comment_add",
                    update_obj=update,
                    metadata=f"comment_length={len(comment_text)}",
                )
            return redirect('updates:feed')
        if action == "toggle_reaction":
            update = get_object_or_404(FieldUpdate, pk=request.POST.get("update_id"))
            if not can_view_update(request.user, update):
                return HttpResponseForbidden("You don't have permission to react to this update.")
            reaction_type = request.POST.get("reaction_type", "ack")
            valid_types = {choice[0] for choice in Reaction.REACTION_CHOICES}
            if reaction_type not in valid_types:
                reaction_type = "ack"

            existing_reaction = Reaction.objects.filter(update=update, user=request.user).first()
            if existing_reaction and existing_reaction.reaction_type == reaction_type:
                existing_reaction.delete()
            else:
                Reaction.objects.update_or_create(
                    update=update,
                    user=request.user,
                    defaults={"reaction_type": reaction_type},
                )
            log_update_event(
                actor=request.user,
                action="reaction_toggle",
                update_obj=update,
                metadata=f"reaction_type={reaction_type}",
            )
            return redirect('updates:feed')

        form = FieldUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            field_update = form.save(commit=False)
            field_update.author = request.user
            field_update.save()
            
            # Handle file uploads
            files = request.FILES.getlist('attachments')
            for uploaded_file in files:
                Attachment.objects.create(
                    update=field_update,
                    file=uploaded_file,
                    file_name=uploaded_file.name,
                    file_size=uploaded_file.size,
                    content_type=uploaded_file.content_type,
                )
            
            log_update_event(
                actor=request.user,
                action="create",
                update_obj=field_update,
                metadata=f"status={field_update.status};category={field_update.category};visibility={field_update.visibility};pinned={field_update.is_pinned};attachments={len(files)}",
            )
            return redirect('updates:feed')
    else:
        form = FieldUpdateForm()
    
    # Get filters from GET parameters
    category_filter = request.GET.get('category')
    status_filter = request.GET.get('status', '').strip()
    visibility_filter = request.GET.get('visibility', '').strip()
    query = request.GET.get('q', '').strip()
    author_filter = request.GET.get('author', '').strip()
    tag_filter = request.GET.get('tag', '').strip().lstrip('#').lower()
    pinned_filter = request.GET.get('pinned', '').strip()
    from_date = parse_date(request.GET.get('from_date', '').strip())
    to_date = parse_date(request.GET.get('to_date', '').strip())
    
    updates = FieldUpdate.objects.select_related('author').prefetch_related(
        'tags',
        'comments__author',
        'reactions__user',
        'attachments',
    ).all()

    # Visibility: public to all, private to owner, team-only to same-team members.
    visibility_q = Q(visibility="public") | Q(author=request.user)
    if viewer_profile.team_name:
        visibility_q |= Q(visibility="team", author__profile__team_name=viewer_profile.team_name)
    updates = updates.filter(visibility_q)

    # Filter updates by category if specified
    if category_filter:
        updates = updates.filter(category=category_filter)
    if status_filter:
        updates = updates.filter(status=status_filter)
    if visibility_filter:
        updates = updates.filter(visibility=visibility_filter)

    # Apply text search across title, content, and author username.
    if query:
        updates = updates.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(author__username__icontains=query)
        )

    if author_filter:
        updates = updates.filter(author__username__icontains=author_filter)

    if tag_filter:
        updates = updates.filter(tags__name__iexact=tag_filter)

    if pinned_filter == 'only':
        updates = updates.filter(is_pinned=True)
    elif pinned_filter == 'exclude':
        updates = updates.filter(is_pinned=False)

    if from_date:
        updates = updates.filter(created_at__date__gte=from_date)
    if to_date:
        updates = updates.filter(created_at__date__lte=to_date)
    
    # Show pinned updates first, then newest.
    updates = updates.distinct().order_by('-is_pinned', '-created_at')
    
    paginator = Paginator(updates, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_updates = list(page_obj.object_list)

    for item in page_updates:
        counts = Counter(item.reactions.values_list("reaction_type", flat=True))
        item.reaction_counts = counts
        user_reaction = next((reaction for reaction in item.reactions.all() if reaction.user_id == request.user.id), None)
        item.current_user_reaction = user_reaction.reaction_type if user_reaction else ""

    # Get user's saved searches
    saved_searches = SavedSearch.objects.filter(user=request.user).order_by('-created_at')[:10]

    return render(request, 'updates/feed.html', {
        'form': form,
        'updates': page_updates,
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'visibility_filter': visibility_filter,
        'author_filter': author_filter,
        'tag_filter': tag_filter,
        'pinned_filter': pinned_filter,
        'from_date_value': request.GET.get('from_date', '').strip(),
        'to_date_value': request.GET.get('to_date', '').strip(),
        'selected_category': category_filter,
        'popular_tags': Tag.objects.order_by('name')[:15],
        'reaction_choices': Reaction.REACTION_CHOICES,
        'viewer_profile': viewer_profile,
        'saved_searches': saved_searches,
    })


@login_required
def edit_update(request, pk):
    update = get_object_or_404(FieldUpdate.objects.prefetch_related('attachments'), pk=pk)
    
    # Check if user is the author
    if not can_manage_update(request.user, update):
        return HttpResponseForbidden("You don't have permission to edit this update.")
    
    if request.method == 'POST':
        previous_title = update.title
        previous_category = update.category
        previous_status = update.status
        previous_visibility = update.visibility
        previous_is_pinned = update.is_pinned
        form = FieldUpdateForm(request.POST, request.FILES, instance=update)
        if form.is_valid():
            edited_update = form.save()
            
            # Handle new file uploads
            files = request.FILES.getlist('attachments')
            for uploaded_file in files:
                Attachment.objects.create(
                    update=edited_update,
                    file=uploaded_file,
                    file_name=uploaded_file.name,
                    file_size=uploaded_file.size,
                    content_type=uploaded_file.content_type,
                )
            
            changed_fields = []
            if previous_title != edited_update.title:
                changed_fields.append("title")
            if previous_category != edited_update.category:
                changed_fields.append("category")
            if previous_is_pinned != edited_update.is_pinned:
                changed_fields.append("is_pinned")
            if previous_status != edited_update.status:
                changed_fields.append("status")
                log_update_event(
                    actor=request.user,
                    action="status_change",
                    update_obj=edited_update,
                    metadata=f"{previous_status}->{edited_update.status}",
                )
            if previous_visibility != edited_update.visibility:
                changed_fields.append("visibility")
            if len(files) > 0:
                changed_fields.append(f"added_{len(files)}_attachments")
            log_update_event(
                actor=request.user,
                action="edit",
                update_obj=edited_update,
                metadata="changed=" + (",".join(changed_fields) if changed_fields else "none"),
            )
            return redirect('updates:feed')
    else:
        form = FieldUpdateForm(instance=update)
    
    return render(request, 'updates/edit.html', {
        'form': form,
        'update': update
    })


@login_required
def delete_update(request, pk):
    update = get_object_or_404(FieldUpdate, pk=pk)
    
    # Check if user is the author
    if not can_manage_update(request.user, update):
        return HttpResponseForbidden("You don't have permission to delete this update.")
    
    if request.method == 'POST':
        log_update_event(
            actor=request.user,
            action="delete",
            update_obj=update,
            metadata=f"status={update.status};category={update.category};visibility={update.visibility}",
        )
        update.delete()
        return redirect('updates:feed')
    
    return render(request, 'updates/confirm_delete.html', {
        'update': update
    })


@login_required
def user_profile(request, user_id):
    profile_user = get_object_or_404(User, pk=user_id)
    profile_user_profile = get_or_create_profile(profile_user)
    viewer_profile = get_or_create_profile(request.user)
    visibility_q = Q(visibility="public") | Q(author=request.user)
    if viewer_profile.team_name and viewer_profile.team_name == profile_user_profile.team_name:
        visibility_q |= Q(visibility="team")
    if request.user == profile_user:
        visibility_q |= Q(visibility="private")

    user_updates = (
        FieldUpdate.objects.filter(author=profile_user)
        .filter(visibility_q)
        .prefetch_related('attachments', 'tags')
        .order_by('-created_at')
    )
    post_count = user_updates.count()
    
    return render(request, 'updates/profile.html', {
        'profile_user': profile_user,
        'profile_user_profile': profile_user_profile,
        'user_updates': user_updates,
        'post_count': post_count
    })


@login_required
def export_feed_csv(request):
    """
    Export the current filtered feed as CSV.
    Respects all filters applied in the feed view.
    """
    viewer_profile = get_or_create_profile(request.user)
    
    # Apply the same filtering logic as the feed view
    category_filter = request.GET.get('category')
    status_filter = request.GET.get('status', '').strip()
    visibility_filter = request.GET.get('visibility', '').strip()
    query = request.GET.get('q', '').strip()
    author_filter = request.GET.get('author', '').strip()
    tag_filter = request.GET.get('tag', '').strip().lstrip('#').lower()
    pinned_filter = request.GET.get('pinned', '').strip()
    from_date = parse_date(request.GET.get('from_date', '').strip())
    to_date = parse_date(request.GET.get('to_date', '').strip())
    
    updates = FieldUpdate.objects.select_related('author').prefetch_related('tags').all()

    # Visibility filtering
    visibility_q = Q(visibility="public") | Q(author=request.user)
    if viewer_profile.team_name:
        visibility_q |= Q(visibility="team", author__profile__team_name=viewer_profile.team_name)
    updates = updates.filter(visibility_q)

    # Apply all filters
    if category_filter:
        updates = updates.filter(category=category_filter)
    if status_filter:
        updates = updates.filter(status=status_filter)
    if visibility_filter:
        updates = updates.filter(visibility=visibility_filter)
    if query:
        updates = updates.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(author__username__icontains=query)
        )
    if author_filter:
        updates = updates.filter(author__username__icontains=author_filter)
    if tag_filter:
        updates = updates.filter(tags__name__iexact=tag_filter)
    if pinned_filter == 'only':
        updates = updates.filter(is_pinned=True)
    elif pinned_filter == 'exclude':
        updates = updates.filter(is_pinned=False)
    if from_date:
        updates = updates.filter(created_at__date__gte=from_date)
    if to_date:
        updates = updates.filter(created_at__date__lte=to_date)
    
    updates = updates.distinct().order_by('-is_pinned', '-created_at')

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="field_updates_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Title', 'Category', 'Status', 'Visibility', 
        'Author', 'Pinned', 'Tags', 'Content', 
        'Created At', 'Updated At'
    ])
    
    for update in updates:
        tags = ', '.join([f'#{tag.name}' for tag in update.tags.all()])
        writer.writerow([
            update.id,
            update.title,
            update.get_category_display(),
            update.get_status_display(),
            update.get_visibility_display(),
            update.author.username,
            'Yes' if update.is_pinned else 'No',
            tags,
            update.content,
            update.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            update.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    
    return response


@login_required
def save_search(request):
    """Save current filter parameters as a named search."""
    if request.method == 'POST':
        search_name = request.POST.get('search_name', '').strip()
        query_params = request.POST.get('query_params', '').strip()
        
        if search_name and query_params:
            SavedSearch.objects.update_or_create(
                user=request.user,
                name=search_name,
                defaults={'query_params': query_params}
            )
    return redirect('updates:feed')


@login_required
def delete_saved_search(request, pk):
    """Delete a saved search."""
    saved_search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    if request.method == 'POST':
        saved_search.delete()
    return redirect('updates:feed')


@login_required
def analytics_dashboard(request):
    """Display analytics dashboard with key metrics."""
    viewer_profile = get_or_create_profile(request.user)
    
    # Base queryset with visibility filtering
    visibility_q = Q(visibility="public") | Q(author=request.user)
    if viewer_profile.team_name:
        visibility_q |= Q(visibility="team", author__profile__team_name=viewer_profile.team_name)
    
    all_updates = FieldUpdate.objects.filter(visibility_q)
    
    # Total metrics
    total_updates = all_updates.count()
    total_comments = Comment.objects.filter(update__in=all_updates).count()
    total_reactions = Reaction.objects.filter(update__in=all_updates).count()
    total_users = User.objects.filter(updates__in=all_updates).distinct().count()
    
    # Category breakdown
    category_stats = []
    for category_code, category_name in FieldUpdate.CATEGORY_CHOICES:
        count = all_updates.filter(category=category_code).count()
        percentage = (count / total_updates * 100) if total_updates > 0 else 0
        category_stats.append({
            'code': category_code,
            'name': category_name,
            'count': count,
            'percentage': percentage
        })
    
    # Status breakdown
    status_stats = []
    for status_code, status_name in FieldUpdate.STATUS_CHOICES:
        count = all_updates.filter(status=status_code).count()
        percentage = (count / total_updates * 100) if total_updates > 0 else 0
        status_stats.append({
            'code': status_code,
            'name': status_name,
            'count': count,
            'percentage': percentage
        })
    
    # Visibility breakdown
    visibility_stats = []
    for visibility_code, visibility_name in FieldUpdate.VISIBILITY_CHOICES:
        count = all_updates.filter(visibility=visibility_code).count()
        percentage = (count / total_updates * 100) if total_updates > 0 else 0
        visibility_stats.append({
            'code': visibility_code,
            'name': visibility_name,
            'count': count,
            'percentage': percentage
        })
    
    # Top contributors (users with most posts)
    top_contributors = (
        User.objects.filter(updates__in=all_updates)
        .annotate(post_count=Count('updates'))
        .order_by('-post_count')[:10]
    )
    
    # Top tags
    top_tags = (
        Tag.objects.filter(updates__in=all_updates)
        .annotate(usage_count=Count('updates'))
        .order_by('-usage_count')[:10]
    )
    
    # Recent activity (last 7 days)
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    recent_updates = all_updates.filter(created_at__gte=seven_days_ago).count()
    recent_comments = Comment.objects.filter(
        update__in=all_updates,
        created_at__gte=seven_days_ago
    ).count()
    
    # Daily activity for the last 7 days
    daily_activity = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_count = all_updates.filter(
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()
        
        daily_activity.append({
            'date': day_start.strftime('%b %d'),
            'count': day_count
        })
    
    # Pinned updates count
    pinned_count = all_updates.filter(is_pinned=True).count()
    
    # Most reacted updates
    most_reacted = (
        all_updates.annotate(reaction_count=Count('reactions'))
        .order_by('-reaction_count')[:5]
    )
    
    # Most commented updates
    most_commented = (
        all_updates.annotate(comment_count=Count('comments'))
        .order_by('-comment_count')[:5]
    )
    
    return render(request, 'updates/analytics.html', {
        'total_updates': total_updates,
        'total_comments': total_comments,
        'total_reactions': total_reactions,
        'total_users': total_users,
        'category_stats': category_stats,
        'status_stats': status_stats,
        'visibility_stats': visibility_stats,
        'top_contributors': top_contributors,
        'top_tags': top_tags,
        'recent_updates': recent_updates,
        'recent_comments': recent_comments,
        'daily_activity': daily_activity,
        'pinned_count': pinned_count,
        'most_reacted': most_reacted,
        'most_commented': most_commented,
        'viewer_profile': viewer_profile,
    })
