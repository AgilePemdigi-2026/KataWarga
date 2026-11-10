"""
Step definitions BDD — FR-USR (Penyusunan & Prioritisasi User Story) — Backlog #7.
"""
import pytest
from django.utils import timezone
from pytest_bdd import given, when, then, scenario, parsers

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from reviews.models import Ulasan
from stories.models import UserStory
from stories.services.composer import compose_pending
from features.conftest import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario('../sprint1/susun_user_story.feature',
          'FR-USR-01 Susun user story dari cluster signifikan (Happy Path)')
def test_fr_usr_01_happy_path():
    pass


@scenario('../sprint1/susun_user_story.feature',
          'FR-USR-02 Cluster tidak signifikan diabaikan')
def test_fr_usr_02_cluster_diabaikan():
    pass


@scenario('../sprint1/susun_user_story.feature',
          'FR-USR-03 Skor prioritas dihitung berdasarkan ukuran cluster')
def test_fr_usr_03_skor_prioritas():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class StoryKonteks:
    def __init__(self):
        self.cluster = None
        self.user_story = None
        self.stories_created = None
        self.nama_cluster = None


@pytest.fixture
def sctx():
    return StoryKonteks()


def _populate_cluster_members(cluster, aplikasi, jumlah, topik, who='wajib pajak', why='agar lancar'):
    """Helper untuk mengisi cluster dengan sejumlah ulasan unik secara efisien."""
    ts = timezone.now().timestamp()
    date_now = timezone.now().date()

    ulasan_objs = [
        Ulasan(
            aplikasi=aplikasi,
            review_id=f'{cluster.pk}_{i}_{ts}',
            isi_ulasan=f'Keluhan {topik} ke-{i}',
            skor_bintang=1,
            tanggal_ulasan=date_now,
            status_filter=Ulasan.StatusFilter.LOLOS,
        )
        for i in range(jumlah)
    ]
    Ulasan.objects.bulk_create(ulasan_objs)
    saved_ulasan = list(Ulasan.objects.filter(aplikasi=aplikasi, review_id__startswith=f'{cluster.pk}_'))

    he_objs = [
        HasilEkstraksi(
            ulasan=u,
            teks_who=who,
            teks_what=topik,
            teks_why=why,
            skor_confidence=0.8,
            status_validasi=HasilEkstraksi.StatusValidasi.TERVALIDASI,
        )
        for u in saved_ulasan
    ]
    HasilEkstraksi.objects.bulk_create(he_objs)
    saved_he = list(HasilEkstraksi.objects.filter(ulasan__in=saved_ulasan))

    ca_objs = [
        ClusterAnggota(cluster=cluster, hasil_ekstraksi=he)
        for he in saved_he
    ]
    ClusterAnggota.objects.bulk_create(ca_objs)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given(parsers.parse('ada cluster dengan {jumlah} anggota dan status "{status}"'),
       target_fixture='sctx')
def given_cluster_signifikan(db, aplikasi, jumlah, status):
    sctx = StoryKonteks()
    count = int(jumlah)
    cluster = Cluster.objects.create(
        nama_topik='Gagal Login OTP',
        jumlah_anggota=count,
        skor_signifikansi=float(count),
        status_cluster=status,
    )
    _populate_cluster_members(cluster, aplikasi, count, 'Gagal Login OTP')
    sctx.cluster = cluster
    return sctx


@given(parsers.parse('ada cluster bernama "{nama}" dengan {jumlah} anggota dan status "{status}"'),
       target_fixture='sctx')
def given_cluster_nama(db, aplikasi, nama, jumlah, status):
    sctx = StoryKonteks()
    count = int(jumlah)
    sctx.nama_cluster = nama
    cluster = Cluster.objects.create(
        nama_topik=nama,
        jumlah_anggota=count,
        skor_signifikansi=float(count),
        status_cluster=status,
    )
    _populate_cluster_members(cluster, aplikasi, count, nama)
    sctx.cluster = cluster
    return sctx


@given(parsers.parse('ada cluster "{nama_cluster}" dengan {jumlah_ulasan} anggota dan status "{status}"'),
       target_fixture='sctx')
def given_cluster_outline(db, aplikasi, nama_cluster, jumlah_ulasan, status):
    sctx = StoryKonteks()
    count = int(jumlah_ulasan)
    sctx.nama_cluster = nama_cluster
    cluster = Cluster.objects.create(
        nama_topik=nama_cluster,
        jumlah_anggota=count,
        skor_signifikansi=float(count),
        status_cluster=status,
    )
    _populate_cluster_members(cluster, aplikasi, count, nama_cluster)
    sctx.cluster = cluster
    return sctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('saya menjalankan penyusunan user story')
def when_susun_user_story(sctx, db):
    sctx.stories_created = compose_pending()


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then(parsers.parse('user story baru dibuat dengan teks dimulai dari "{awalan}"'))
def then_user_story_dibuat(sctx, db, awalan):
    story = UserStory.objects.filter(cluster=sctx.cluster).first()
    assert story is not None, "User story seharusnya ada setelah compose_pending()"
    assert story.kalimat.startswith(awalan), (
        f"Teks user story seharusnya dimulai '{awalan}', "
        f"tetapi '{story.kalimat[:30]}'"
    )


@then(parsers.parse('cluster "{nama}" tidak menghasilkan user story'))
def then_cluster_tidak_menghasilkan(sctx, db, nama):
    story = UserStory.objects.filter(cluster=sctx.cluster).first()
    assert story is None, (
        f"Cluster '{nama}' dengan anggota sedikit tidak seharusnya menghasilkan user story"
    )
    sctx.cluster.refresh_from_db()
    assert sctx.cluster.status_cluster == Cluster.StatusCluster.DIABAIKAN


@then(parsers.parse('kategori prioritas user story adalah "{hasil_prioritas}"'))
def then_kategori_prioritas(sctx, db, hasil_prioritas):
    story = UserStory.objects.filter(cluster=sctx.cluster).first()
    assert story is not None, (
        f"User story untuk cluster '{sctx.nama_cluster}' seharusnya berhasil disusun"
    )
    assert story.kategori_prioritas == hasil_prioritas, (
        f"Kategori prioritas seharusnya '{hasil_prioritas}', "
        f"tetapi '{story.kategori_prioritas}' (skor: {story.skor_prioritas})"
    )
