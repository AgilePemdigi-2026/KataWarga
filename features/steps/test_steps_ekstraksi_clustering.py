"""
Step definitions BDD — FR-EKS (Ekstraksi & Clustering) — Backlog #5.
"""
import pytest
from pytest_bdd import given, when, then, scenario, parsers

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services.clustering import kelompokkan_ekstraksi
from extraction.services.aturan import EkstraktorAturan
from extraction.services.runner import ekstrak_ulasan_baru
from reviews.models import Ulasan
from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint2/ekstraksi_clustering.feature',
          'FR-EKS-01 Jalankan ekstraksi dan dapatkan cluster baru (Happy Path)')
def test_fr_eks_01_happy_path():
    pass


@scenario('../sprint2/ekstraksi_clustering.feature',
          'FR-EKS-02 Ulasan pendek atau generik difilter otomatis')
def test_fr_eks_02_filter_generik():
    pass


@scenario('../sprint2/ekstraksi_clustering.feature',
          'FR-EKS-03 Ulasan dengan keluhan serupa dikelompokkan ke cluster yang sama')
def test_fr_eks_03_cluster_sama():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class EkstraksiKonteks:
    def __init__(self):
        self.ulasan_list = []
        self.he_list = []
        self.ulasan_generik = None
        self.hasil_clustering = None


@pytest.fixture
def ctx():
    return EkstraksiKonteks()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given('saya memiliki ulasan yang sudah diekstraksi dengan status TERVALIDASI',
       target_fixture='ctx')
def given_ulasan_tervalidasi(db, ulasan_factory, hasil_ekstraksi_factory):
    ctx = EkstraksiKonteks()
    u1 = ulasan_factory('aplikasi selalu force close saat login')
    u2 = ulasan_factory('aplikasi keluar sendiri waktu masuk')
    he1 = hasil_ekstraksi_factory(teks_what='aplikasi force close saat login', ulasan=u1)
    he2 = hasil_ekstraksi_factory(teks_what='aplikasi keluar sendiri waktu login', ulasan=u2)
    ctx.ulasan_list = [u1, u2]
    ctx.he_list = [he1, he2]
    return ctx


@given(parsers.parse('saya memiliki ulasan "{teks}" untuk aplikasi "{app}"'),
       target_fixture='ctx')
def given_ulasan_generik(db, aplikasi, teks, app, ulasan_factory):
    ctx = EkstraksiKonteks()
    # Ulasan generik seperti "bagus" diberi status DIBUANG saat filtering/scraping
    u = ulasan_factory(teks=teks, status=Ulasan.StatusFilter.DIBUANG)
    ctx.ulasan_generik = u
    return ctx


@given(parsers.parse('saya memiliki ulasan "{teks}"'))
def given_ulasan_keluhan(ctx, db, ulasan_factory, hasil_ekstraksi_factory, teks):
    u = ulasan_factory(teks=teks)
    he = hasil_ekstraksi_factory(teks_what=teks, ulasan=u)
    ctx.ulasan_list.append(u)
    ctx.he_list.append(he)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('saya menjalankan proses clustering')
def when_jalankan_clustering(ctx, db):
    ctx.hasil_clustering = kelompokkan_ekstraksi(distance_threshold=0.65)


@when('saya menjalankan proses ekstraksi')
def when_jalankan_ekstraksi(ctx, db):
    ekstraktor = EkstraktorAturan()
    ekstrak_ulasan_baru(ekstraktor)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then('cluster baru berhasil dibuat dari hasil ekstraksi')
def then_cluster_dibuat(ctx, db):
    assert Cluster.objects.count() >= 1, "Tidak ada cluster yang dibuat"


@then(parsers.parse('ulasan "{teks}" tidak muncul di hasil ekstraksi'))
def then_ulasan_tidak_muncul(ctx, db, teks):
    # Ulasan yang berstatus DIBUANG tidak diproses oleh runner ekstraksi
    hasil = HasilEkstraksi.objects.filter(ulasan=ctx.ulasan_generik)
    assert hasil.count() == 0, (
        f"Ulasan generik '{teks}' seharusnya tidak memiliki hasil ekstraksi"
    )


@then('kedua ulasan masuk ke dalam cluster yang sama')
def then_cluster_sama(ctx, db):
    assert len(ctx.he_list) >= 2, "Perlu minimal 2 hasil ekstraksi"
    c1 = ClusterAnggota.objects.get(hasil_ekstraksi=ctx.he_list[0]).cluster
    c2 = ClusterAnggota.objects.get(hasil_ekstraksi=ctx.he_list[1]).cluster
    assert c1.pk == c2.pk, (
        f"Kedua ulasan seharusnya berada di cluster yang sama, "
        f"tetapi cluster #{c1.pk} ≠ #{c2.pk}"
    )
