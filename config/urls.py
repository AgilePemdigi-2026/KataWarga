"""KataWarga — Root URL configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('stories.urls')),
    path('', include('dashboard.urls')),
    path('', include('accounts.urls')),
    path('', include('extraction.urls')),
    path('', include('backlog.urls')),
]
