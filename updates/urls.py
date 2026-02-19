from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'updates'

urlpatterns = [
    path('', RedirectView.as_view(url='/feed/', permanent=False)),
    path('feed/', views.feed, name='feed'),
]
