"""
Uji clustering semantik dan validasi hasil ekstraksi oleh Analyst (Backlog #5 & #6, UC-1, UC-2, FR-EKS-08/09, FR-VAL-01 s/d 05).
"""
import pytest
from django.urls import reverse

from accounts.models import User
from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services import clustering, validation
from reviews.models import Aplikasi, Ulasan


@pytest.fixture
def extraction_data(db):
    app = Aplikasi.objects.create(
        nama_aplikasi='SATU SEHAT',
        package_name='com.telkom.tracencare',
        kategori='Kesehatan',
    )
    analyst_user = User.objects.create_user(
        username='analyst_tester',
        email='analyst@katawarga.local',
        password='password123',
        role=User.RolePengguna.ANALYST,
    )
    dev_user = User.objects.create_user(
        username='dev_tester',
        email='dev@katawarga.local',
        password='password123',
        role=User.RolePengguna.TIM_DEVELOPER,
    )

    u1 = Ulasan.objects.create(
        aplikasi=app,
        isi_ulasan='Aplikasi selalu force close saat login masuk',
        tanggal_ulasan='2026-10-01',
        skor_bintang=1,
        status_filter=Ulasan.StatusFilter.LOLOS,
    )
    u2 = Ulasan.objects.create(
        aplikasi=app,
        isi_ulasan='Aplikasi keluar sendiri waktu login',
        tanggal_ulasan='2026-10-02',
        skor_bintang=1,
        status_filter=Ulasan.StatusFilter.LOLOS,
    )
    u3 = Ulasan.objects.create(
        aplikasi=app,
        isi_ulasan='Mohon tambahkan fitur tema gelap dark mode',
        tanggal_ulasan='2026-10-03',
        skor_bintang=4,
        status_filter=Ulasan.StatusFilter.LOLOS,
    )

    h1 = HasilEkstraksi.objects.create(
        ulasan=u1,
        teks_who='pengguna',
        teks_what='aplikasi force close saat login',
        teks_why='',
        skor_confidence=0.8,
    )
    h2 = HasilEkstraksi.objects.create(
        ulasan=u2,
        teks_who='pengguna',
        teks_what='aplikasi keluar sendiri waktu login',
        teks_why='',
        skor_confidence=0.8,
    )
    h3 = HasilEkstraksi.objects.create(
        ulasan=u3,
        teks_who='pengguna',
        teks_what='fitur tema gelap dark mode',
        teks_why='supaya nyaman di mata',
        skor_confidence=0.8,
    )

    return {
        'app': app,
        'analyst': analyst_user,
        'dev': dev_user,
        'h1': h1,
        'h2': h2,
        'h3': h3,
    }


@pytest.mark.django_db
def test_clustering_semantik(extraction_data):
    """
    Kriteria Gherkin 5.2.1:
    Dua ulasan 'force close saat login' dan 'keluar sendiri waktu login' berada di cluster yang sama.
    """
    res = clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    assert res.diproses == 3
    assert res.cluster_baru >= 1

    h1 = extraction_data['h1']
    h2 = extraction_data['h2']
    h3 = extraction_data['h3']

    c1 = ClusterAnggota.objects.get(hasil_ekstraksi=h1).cluster
    c2 = ClusterAnggota.objects.get(hasil_ekstraksi=h2).cluster
    c3 = ClusterAnggota.objects.get(hasil_ekstraksi=h3).cluster

    # h1 dan h2 harus berada dalam cluster yang sama
    assert c1.pk == c2.pk
    # h3 (fitur tema gelap) harus berada di cluster berbeda
    assert c1.pk != c3.pk
    # Status cluster awal adalah MENUNGGU_VALIDASI
    assert c1.status_cluster == Cluster.StatusCluster.MENUNGGU_VALIDASI


@pytest.mark.django_db
def test_validasi_setujui_cluster(client, extraction_data):
    """
    FR-VAL-03: Setujui cluster -> status TERVALIDASI
    """
    clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    cluster = Cluster.objects.first()
    analyst = extraction_data['analyst']

    client.force_login(analyst)
    url = reverse('extraction:setujui_cluster', kwargs={'pk': cluster.pk})
    resp = client.post(url, follow=True)

    assert resp.status_code == 200
    cluster.refresh_from_db()
    assert cluster.status_cluster == Cluster.StatusCluster.TERVALIDASI

    # Anggota ekstraksinya juga ikut tervalidasi
    for anggota in cluster.anggota_set.all():
        assert anggota.hasil_ekstraksi.status_validasi == HasilEkstraksi.StatusValidasi.TERVALIDASI
        assert anggota.hasil_ekstraksi.pengguna == analyst
        assert anggota.hasil_ekstraksi.tanggal_validasi is not None


@pytest.mark.django_db
def test_validasi_tolak_cluster(client, extraction_data):
    """
    FR-VAL-04: Tolak cluster -> status DIABAIKAN, ekstraksi -> DIHAPUS (soft delete)
    """
    clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    cluster = Cluster.objects.first()
    analyst = extraction_data['analyst']

    client.force_login(analyst)
    url = reverse('extraction:tolak_cluster', kwargs={'pk': cluster.pk})
    resp = client.post(url, follow=True)

    assert resp.status_code == 200
    cluster.refresh_from_db()
    assert cluster.status_cluster == Cluster.StatusCluster.DIABAIKAN

    for anggota in cluster.anggota_set.all():
        assert anggota.hasil_ekstraksi.status_validasi == HasilEkstraksi.StatusValidasi.DIHAPUS


@pytest.mark.django_db
def test_validasi_hanya_analyst(client, extraction_data):
    """
    Hanya Analyst yang berhak mengakses validasi ekstraksi.
    """
    clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    cluster = Cluster.objects.first()
    dev = extraction_data['dev']

    client.force_login(dev)
    url = reverse('extraction:setujui_cluster', kwargs={'pk': cluster.pk})
    resp = client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_validasi_state_machine_guard(client, extraction_data):
    """
    KW-04: Transisi status hanya diizinkan dari MENUNGGU_VALIDASI.
    - Setujui 2x harus gagal
    - Tolak setelah disetujui harus gagal
    - Tolak 2x harus gagal
    - Setujui setelah ditolak harus gagal
    """
    clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    cluster = Cluster.objects.first()
    analyst = extraction_data['analyst']

    # 1. Setujui pertama kali -> BERHASIL (MENUNGGU_VALIDASI -> TERVALIDASI)
    validation.setujui_cluster(cluster, validator_user=analyst)
    cluster.refresh_from_db()
    assert cluster.status_cluster == Cluster.StatusCluster.TERVALIDASI

    # 2. Coba setujui kedua kali -> HARUS GAGAL
    with pytest.raises(validation.ValidationError) as exc:
        validation.setujui_cluster(cluster, validator_user=analyst)
    assert "Hanya cluster berstatus 'Menunggu Validasi'" in str(exc.value)

    # 3. Coba tolak cluster yang sudah TERVALIDASI -> HARUS GAGAL
    with pytest.raises(validation.ValidationError) as exc:
        validation.tolak_cluster(cluster, validator_user=analyst)
    assert "Hanya cluster berstatus 'Menunggu Validasi'" in str(exc.value)

    # Buat cluster baru untuk pengujian tolak
    cluster_b = Cluster.objects.create(
        nama_topik='Topik B',
        status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
    )

    # 4. Tolak pertama kali -> BERHASIL (MENUNGGU_VALIDASI -> DIABAIKAN)
    validation.tolak_cluster(cluster_b, validator_user=analyst)
    cluster_b.refresh_from_db()
    assert cluster_b.status_cluster == Cluster.StatusCluster.DIABAIKAN

    # 5. Coba tolak kedua kali -> HARUS GAGAL
    with pytest.raises(validation.ValidationError) as exc:
        validation.tolak_cluster(cluster_b, validator_user=analyst)
    assert "Hanya cluster berstatus 'Menunggu Validasi'" in str(exc.value)

    # 6. Coba setujui cluster yang sudah DIABAIKAN -> HARUS GAGAL
    with pytest.raises(validation.ValidationError) as exc:
        validation.setujui_cluster(cluster_b, validator_user=analyst)
    assert "Hanya cluster berstatus 'Menunggu Validasi'" in str(exc.value)


@pytest.mark.django_db
def test_views_validasi_berulang_menolak_tanpa_error_500(client, extraction_data):
    """
    KW-04: View setujui dan tolak menangani ValidationError secara anggun
    dengan pesan error dan redirect, bukan crash 500.
    """
    clustering.kelompokkan_ekstraksi(distance_threshold=0.65)
    cluster = Cluster.objects.first()
    analyst = extraction_data['analyst']
    client.force_login(analyst)

    # Setujui sekali
    url_setujui = reverse('extraction:setujui_cluster', kwargs={'pk': cluster.pk})
    resp1 = client.post(url_setujui, follow=True)
    assert resp1.status_code == 200

    # Setujui kedua kali lewat view -> tidak 500, redirect 200 dengan pesan error
    resp2 = client.post(url_setujui, follow=True)
    assert resp2.status_code == 200
    messages_text = [m.message for m in resp2.context['messages']]
    assert any("Hanya cluster berstatus 'Menunggu Validasi'" in m for m in messages_text)

    # Tolak cluster yang sudah disetujui lewat view -> tidak 500, redirect 200 dengan pesan error
    url_tolak = reverse('extraction:tolak_cluster', kwargs={'pk': cluster.pk})
    resp3 = client.post(url_tolak, follow=True)
    assert resp3.status_code == 200
    messages_text_3 = [m.message for m in resp3.context['messages']]
    assert any("Hanya cluster berstatus 'Menunggu Validasi'" in m for m in messages_text_3)


