from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django import forms
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
        return redirect("feed")


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('feed')
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
            return redirect('feed')
    else:
        form = FieldUpdateForm()
    
    # Get all field updates, ordered by newest first (handled by model Meta)
    updates = FieldUpdate.objects.all()
    
    return render(request, 'updates/feed.html', {
        'form': form,
        'updates': updates
    })
