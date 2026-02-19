from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'updates'

urlpatterns = [
    path('', RedirectView.as_view(url='/feed/', permanent=False)),
    path('feed/', views.feed, name='feed'),
    path('profile/<int:user_id>/', views.user_profile, name='profile'),
    path('edit/<int:pk>/', views.edit_update, name='edit'),
    path('delete/<int:pk>/', views.delete_update, name='delete'),
]
