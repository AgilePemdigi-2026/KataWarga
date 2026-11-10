"""
Step definitions BDD — FR-AUT (Autentikasi: Sign Up, Login, Logout) — Backlog #1, #2, #3.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers
from django.urls import reverse
from django.contrib.auth import get_user_model

from features.conftest import *  # noqa: F401,F403

User = get_user_model()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-04 Pengguna baru mendaftar akun (Sign Up Happy Path)')
def test_fr_aut_04_signup_happy_path():
    pass


@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-05 Pendaftaran gagal jika email sudah terdaftar')
def test_fr_aut_05_signup_email_duplikat():
    pass


@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-06 Pengguna aktif berhasil login (Login Happy Path)')
def test_fr_aut_06_login_happy_path():
    pass


@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-07 Login ditolak jika password salah')
def test_fr_aut_07_login_gagal():
    pass


@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-08 Pengguna login melakukan logout via POST')
def test_fr_aut_08_logout_post():
    pass


@scenario('../sprint3/autentikasi.feature',
          'FR-AUT-09 Request GET pada logout ditolak')
def test_fr_aut_09_logout_get_ditolak():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class AuthKonteks:
    def __init__(self):
        self.user = None
        self.response = None
        self.username_mendaftar = None


@pytest.fixture
def actx():
    return AuthKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given('saya adalah pengunjung yang belum memiliki akun', target_fixture='actx')
def given_pengunjung_anonim():
    return AuthKonteks()


@given(parsers.parse('ada pengguna terdaftar dengan email "{email}"'),
       target_fixture='actx')
def given_pengguna_ada_email(db, email):
    actx = AuthKonteks()
    user = User.objects.create_user(
        username='user_existing',
        email=email,
        password='Password123!',
    )
    actx.user = user
    return actx


@given(parsers.parse('ada pengguna aktif dengan username "{username}" dan password "{password}"'),
       target_fixture='actx')
def given_pengguna_aktif(db, username, password):
    actx = AuthKonteks()
    user = User.objects.create_user(
        username=username,
        email=f'{username}@katawarga.test',
        password=password,
        role=User.RolePengguna.TIM_DEVELOPER,
        is_active=True,
    )
    actx.user = user
    return actx


@given('saya adalah pengguna yang sudah login', target_fixture='actx')
def given_user_sudah_login(db, dev_user, client):
    actx = AuthKonteks()
    actx.user = dev_user
    client.force_login(dev_user)
    return actx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when(parsers.parse('saya mendaftar dengan username "{username}", email "{email}", dan password "{password}"'))
def when_mendaftar(actx, db, client, username, email, password):
    actx.username_mendaftar = username
    actx.response = client.post(
        reverse('accounts:signup'),
        data={
            'username': username,
            'email': email,
            'password1': password,
            'password2': password,
        },
    )


@when(parsers.parse('saya mendaftar dengan username "{username}" dan email "{email}"'))
def when_mendaftar_duplikat(actx, db, client, username, email):
    actx.username_mendaftar = username
    actx.response = client.post(
        reverse('accounts:signup'),
        data={
            'username': username,
            'email': email,
            'password1': 'Rahasia123!',
            'password2': 'Rahasia123!',
        },
    )


@when(parsers.parse('saya melakukan login dengan username "{username}" dan password "{password}"'))
def when_login_sukses(actx, db, client, username, password):
    actx.response = client.post(
        reverse('accounts:login'),
        data={
            'username': username,
            'password': password,
        },
    )


@when(parsers.parse('saya melakukan login dengan username "{username}" dan password salah "{password}"'))
def when_login_salah(actx, db, client, username, password):
    actx.response = client.post(
        reverse('accounts:login'),
        data={
            'username': username,
            'password': password,
        },
    )


@when('saya melakukan logout dengan request POST')
def when_logout_post(actx, db, client):
    actx.response = client.post(reverse('accounts:logout'))


@when('saya mengakses logout dengan request GET')
def when_logout_get(actx, db, client):
    actx.response = client.get(reverse('accounts:logout'))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('akun "{username}" berhasil dibuat di database'))
def then_akun_terbuat(actx, db, username):
    user = User.objects.filter(username=username).first()
    assert user is not None, f"Akun {username} seharusnya berhasil dibuat di database"


@then('saya dialihkan ke halaman login')
def then_dialihkan_ke_login(actx):
    assert actx.response.status_code == 302, (
        f"Diharapkan 302 redirect, tetapi mendapat {actx.response.status_code}"
    )
    assert reverse('accounts:login') in actx.response.url


@then(parsers.parse('sistem menolak pendaftaran dan akun "{username}" tidak dibuat'))
def then_pendaftaran_ditolak(actx, db, username):
    # Form tidak valid (status 200 dengan error message)
    assert actx.response.status_code == 200
    user = User.objects.filter(username=username).first()
    assert user is None, f"Akun {username} seharusnya tidak boleh dibuat"


@then('login berhasil dan saya dialihkan ke halaman utama')
def then_login_berhasil(actx):
    assert actx.response.status_code == 302, (
        f"Login berhasil seharusnya redirect (302), mendapat {actx.response.status_code}"
    )


@then(parsers.parse('sesi pengguna "{username}" aktif'))
def then_sesi_aktif(actx, db, client, username):
    user = User.objects.get(username=username)
    assert client.session.get('_auth_user_id') == str(user.pk)


@then('login ditolak dan saya tetap di halaman login')
def then_login_ditolak(actx, client):
    assert actx.response.status_code == 200
    assert '_auth_user_id' not in client.session


@then('sesi login berakhir dan saya dialihkan ke halaman login')
def then_sesi_logout(actx, client):
    assert actx.response.status_code == 302
    assert reverse('accounts:login') in actx.response.url
    assert '_auth_user_id' not in client.session


@then('saya menerima respons 403 Forbidden')
def then_403_logout(actx):
    assert actx.response.status_code == 403, (
        f"Logout via GET harus 403 Forbidden, dapat {actx.response.status_code}"
    )

