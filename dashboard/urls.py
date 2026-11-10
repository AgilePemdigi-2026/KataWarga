from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    # UI guideline menempatkan Dashboard Overview di root aplikasi.
    path('', views.overview_view, name='overview'),
    # Alias eksplisit agar /dashboard/ juga dapat dibuka.
    path('dashboard/', views.overview_view, name='dashboard'),
]
