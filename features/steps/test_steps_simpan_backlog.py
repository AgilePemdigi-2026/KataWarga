"""
Step definitions BDD — FR-SIM (Simpan User Story ke Backlog) — Backlog #9.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers
from unittest.mock import patch

from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint1/simpan_backlog.feature',
          'FR-SIM-01 User story yang disetujui tersimpan ke backlog (Happy Path)')
def test_fr_sim_01_simpan_happy_path():
    pass


@scenario('../sprint1/simpan_backlog.feature',
          'FR-SIM-02 User story yang sudah ada di backlog tidak terduplikasi')
def test_fr_sim_02_no_duplikasi():
    pass


@scenario('../sprint1/simpan_backlog.feature',
          'FR-SIM-03 Gagal menyimpan ke backlog melakukan rollback')
def test_fr_sim_03_rollback():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class SimKonteks:
    def __init__(self):
        self.user_story = None
        self.error_raised = False


@pytest.fixture
def simctx():
    return SimKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given(parsers.parse('ada user story dengan status "{status}"'),
       target_fixture='simctx')
def given_user_story_menunggu(db, status, user_story_factory):
    simctx = SimKonteks()
    simctx.user_story = user_story_factory(status=status)
    return simctx


@given('ada user story yang sudah disetujui dan masuk ke backlog',
       target_fixture='simctx')
def given_user_story_sudah_di_backlog(db, user_story_factory, backlog_item_factory):
    simctx = SimKonteks()
    us = user_story_factory(status='DISETUJUI')
    # Sudah ada di backlog
    backlog_item_factory(user_story=us, status='SIAP_DIEKSEKUSI')
    simctx.user_story = us
    return simctx


@given('penyimpanan backlog gagal karena kesalahan sistem')
def given_backlog_gagal(simctx):
    # Flag untuk mock — ditangani di step When
    simctx.mock_gagal = True


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('Product Owner menyetujui user story tersebut')
def when_po_setujui_sim(simctx, db, po_user):
    from stories.services.approval import setujui_user_story, ApprovalError
    if getattr(simctx, 'mock_gagal', False):
        with patch('backlog.services.saver.BacklogItem.objects.get_or_create',
                   side_effect=Exception('Database tidak tersedia')):
            try:
                setujui_user_story(simctx.user_story, validator_user=po_user)
            except (ApprovalError, Exception):
                simctx.error_raised = True
    else:
        setujui_user_story(simctx.user_story, validator_user=po_user)
    simctx.user_story.refresh_from_db()


@when('sistem mencoba menyimpan user story yang sama ke backlog lagi')
def when_simpan_lagi(simctx, db):
    from backlog.services.saver import save_to_backlog
    # Panggil save_to_backlog lagi — get_or_create mencegah duplikasi
    save_to_backlog(simctx.user_story)


@when('saya membuka halaman backlog')
def when_buka_backlog(simctx, db, client):
    simctx.response_backlog = client.get('/backlog/')


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('user story tersimpan di backlog dengan status "{status_expected}"'))
def then_tersimpan_backlog(simctx, db, status_expected):
    from backlog.models import BacklogItem
    item = BacklogItem.objects.filter(user_story=simctx.user_story).first()
    assert item is not None, "BacklogItem seharusnya ada setelah user story disetujui"
    assert item.status_eksekusi == status_expected, (
        f"Status backlog seharusnya '{status_expected}', tetapi '{item.status_eksekusi}'"
    )


@then('backlog hanya berisi satu item untuk user story tersebut')
def then_tidak_duplikasi(simctx, db):
    from backlog.models import BacklogItem
    count = BacklogItem.objects.filter(user_story=simctx.user_story).count()
    assert count == 1, f"Backlog seharusnya hanya 1 item, tetapi ada {count}"


@then(parsers.parse('status user story tetap "{status_expected}"'))
def then_status_tetap(simctx, db, status_expected):
    assert simctx.user_story.status_persetujuan == status_expected, (
        f"Status seharusnya tetap '{status_expected}', "
        f"tetapi '{simctx.user_story.status_persetujuan}'"
    )


@then('backlog tidak bertambah item baru')
def then_backlog_tidak_bertambah(simctx, db):
    from backlog.models import BacklogItem
    item = BacklogItem.objects.filter(user_story=simctx.user_story).first()
    assert item is None, "Backlog seharusnya kosong karena penyimpanan gagal"

