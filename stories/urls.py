"""
URL patterns untuk app stories (§9, Gherkin acceptance routes).
"""
from django.urls import path, re_path

from . import views

app_name = 'stories'

urlpatterns = [
    re_path(r'^susun-user-story/?$', views.susun_user_story_view, name='susun'),
    re_path(r'^user-story/?$', views.user_story_board_view, name='board'),
    path('user-story/detail/', views.user_story_detail_latest_view, name='detail_latest'),
    re_path(r'^user-story/(?P<pk>\d+)/?$', views.user_story_detail_view, name='detail'),
    path('user-story/<int:pk>/setujui', views.setujui_view, name='setujui'),
    path('user-story/<int:pk>/abaikan', views.abaikan_view, name='abaikan'),
]
