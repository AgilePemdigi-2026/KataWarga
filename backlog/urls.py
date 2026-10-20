from django.urls import re_path
from . import views

app_name = 'backlog'

urlpatterns = [
    re_path(r'^backlog/?$', views.backlog_list_view, name='list'),
]
