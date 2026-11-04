from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('kelola-role/', views.kelola_role_view, name='kelola_role'),
    path('kelola-role/<int:pk>/ubah/', views.ubah_role_view, name='ubah_role'),
    path('kelola-role/switch/', views.switch_acting_role_view, name='switch_role'),
]
