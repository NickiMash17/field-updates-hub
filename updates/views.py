from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django import forms
from django.http import HttpResponseForbidden
from .models import FieldUpdate
from .forms import FieldUpdateForm


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
        form = FieldUpdateForm(request.POST)
        if form.is_valid():
            field_update = form.save(commit=False)
            field_update.author = request.user
            field_update.save()
            return redirect('updates:feed')
    else:
        form = FieldUpdateForm()
    
    # Get category filter from GET parameters
    category_filter = request.GET.get('category')
    
    # Filter updates by category if specified
    if category_filter:
        updates = FieldUpdate.objects.filter(category=category_filter)
    else:
        updates = FieldUpdate.objects.all()
    
    # Order by newest first (handled by model Meta)
    updates = updates.order_by('-created_at')
    
    return render(request, 'updates/feed.html', {
        'form': form,
        'updates': updates
    })


@login_required
def edit_update(request, pk):
    update = get_object_or_404(FieldUpdate, pk=pk)
    
    # Check if user is the author
    if update.author != request.user:
        return HttpResponseForbidden("You don't have permission to edit this update.")
    
    if request.method == 'POST':
        form = FieldUpdateForm(request.POST, instance=update)
        if form.is_valid():
            form.save()
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
