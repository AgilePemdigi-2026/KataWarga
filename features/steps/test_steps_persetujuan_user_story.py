"""
Step definitions BDD — FR-APP (Persetujuan User Story) — Backlog #8.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers

from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint1/persetujuan_user_story.feature',
          'FR-APP-01 Setujui user story berprioritas tinggi (Happy Path)')
def test_fr_app_01_setujui_happy_path():
    pass


@scenario('../sprint1/persetujuan_user_story.feature',
          'FR-APP-02 Abaikan user story berprioritas rendah')
def test_fr_app_02_abaikan():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class PersetujuanKonteks:
    def __init__(self):
        self.user_story = None


@pytest.fixture
def pctx():
    return PersetujuanKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given(parsers.parse('ada user story dengan kategori prioritas "{prioritas}" dan status "{status}"'),
       target_fixture='pctx')
def given_user_story(db, prioritas, status, user_story_factory):
    pctx = PersetujuanKonteks()
    pctx.user_story = user_story_factory(prioritas=prioritas, status=status)
    return pctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('Product Owner menyetujui user story tersebut')
def when_po_setujui(pctx, db, po_user):
    from stories.services.approval import setujui_user_story
    setujui_user_story(pctx.user_story, validator_user=po_user)
    pctx.user_story.refresh_from_db()


@when('Product Owner mengabaikan user story tersebut')
def when_po_abaikan(pctx, db, po_user):
    from stories.services.approval import abaikan_user_story
    abaikan_user_story(pctx.user_story, alasan='Prioritas terlalu rendah')
    pctx.user_story.refresh_from_db()


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('status user story berubah menjadi "{status_expected}"'))
def then_status_user_story(pctx, db, status_expected):
    assert pctx.user_story.status_persetujuan == status_expected, (
        f"Status seharusnya '{status_expected}', "
        f"tetapi '{pctx.user_story.status_persetujuan}'"
    )


@then('tanggal persetujuan tercatat')
def then_tanggal_persetujuan(pctx, db):
    assert pctx.user_story.tanggal_persetujuan is not None, (
        "Tanggal persetujuan seharusnya tercatat setelah disetujui"
    )


@then('user story tidak masuk ke backlog')
def then_tidak_di_backlog(pctx, db):
    from backlog.models import BacklogItem
    exists = BacklogItem.objects.filter(user_story=pctx.user_story).exists()
    assert not exists, "User story yang diabaikan seharusnya tidak masuk backlog"

