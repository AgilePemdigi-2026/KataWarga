"""
Step definitions BDD — FR-AUT (Kelola Akses Role) — Backlog #4.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers

from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint2/kelola_role.feature',
          'FR-AUT-01 Requirements Engineer mengubah role pengguna (Happy Path)')
def test_fr_aut_01_ubah_role_happy_path():
    pass


@scenario('../sprint2/kelola_role.feature',
          'FR-AUT-02 Non-RE tidak bisa mengakses halaman kelola role')
def test_fr_aut_02_akses_ditolak():
    pass


@scenario('../sprint2/kelola_role.feature',
          'FR-AUT-03 Switch acting role di dev mode')
def test_fr_aut_03_switch_acting_role():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class RoleKonteks:
    def __init__(self):
        self.aktor = None
        self.target_user = None
        self.role_baru = None
        self.response = None


@pytest.fixture
def rctx():
    return RoleKonteks()


# ---------------------------------------------------------------------------
# Given — FR-AUT-01
# ---------------------------------------------------------------------------

@given(parsers.parse('saya adalah pengguna dengan peran "{peran}"'),
       target_fixture='rctx')
def given_aktor_peran(db, peran):
    from accounts.models import User
    rctx = RoleKonteks()
    user, _ = User.objects.get_or_create(
        username=f'bdd_aktor_{peran.lower()}',
        defaults={'role': peran, 'email': f'aktor_{peran.lower()}@katawarga.test'}
    )
    user.set_password('testpass123')
    user.save()
    rctx.aktor = user
    return rctx


@given(parsers.parse('ada pengguna lain dengan peran "{peran}"'))
def given_target_pengguna(rctx, db, peran):
    from accounts.models import User
    target, _ = User.objects.get_or_create(
        username='bdd_target_user',
        defaults={'role': peran, 'email': 'target@katawarga.test'}
    )
    target.set_password('testpass123')
    target.save()
    rctx.target_user = target


@given('saya adalah pengguna dalam mode dev', target_fixture='rctx')
def given_dev_mode(db):
    from accounts.models import User
    rctx = RoleKonteks()
    user, _ = User.objects.get_or_create(
        username='bdd_dev_mode_user',
        defaults={'role': User.RolePengguna.REQUIREMENTS_ENGINEER,
                  'email': 'devmode@katawarga.test'}
    )
    user.set_password('testpass123')
    user.save()
    rctx.aktor = user
    return rctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when(parsers.parse('saya mengubah role pengguna tersebut menjadi "{role_baru}"'))
def when_ubah_role(rctx, db, client, role_baru):
    rctx.role_baru = role_baru
    client.force_login(rctx.aktor)
    session = client.session
    session['acting_role'] = rctx.aktor.role
    session.save()
    rctx.response = client.post(
        f'/kelola-role/{rctx.target_user.pk}/ubah/',
        data={'role': role_baru},
    )
    rctx.target_user.refresh_from_db()


@when('saya mengakses halaman kelola role')
def when_akses_kelola_role(rctx, db, client):
    client.force_login(rctx.aktor)
    session = client.session
    session['acting_role'] = rctx.aktor.role
    session.save()
    rctx.response = client.get('/kelola-role/')


@when(parsers.parse('saya berpindah acting role ke "{role_tujuan}"'))
def when_switch_acting_role(rctx, db, client, role_tujuan):
    client.force_login(rctx.aktor)
    rctx.response = client.post(
        '/kelola-role/switch/',
        data={'acting_role': role_tujuan},
    )
    rctx.role_tujuan = role_tujuan


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('role pengguna berhasil diubah menjadi "{role_expected}"'))
def then_role_berubah(rctx, db, role_expected):
    assert rctx.target_user.role == role_expected, (
        f"Role seharusnya '{role_expected}', tetapi '{rctx.target_user.role}'"
    )


@then('saya menerima respons 403 Forbidden')
def then_403_role(rctx, db):
    assert rctx.response.status_code == 403, (
        f"Diharapkan 403, dapat {rctx.response.status_code}"
    )


@then(parsers.parse('acting role aktif menjadi "{role_expected}"'))
def then_acting_role_aktif(rctx, db, client, role_expected):
    # Verifikasi session di client setelah switch
    # Switch role mengembalikan redirect; cek session
    assert rctx.response.status_code in [200, 302], (
        f"Respons switch role seharusnya 200 atau 302, dapat {rctx.response.status_code}"
    )
    # Akses session melalui client setelah switch
    session_role = client.session.get('acting_role', '')
    assert session_role == role_expected, (
        f"Acting role di session seharusnya '{role_expected}', "
        f"tetapi '{session_role}'"
    )

