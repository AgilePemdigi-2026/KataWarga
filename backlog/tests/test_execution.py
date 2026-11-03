"""
Uji eksekusi item backlog (Backlog #10, UC-6, FR-BKL-01 s/d FR-BKL-05).
"""
import pytest
from django.urls import reverse

from accounts.models import User
from backlog.models import BacklogItem
from backlog.services import execution
from extraction.models import Cluster
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


@pytest.fixture
def data_setup(db):
    app = Aplikasi.objects.create(
        nama_aplikasi='SATU SEHAT',
        package_name='com.telkom.tracencare',
        kategori='Kesehatan',
    )
    cluster = Cluster.objects.create(
        nama_topik='Gagal Login OTP',
        jumlah_anggota=10,
        skor_signifikansi=10.0,
        status_cluster=Cluster.StatusCluster.TERVALIDASI,
    )
    story = UserStory.objects.create(
        cluster=cluster,
        peran='pengguna aplikasi SATU SEHAT',
        kebutuhan='dapat menerima kode OTP login dengan cepat',
        alasan='bisa segera mengakses sertifikat vaksin',
        skor_prioritas=80.0,
        kategori_prioritas=UserStory.LevelPrioritas.TINGGI,
        status_persetujuan=UserStory.StatusPersetujuan.DISETUJUI,
    )
    backlog_item = BacklogItem.objects.create(
        user_story=story,
        status_eksekusi=BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI,
    )
    dev_user = User.objects.create_user(
        username='dev_tester',
        email='dev@tester.local',
        password='password123',
        role=User.RolePengguna.TIM_DEVELOPER,
    )
    po_user = User.objects.create_user(
        username='po_tester',
        email='po@tester.local',
        password='password123',
        role=User.RolePengguna.PRODUCT_OWNER,
    )
    return {
        'app': app,
        'cluster': cluster,
        'story': story,
        'item': backlog_item,
        'dev': dev_user,
        'po': po_user,
    }


@pytest.mark.django_db
def test_mulai_kerjakan_service_dan_view(client, data_setup):
    item = data_setup['item']
    dev = data_setup['dev']

    # Test via POST endpoint
    client.force_login(dev)
    url = reverse('backlog:mulai', kwargs={'pk': item.pk})
    resp = client.post(url, follow=True)

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN
    assert item.pengguna == dev
    assert item.tanggal_mulai_dikerjakan is not None


@pytest.mark.django_db
def test_tandai_selesai_service_dan_view(client, data_setup):
    item = data_setup['item']
    dev = data_setup['dev']

    # Mulai dulu
    execution.mulai_kerjakan(item, dev)

    # Selesaikan via view
    client.force_login(dev)
    url = reverse('backlog:selesai', kwargs={'pk': item.pk})
    resp = client.post(url, follow=True)

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SELESAI
    assert item.tanggal_selesai is not None

    # Verifikasi pesan persis FR-BKL-04
    messages_list = list(resp.context['messages'])
    assert any('Keluhan pengguna telah ditangani' in str(m) for m in messages_list)


@pytest.mark.django_db
def test_transisi_tidak_valid_ditolak(client, data_setup):
    item = data_setup['item']
    dev = data_setup['dev']

    # Langsung tandai selesai padahal belum mulai
    client.force_login(dev)
    url = reverse('backlog:selesai', kwargs={'pk': item.pk})
    resp = client.post(url, follow=True)

    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI
    messages_list = list(resp.context['messages'])
    assert any('belum berstatus SEDANG_DIKERJAKAN' in str(m) for m in messages_list)


@pytest.mark.django_db
def test_role_selain_developer_ditolak(client, data_setup):
    item = data_setup['item']
    po = data_setup['po']

    client.force_login(po)
    url = reverse('backlog:mulai', kwargs={'pk': item.pk})
    resp = client.post(url)

    assert resp.status_code == 403

