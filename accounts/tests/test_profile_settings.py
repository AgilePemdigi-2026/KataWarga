"""Uji halaman profil dan pengaturan tampilan untuk semua peran."""
import pytest
from django.urls import reverse

from accounts.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="profil_user",
        email="profil@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=User.RolePengguna.ANALYST,
    )


def test_profile_page_renders_for_authenticated_user(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Profil Saya" in body
    assert user.username in body
    assert user.email in body
    assert reverse("accounts:settings") in body


def test_profile_updates_email_with_validation(client, user):
    other = User.objects.create_user(
        username="other_user",
        email="other@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=User.RolePengguna.TIM_DEVELOPER,
    )
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile"),
        {"email": "email.baru@katawarga.test"},
        follow=True,
    )
    user.refresh_from_db()

    assert response.status_code == 200
    assert user.email == "email.baru@katawarga.test"
    assert "Email profil berhasil diperbarui" in response.content.decode("utf-8")

    response = client.post(
        reverse("accounts:profile"),
        {"email": other.email.upper()},
        follow=True,
    )
    user.refresh_from_db()

    assert response.status_code == 200
    assert user.email == "email.baru@katawarga.test"
    assert "Email sudah digunakan akun lain" in response.content.decode("utf-8")


def test_settings_page_exposes_real_theme_controls(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:settings"))
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Pengaturan Tampilan" in body
    assert 'data-theme-option="dark"' in body
    assert 'data-theme-option="light"' in body
    assert "localStorage" in body or "browser ini" in body


def test_login_page_uses_shared_design_system(client):
    response = client.get(reverse("accounts:login"))
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "css/app.css" in body
    assert "js/app.js" in body
    assert "Masuk ke KataWarga" in body
