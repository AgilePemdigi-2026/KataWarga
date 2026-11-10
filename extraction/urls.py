from django.urls import path

from . import views

app_name = 'extraction'

urlpatterns = [
    # Extraction Pipeline (RE: kelola, Analyst: read-only)
    path('ekstraksi/', views.pipeline_view, name='pipeline'),
    path('ekstraksi/jalankan/', views.run_pipeline_view, name='run_pipeline'),

    # Clustering / monitoring cluster (RE & Analyst)
    path('clustering/', views.cluster_list_view, name='cluster_list'),
    path('clustering/<int:pk>/', views.cluster_detail_view, name='cluster_detail'),

    # Validasi khusus Analyst
    path('validasi-ekstraksi/', views.validasi_list_view, name='validasi_list'),
    path(
        'validasi-ekstraksi/<int:pk>/setujui/',
        views.setujui_cluster_view,
        name='setujui_cluster',
    ),
    path(
        'validasi-ekstraksi/<int:pk>/tolak/',
        views.tolak_cluster_view,
        name='tolak_cluster',
    ),
]
