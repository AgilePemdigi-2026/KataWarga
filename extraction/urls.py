from django.urls import path
from . import views

app_name = 'extraction'

urlpatterns = [
    path('validasi-ekstraksi/', views.validasi_list_view, name='validasi_list'),
    path('validasi-ekstraksi/<int:pk>/setujui/', views.setujui_cluster_view, name='setujui_cluster'),
    path('validasi-ekstraksi/<int:pk>/tolak/', views.tolak_cluster_view, name='tolak_cluster'),
]
