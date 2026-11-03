from django.urls import path, re_path
from . import views

app_name = 'backlog'

urlpatterns = [
    re_path(r'^backlog/?$', views.backlog_list_view, name='list'),
    path('backlog/<int:pk>/mulai', views.mulai_kerjakan_view, name='mulai'),
    path('backlog/<int:pk>/selesai', views.tandai_selesai_view, name='selesai'),
]
