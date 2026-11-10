from django.urls import path, re_path

from . import views

app_name = 'backlog'

urlpatterns = [
    re_path(r'^backlog/?$', views.backlog_list_view, name='list'),
    path('backlog/detail/', views.backlog_detail_latest_view, name='detail_latest'),
    path('backlog/<int:pk>/', views.backlog_detail_view, name='detail'),
    re_path(r'^backlog/(?P<pk>\d+)/mulai/?$', views.mulai_kerjakan_view, name='mulai'),
    re_path(r'^backlog/(?P<pk>\d+)/selesai/?$', views.tandai_selesai_view, name='selesai'),
]
