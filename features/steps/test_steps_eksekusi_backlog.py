"""
Step definitions BDD — FR-BKL (Eksekusi Backlog) — Backlog #10.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers
from django.urls import reverse

from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint1/eksekusi_backlog.feature',
          'FR-BKL-01 Tandai item backlog mulai dikerjakan (Happy Path)')
def test_fr_bkl_01_mulai_happy_path():
    pass


@scenario('../sprint1/eksekusi_backlog.feature',
          'FR-BKL-02 Tandai item backlog selesai dikerjakan')
def test_fr_bkl_02_selesai():
    pass


@scenario('../sprint1/eksekusi_backlog.feature',
          'FR-BKL-03 Non-developer tidak bisa mengeksekusi backlog')
def test_fr_bkl_03_akses_ditolak():
    pass


@scenario('../sprint1/eksekusi_backlog.feature',
          'FR-BKL-04 Transisi tidak valid ditolak')
def test_fr_bkl_04_transisi_invalid():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class BacklogKonteks:
    def __init__(self):
        self.item = None
        self.user = None
        self.response = None
        self.error_msg = None


@pytest.fixture
def bctx():
    return BacklogKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given(parsers.parse('ada backlog item dengan status "{status}"'),
       target_fixture='bctx')
def given_backlog_item(db, status, backlog_item_factory, user_story_factory):
    from stories.models import UserStory
    bctx = BacklogKonteks()
    us = user_story_factory(status=UserStory.StatusPersetujuan.DISETUJUI)
    bctx.item = backlog_item_factory(user_story=us, status=status)
    return bctx


@given(parsers.parse('saya adalah pengguna dengan peran "{peran}"'))
def given_peran_bkl(bctx, db, peran):
    from accounts.models import User
    user, _ = User.objects.get_or_create(
        username=f'bdd_bkl_{peran.lower()}',
        defaults={'role': peran, 'email': f'bkl_{peran.lower()}@katawarga.test'}
    )
    user.set_password('testpass123')
    user.save()
    bctx.user = user


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('Tim Developer menekan tombol Mulai Kerjakan')
def when_mulai_kerjakan(bctx, db, dev_user, client):
    client.force_login(dev_user)
    session = client.session
    session['acting_role'] = 'TIM_DEVELOPER'
    session.save()
    url = reverse('backlog:mulai', kwargs={'pk': bctx.item.pk})
    bctx.response = client.post(url, follow=True)
    bctx.item.refresh_from_db()


@when('Tim Developer menekan tombol Tandai Selesai')
def when_tandai_selesai(bctx, db, dev_user, client):
    client.force_login(dev_user)
    session = client.session
    session['acting_role'] = 'TIM_DEVELOPER'
    session.save()
    url = reverse('backlog:selesai', kwargs={'pk': bctx.item.pk})
    bctx.response = client.post(url, follow=True)
    bctx.item.refresh_from_db()


@when('saya mencoba memulai pengerjaan item backlog')
def when_non_dev_mulai(bctx, db, client):
    client.force_login(bctx.user)
    session = client.session
    session['acting_role'] = bctx.user.role
    session.save()
    url = reverse('backlog:mulai', kwargs={'pk': bctx.item.pk})
    bctx.response = client.post(url)


@when('Tim Developer menekan tombol Tandai Selesai secara langsung')
def when_tandai_selesai_langsung(bctx, db, dev_user):
    """Mencoba transisi SIAP_DIEKSEKUSI -> SELESAI langsung (tidak valid)."""
    from backlog.services.execution import tandai_selesai, BacklogExecutionError
    try:
        tandai_selesai(bctx.item, dev_user)
    except BacklogExecutionError as exc:
        bctx.error_msg = str(exc)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('status backlog item berubah menjadi "{status_expected}"'))
def then_status_backlog(bctx, db, status_expected):
    assert bctx.item.status_eksekusi == status_expected, (
        f"Status backlog seharusnya '{status_expected}', "
        f"tetapi '{bctx.item.status_eksekusi}'"
    )


@then('waktu mulai dikerjakan tercatat')
def then_waktu_mulai(bctx, db):
    assert bctx.item.tanggal_mulai_dikerjakan is not None, (
        "Waktu mulai dikerjakan seharusnya tercatat"
    )


@then('saya menerima respons 403 Forbidden')
def then_403_bkl(bctx, db):
    assert bctx.response.status_code == 403, (
        f"Diharapkan 403, dapat {bctx.response.status_code}"
    )


@then('sistem menolak dengan pesan error transisi tidak valid')
def then_error_transisi(bctx, db):
    assert bctx.error_msg is not None, (
        "Seharusnya ada error message untuk transisi yang tidak valid"
    )
