from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'updates'

urlpatterns = [
    path('', RedirectView.as_view(url='/feed/', permanent=False)),
    path('feed/', views.feed, name='feed'),
    path('feed/export-csv/', views.export_feed_csv, name='export_csv'),
    path('feed/save-search/', views.save_search, name='save_search'),
    path('feed/delete-search/<int:pk>/', views.delete_saved_search, name='delete_saved_search'),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('profile/<int:user_id>/', views.user_profile, name='profile'),
    path('edit/<int:pk>/', views.edit_update, name='edit'),
    path('delete/<int:pk>/', views.delete_update, name='delete'),
]
