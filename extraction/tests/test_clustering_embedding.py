"""Tes clustering embedding (bagian D) tanpa jaringan: embedder dan SDK dipalsukan."""
from io import StringIO
from unittest import mock

import numpy as np
import pytest
from django.core.management import call_command

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services import clustering_embedding as ce
from extraction.services.llm import GeminiClient, LLMResponseError
from reviews.models import Aplikasi, Ulasan

# Tiga "topik" pada ruang 3 dimensi: login, unduh, dan lambat. Sedikit noise supaya anggota berbeda tipis.
VEKTOR = {
    'tetap login setelah update': [1.0, 0.05, 0.0],
    'tidak perlu login ulang': [0.95, 0.10, 0.0],
    'login tanpa input NIK berulang': [0.9, 0.15, 0.05],
    'mengunduh aplikasi ukuran kecil': [0.0, 1.0, 0.05],
    'aplikasi bisa diunduh di HP lama': [0.05, 0.95, 0.1],
    'aplikasi tidak lemot': [0.0, 0.0, 1.0],
}


class EmbedderPalsu(ce.Embedder):
    nama = 'palsu'

    def __init__(self):
        self.panggilan = []

    def embed(self, teks_list):
        self.panggilan.append(list(teks_list))
        return ce._normalisasi([VEKTOR[t] for t in teks_list])


@pytest.fixture
def hasil(db):
    app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')
    out = []
    for i, what in enumerate(VEKTOR):
        u = Ulasan.objects.create(aplikasi=app, review_id=f'r{i}', isi_ulasan=what, tanggal_ulasan='2026-01-01',
                                  skor_bintang=1)
        out.append(HasilEkstraksi.objects.create(ulasan=u, teks_who='pengguna', teks_what=what))
    return out


def test_label_memisahkan_topik_berbeda_dan_menyatukan_yang_sama():
    X = ce._normalisasi(list(VEKTOR.values()))
    label = ce.bentuk_label(X, 0.1)
    assert len(set(label)) == 3
    assert label[0] == label[1] == label[2]
    assert label[3] == label[4] != label[0]
    assert label[5] not in (label[0], label[3])


def test_ambang_sangat_longgar_menggabung_semua_dan_sangat_ketat_memecah_semua():
    X = ce._normalisasi(list(VEKTOR.values()))
    assert len(set(ce.bentuk_label(X, 1.5))) == 1
    assert len(set(ce.bentuk_label(X, 1e-9))) == len(X)


def test_representatif_terdekat_ke_centroid():
    v = ce._normalisasi([[1, 0], [0.9, 0.1], [0.6, 0.8]])
    assert ce.indeks_representatif(v) == 1  # yang tengah


def test_rata_jarak_dan_silhouette():
    X = ce._normalisasi(list(VEKTOR.values()))
    assert ce.rata_jarak_internal(X[:1]) == 0.0
    assert 0 < ce.rata_jarak_internal(X[:3]) < 0.1
    sil = ce.skor_silhouette(X, ce.bentuk_label(X, 0.1))
    assert sil is not None and sil > 0.5
    assert ce.skor_silhouette(X, np.zeros(len(X), dtype=int)) is None


def test_kelompokkan_membuat_cluster_tautan_dan_representatif(hasil):
    e = EmbedderPalsu()
    r = ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    assert (r.diproses, r.cluster_baru, r.singleton, r.ukuran_maks) == (6, 3, 1, 3)
    assert Cluster.objects.count() == 3
    c = Cluster.objects.order_by('-jumlah_anggota').first()
    assert c.jumlah_anggota == 3 == c.anggota_set.count()
    from extraction.services.clustering import bentuk_label_topik
    assert c.representatif.teks_what in VEKTOR
    assert c.nama_topik == bentuk_label_topik(c.representatif.teks_what, c.representatif.teks_why)
    assert (c.metode, c.ambang_jarak) == ('embedding', 0.1)
    # cluster tertaut ke ulasan sumber lewat anggota
    assert {a.hasil_ekstraksi.ulasan.review_id for a in c.anggota_set.all()} == {'r0', 'r1', 'r2'}
    assert c.status_cluster == Cluster.StatusCluster.MENUNGGU_VALIDASI


def test_embedding_disimpan_dan_tidak_dihitung_ulang(hasil):
    e = EmbedderPalsu()
    ce.kelompokkan_embedding(distance_threshold=0.1, dry_run=True, embedder=e)
    assert Cluster.objects.count() == 0                       # dry-run: tidak ada cluster
    assert HasilEkstraksi.objects.filter(embedding_what__isnull=False).count() == 6  # cache tersimpan
    ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    assert len(e.panggilan) == 1                              # panggilan kedua memakai cache


def test_hanya_yang_belum_ber_cluster_diproses(hasil):
    e = EmbedderPalsu()
    ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    r = ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    assert r.diproses == 0 and Cluster.objects.count() == 3


def test_bangun_ulang_hanya_menyentuh_cluster_menunggu_validasi(hasil):
    e = EmbedderPalsu()
    ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    besar = Cluster.objects.order_by('-jumlah_anggota').first()
    besar.status_cluster = Cluster.StatusCluster.TERVALIDASI
    besar.save()
    r = ce.kelompokkan_embedding(distance_threshold=1.5, embedder=e, bangun_ulang=True)
    assert r.cluster_dihapus == 2
    assert Cluster.objects.filter(pk=besar.pk).exists()        # yang tervalidasi tidak dihapus
    assert r.diproses == 3 and r.cluster_baru == 1             # 3 sisanya digabung pada ambang longgar
    assert ClusterAnggota.objects.count() == 6


def test_sweep_menghasilkan_satu_baris_per_ambang(hasil):
    baris = ce.sweep([1e-9, 0.1, 1.5], embedder=EmbedderPalsu())
    assert [b['cluster'] for b in baris] == [6, 3, 1]
    assert Cluster.objects.count() == 0


def test_hasil_dihapus_atau_what_kosong_diabaikan(hasil):
    hasil[0].status_validasi = HasilEkstraksi.StatusValidasi.DIHAPUS
    hasil[0].save()
    r = ce.kelompokkan_embedding(distance_threshold=0.1, embedder=EmbedderPalsu())
    assert r.diproses == 5


class _Emb:
    def __init__(self, v):
        self.values = v


class _SdkEmbed:
    def __init__(self, jumlah_dikembalikan=None):
        self.models = self
        self.jumlah, self.panggilan = jumlah_dikembalikan, []

    def embed_content(self, **kw):
        self.panggilan.append(kw)
        n = self.jumlah if self.jumlah is not None else len(kw['contents'])
        return mock.Mock(embeddings=[_Emb([3.0, 4.0]) for _ in range(n)])


def _klien(sdk):
    return GeminiClient(api_key='x', model='m', sdk_client=sdk, rpm=0, tidur=lambda s: None)


def test_client_embed_dan_embedder_menormalisasi_serta_memecah_batch():
    sdk = _SdkEmbed()
    emb = ce.GeminiEmbedder(client=_klien(sdk), model='gemini-embedding-001', dimensi=2, batch=2)
    m = emb.embed(['a', 'b', 'c'])
    assert m.shape == (3, 2) and np.allclose(np.linalg.norm(m, axis=1), 1.0)
    assert np.allclose(m[0], [0.6, 0.8])
    assert [len(p['contents']) for p in sdk.panggilan] == [2, 1]


def test_client_embed_jumlah_tidak_cocok_error():
    with pytest.raises(LLMResponseError):
        _klien(_SdkEmbed(jumlah_dikembalikan=1)).embed(['a', 'b'], model='m')


def test_client_embed_daftar_kosong():
    assert _klien(_SdkEmbed()).embed([]) == []


def test_command_embedding_dan_tfidf(hasil):
    out = StringIO()
    with mock.patch.object(ce, 'GeminiEmbedder', return_value=EmbedderPalsu()):
        call_command('cluster_reviews', '--threshold', '0.1', '--lihat', stdout=out)
    assert '3 cluster dibuat' in out.getvalue() and 'rata jarak' in out.getvalue()
    out2 = StringIO()
    call_command('cluster_reviews', '--metode', 'tfidf', '--dry-run', stdout=out2)
    assert '[tfidf]' in out2.getvalue()


def test_command_sweep(hasil):
    out = StringIO()
    with mock.patch.object(ce, 'GeminiEmbedder', return_value=EmbedderPalsu()):
        call_command('cluster_reviews', '--sweep', '0.1,1.5', stdout=out)
    assert 'ambang' in out.getvalue() and Cluster.objects.count() == 0


def test_bangun_ulang_dry_run_tidak_mengubah_cluster(hasil):
    e = EmbedderPalsu()
    ce.kelompokkan_embedding(distance_threshold=0.1, embedder=e)
    besar = Cluster.objects.order_by('-jumlah_anggota').first()
    besar.status_cluster = Cluster.StatusCluster.TERVALIDASI
    besar.save()
    jumlah_cluster, jumlah_anggota = Cluster.objects.count(), ClusterAnggota.objects.count()
    r = ce.kelompokkan_embedding(distance_threshold=1.5, embedder=e, bangun_ulang=True, dry_run=True)
    assert r.diproses == 3 and r.cluster_baru == 1            # simulasi: yang tervalidasi tidak ikut
    assert (Cluster.objects.count(), ClusterAnggota.objects.count()) == (jumlah_cluster, jumlah_anggota)
    assert r.cluster_dihapus == 0                              # tidak ada yang benar-benar dihapus


def test_embedding_disimpan_per_batch_saat_kuota_habis(hasil):
    class Gagal(EmbedderPalsu):
        batch = 2

        def embed(self, teks_list):
            if len(self.panggilan) >= 1:
                raise LLMResponseError('429')
            return super().embed(teks_list)

    with pytest.raises(LLMResponseError):
        ce.pastikan_embedding(list(HasilEkstraksi.objects.order_by('id')), Gagal())
    assert HasilEkstraksi.objects.exclude(embedding_what__isnull=True).exclude(model_embedding='').count() == 2
    e = EmbedderPalsu()
    assert ce.pastikan_embedding(list(HasilEkstraksi.objects.order_by('id')), e) == 4  # hanya sisanya
