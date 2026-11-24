from django.urls import path

from . import api, views

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

    # API JSON (bagian E) — format respons seragam, lihat extraction/api.py
    path('api/v1/ringkasan/', api.ringkasan, name='api_ringkasan'),
    path('api/v1/ulasan/', api.ulasan_list, name='api_ulasan'),
    path('api/v1/ekstraksi/', api.ekstraksi_list, name='api_ekstraksi_list'),
    path('api/v1/ekstraksi/<int:pk>/', api.ekstraksi_detail, name='api_ekstraksi_detail'),
    path('api/v1/ekstraksi/<int:pk>/riwayat/', api.ekstraksi_riwayat, name='api_ekstraksi_riwayat'),
    path('api/v1/ekstraksi/<int:pk>/setujui/', api.ekstraksi_setujui, name='api_ekstraksi_setujui'),
    path('api/v1/ekstraksi/<int:pk>/tolak/', api.ekstraksi_tolak, name='api_ekstraksi_tolak'),
    path('api/v1/ekstraksi/<int:pk>/perbaiki/', api.ekstraksi_perbaiki, name='api_ekstraksi_perbaiki'),
    path('api/v1/cluster/', api.cluster_list, name='api_cluster_list'),
    path('api/v1/cluster/<int:pk>/', api.cluster_detail, name='api_cluster_detail'),
    path('api/v1/cluster/<int:pk>/setujui/', api.cluster_setujui, name='api_cluster_setujui'),
    path('api/v1/cluster/<int:pk>/tolak/', api.cluster_tolak, name='api_cluster_tolak'),
]
