from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    path("kelola-role/", views.kelola_role_view, name="kelola_role"),
    path(
        "kelola-role/<int:pk>/ubah/",
        views.ubah_role_view,
        name="ubah_role",
    ),
    path(
        "kelola-role/<int:pk>/aktifasi/",
        views.toggle_active_view,
        name="toggle_active",
    ),
    path(
        "kelola-role/switch/",
        views.switch_acting_role_view,
        name="switch_role",
    ),
]