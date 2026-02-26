from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django import forms
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_date
from collections import Counter

from .models import Comment, FieldUpdate, Reaction, Tag, UpdateAuditLog
from .forms import FieldUpdateForm


def log_update_event(*, actor, action, update_obj=None, metadata=""):
    UpdateAuditLog.objects.create(
        field_update=update_obj,
        actor=actor,
        action=action,
        metadata=metadata,
        update_title_snapshot=(update_obj.title if update_obj else ""),
    )


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
    if request.method == 'POST':
        action = request.POST.get("action", "create_update")
        if action == "add_comment":
            update = get_object_or_404(FieldUpdate, pk=request.POST.get("update_id"))
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

        form = FieldUpdateForm(request.POST)
        if form.is_valid():
            field_update = form.save(commit=False)
            field_update.author = request.user
            field_update.save()
            log_update_event(
                actor=request.user,
                action="create",
                update_obj=field_update,
                metadata=f"status={field_update.status};category={field_update.category};pinned={field_update.is_pinned}",
            )
            return redirect('updates:feed')
    else:
        form = FieldUpdateForm()
    
    # Get filters from GET parameters
    category_filter = request.GET.get('category')
    status_filter = request.GET.get('status', '').strip()
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
    ).all()

    # Filter updates by category if specified
    if category_filter:
        updates = updates.filter(category=category_filter)
    if status_filter:
        updates = updates.filter(status=status_filter)

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

    return render(request, 'updates/feed.html', {
        'form': form,
        'updates': page_updates,
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'author_filter': author_filter,
        'tag_filter': tag_filter,
        'pinned_filter': pinned_filter,
        'from_date_value': request.GET.get('from_date', '').strip(),
        'to_date_value': request.GET.get('to_date', '').strip(),
        'selected_category': category_filter,
        'popular_tags': Tag.objects.order_by('name')[:15],
        'reaction_choices': Reaction.REACTION_CHOICES,
    })


@login_required
def edit_update(request, pk):
    update = get_object_or_404(FieldUpdate, pk=pk)
    
    # Check if user is the author
    if update.author != request.user:
        return HttpResponseForbidden("You don't have permission to edit this update.")
    
    if request.method == 'POST':
        previous_title = update.title
        previous_category = update.category
        previous_status = update.status
        previous_is_pinned = update.is_pinned
        form = FieldUpdateForm(request.POST, instance=update)
        if form.is_valid():
            edited_update = form.save()
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
    if update.author != request.user:
        return HttpResponseForbidden("You don't have permission to delete this update.")
    
    if request.method == 'POST':
        log_update_event(
            actor=request.user,
            action="delete",
            update_obj=update,
            metadata=f"status={update.status};category={update.category}",
        )
        update.delete()
        return redirect('updates:feed')
    
    return render(request, 'updates/confirm_delete.html', {
        'update': update
    })


@login_required
def user_profile(request, user_id):
    profile_user = get_object_or_404(User, pk=user_id)
    user_updates = FieldUpdate.objects.filter(author=profile_user).order_by('-created_at')
    post_count = user_updates.count()
    
    return render(request, 'updates/profile.html', {
        'profile_user': profile_user,
        'user_updates': user_updates,
        'post_count': post_count
    })
