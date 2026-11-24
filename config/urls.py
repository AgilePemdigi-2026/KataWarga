"""KataWarga — Root URL configuration."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include


def health(request):
    """Pemeriksaan kesehatan untuk Coolify/server kampus (tanpa akses basis data)."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('health', health, name='health'),
    path('health/', health),
    path('admin/', admin.site.urls),
    path('', include('stories.urls')),
    path('', include('dashboard.urls')),
    path('', include('accounts.urls')),
    path('', include('extraction.urls')),
    path('', include('backlog.urls')),
    path('', include('reviews.urls')),
]
