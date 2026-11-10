"""
Step definitions BDD — FR-DSH (Melihat Dashboard Overview) — Backlog #11.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers
from django.urls import reverse

from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint2/dashboard_overview.feature',
          'FR-DSH-01 Pengguna login melihat ringkasan metrik di dashboard (Happy Path)')
def test_fr_dsh_01_overview_happy_path():
    pass


@scenario('../sprint2/dashboard_overview.feature',
          'FR-DSH-02 Pengguna belum login dialihkan ke halaman login')
def test_fr_dsh_02_pengguna_belum_login():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class DashboardKonteks:
    def __init__(self):
        self.user = None
        self.response = None


@pytest.fixture
def dctx():
    return DashboardKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given('saya adalah pengguna terotentikasi yang sudah login', target_fixture='dctx')
def given_user_login(db, dev_user, client):
    dctx = DashboardKonteks()
    dctx.user = dev_user
    client.force_login(dev_user)
    return dctx


@given('sistem memiliki data ulasan, cluster, dan user story')
def given_data_sistem(db, ulasan_factory, cluster_factory, user_story_factory, backlog_item_factory):
    # Buat beberapa data pendukung metrik
    u = ulasan_factory('Aplikasi sering force close saat login')
    c = cluster_factory('Masalah Login', jumlah=5, status='TERVALIDASI')
    us = user_story_factory(cluster=c, prioritas='TINGGI', status='DISETUJUI')
    backlog_item_factory(user_story=us, status='SIAP_DIEKSEKUSI')


@given('saya adalah pengguna anonim yang belum login', target_fixture='dctx')
def given_user_anonim(db):
    dctx = DashboardKonteks()
    dctx.user = None
    return dctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('saya membuka halaman dashboard')
def when_buka_dashboard(dctx, db, client):
    dctx.response = client.get(reverse('dashboard:dashboard'))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then('saya melihat halaman dashboard dengan status 200')
def then_status_200(dctx):
    assert dctx.response.status_code == 200, (
        f"Diharapkan 200, tetapi mendapat {dctx.response.status_code}"
    )


@then('saya melihat metrik ringkasan ulasan, cluster, dan user story')
def then_metrik_ringkasan(dctx):
    metrics = dctx.response.context.get('metrics', {})
    assert metrics is not None, "Konteks metrics seharusnya ada di template"
    assert metrics.get('total_ulasan', 0) >= 1
    assert metrics.get('total_cluster', 0) >= 1
    assert metrics.get('total_user_story', 0) >= 1


@then('saya dialihkan ke halaman login')
def then_redirect_login(dctx):
    assert dctx.response.status_code == 302, (
        f"Pengguna belum login seharusnya diredirect (302), dapat {dctx.response.status_code}"
    )
    assert '/login/' in dctx.response.url
