"""
Step definitions BDD — FR-VAL (Validasi Hasil Ekstraksi) — Backlog #6.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers
from django.urls import reverse

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services.validation import setujui_cluster, tolak_cluster
from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint2/validasi_ekstraksi.feature',
          'FR-VAL-01 Setujui hasil ekstraksi yang valid (Happy Path)')
def test_fr_val_01_setujui_happy_path():
    pass


@scenario('../sprint2/validasi_ekstraksi.feature',
          'FR-VAL-02 Tolak hasil ekstraksi yang tidak valid')
def test_fr_val_02_tolak():
    pass


@scenario('../sprint2/validasi_ekstraksi.feature',
          'FR-VAL-03 Non-Analyst tidak bisa mengakses validasi')
def test_fr_val_03_akses_ditolak():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class ValidasiKonteks:
    def __init__(self):
        self.cluster = None
        self.user = None
        self.response = None


@pytest.fixture
def vctx():
    return ValidasiKonteks()


# ---------------------------------------------------------------------------
# Given — FR-VAL-01 & FR-VAL-02
# ---------------------------------------------------------------------------

@given(parsers.parse('saya memiliki cluster dengan status "{status}"'),
       target_fixture='vctx')
def given_cluster_menunggu(db, cluster_factory, status):
    vctx = ValidasiKonteks()
    vctx.cluster = cluster_factory(nama='Gagal Login', jumlah=1, status=status)
    return vctx


@given(parsers.parse('field "who" berisi "{nilai}"'))
def given_field_who(vctx, db, hasil_ekstraksi_factory, nilai):
    he = hasil_ekstraksi_factory(teks_who=nilai, teks_what='gagal login')
    ClusterAnggota.objects.create(cluster=vctx.cluster, hasil_ekstraksi=he)


@given(parsers.parse('field "what" berisi "{nilai}"'))
def given_field_what(vctx, db, nilai):
    pass


@given('field "who" kosong')
def given_field_who_kosong(vctx, db, hasil_ekstraksi_factory):
    he = hasil_ekstraksi_factory(teks_who='', teks_what='masalah umum')
    ClusterAnggota.objects.create(cluster=vctx.cluster, hasil_ekstraksi=he)


# ---------------------------------------------------------------------------
# Given — FR-VAL-03
# ---------------------------------------------------------------------------

@given(parsers.parse('saya adalah pengguna dengan peran "{peran}"'),
       target_fixture='vctx')
def given_pengguna_peran(db, peran, cluster_factory):
    from accounts.models import User
    vctx = ValidasiKonteks()
    user, _ = User.objects.get_or_create(
        username=f'bdd_{peran.lower()}',
        defaults={'role': peran, 'email': f'{peran.lower()}@katawarga.test'}
    )
    user.set_password('testpass123')
    user.save()
    vctx.user = user
    vctx.cluster = cluster_factory()
    return vctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('saya menyetujui cluster tersebut sebagai Analyst')
def when_setujui_cluster(vctx, db, analyst_user):
    setujui_cluster(vctx.cluster, validator_user=analyst_user)
    vctx.cluster.refresh_from_db()


@when('saya menolak cluster tersebut sebagai Analyst')
def when_tolak_cluster(vctx, db, analyst_user):
    tolak_cluster(vctx.cluster, validator_user=analyst_user)
    vctx.cluster.refresh_from_db()


@when('saya mengakses halaman validasi ekstraksi')
def when_akses_validasi(vctx, db, client):
    client.force_login(vctx.user)
    session = client.session
    session['acting_role'] = vctx.user.role
    session.save()
    vctx.response = client.get(reverse('extraction:validasi_list'))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('status cluster berubah menjadi "{status_expected}"'))
def then_status_cluster(vctx, db, status_expected):
    assert vctx.cluster.status_cluster == status_expected, (
        f"Status cluster seharusnya '{status_expected}', "
        f"tetapi '{vctx.cluster.status_cluster}'"
    )


@then('cluster tidak muncul di antrian menunggu penyusunan')
def then_cluster_tidak_di_antrian(vctx, db):
    antrian = Cluster.objects.filter(
        status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        pk=vctx.cluster.pk,
    )
    assert not antrian.exists(), "Cluster seharusnya tidak ada di antrian menunggu validasi"


@then('saya menerima respons 403 Forbidden')
def then_403_validasi(vctx, db):
    assert vctx.response.status_code == 403, (
        f"Diharapkan 403, dapat {vctx.response.status_code}"
    )
