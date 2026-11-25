"""
Clustering semantik berbasis embedding (Sprint 3, bagian D).

Mengikuti Prasetya et al. (JISEBI 12(2), 2026): embedding HANYA dari teks WHAT, jarak cosine,
agglomerative clustering dengan average linkage dan ambang jarak, dan story perwakilan
= anggota yang paling dekat ke centroid cluster.

Alur: pastikan embedding (cache di DB) -> matriks jarak cosine -> agglomerative -> simpan Cluster
(+ ClusterAnggota yang menautkan cluster ke hasil ekstraksi dan, lewat itu, ke ulasan sumber).
Metode TF-IDF lama (extraction/services/clustering.py) tetap tersedia sebagai baseline.
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from django.conf import settings
from django.db import transaction
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services.clustering import bentuk_label_topik

logger = logging.getLogger('extraction.clustering')
METODE = 'embedding'


# --------------------------------------------------------------------------- embedder
class Embedder(ABC):
    nama = 'embedder'

    @abstractmethod
    def embed(self, teks_list):
        """Kembalikan ndarray (n, d), tiap baris L2-normalized."""


def _normalisasi(matriks):
    m = np.asarray(matriks, dtype=float)
    norma = np.linalg.norm(m, axis=1, keepdims=True)
    norma[norma == 0] = 1.0
    return m / norma


class GeminiEmbedder(Embedder):
    def __init__(self, client=None, model=None, dimensi=None, batch=None):
        from extraction.services.llm import get_llm_client
        provider = settings.EMBED_PROVIDER  # didefinisikan di base.py; sengaja tanpa default agar salah ketik terlihat
        self.client = client or get_llm_client(provider=provider)
        if provider == 'kampus':
            default_model = settings.LLM_KAMPUS.get('embedding_model', '')
        else:
            default_model = settings.LLM.get('embedding_model', 'gemini-embedding-001')
        self.nama = model or default_model
        self.dimensi = dimensi or settings.LLM.get('embedding_dim')
        self.batch = batch or settings.CLUSTERING.get('batch_embedding', 100)

    def embed(self, teks_list):
        hasil = []
        for awal in range(0, len(teks_list), self.batch):
            hasil.extend(self.client.embed(
                teks_list[awal:awal + self.batch], model=self.nama, dimensi=self.dimensi,
                task_type='CLUSTERING'))
        # Vektor berdimensi < penuh tidak otomatis ternormalisasi: normalisasi di sini.
        return _normalisasi(hasil)


# --------------------------------------------------------------------------- inti numerik
def jarak_cosine(vektor):
    """Matriks jarak cosine dari vektor L2-normalized."""
    v = _normalisasi(vektor)
    d = 1.0 - v @ v.T
    np.fill_diagonal(d, 0.0)
    return np.clip(d, 0.0, 2.0)


def bentuk_label(vektor, ambang):
    """Label cluster (agglomerative, cosine, average linkage, distance_threshold=ambang)."""
    n = len(vektor)
    if n == 1:
        return np.array([0])
    return AgglomerativeClustering(
        n_clusters=None, metric='precomputed', linkage='average', distance_threshold=ambang,
    ).fit_predict(jarak_cosine(vektor))


def indeks_representatif(vektor_anggota):
    """Indeks anggota terdekat ke centroid (kemiripan cosine tertinggi)."""
    v = _normalisasi(vektor_anggota)
    centroid = v.mean(axis=0)
    norma = np.linalg.norm(centroid)
    if norma == 0:
        return 0
    return int(np.argmax(v @ (centroid / norma)))


def rata_jarak_internal(vektor_anggota):
    n = len(vektor_anggota)
    if n < 2:
        return 0.0
    d = jarak_cosine(vektor_anggota)
    return float(d.sum() / (n * (n - 1)))


def skor_silhouette(vektor, label):
    """Silhouette (cosine); None bila tidak terdefinisi (kurang dari 2 cluster atau semua singleton)."""
    k = len(set(label))
    if k < 2 or k >= len(label):
        return None
    return float(silhouette_score(jarak_cosine(vektor), label, metric='precomputed'))


# --------------------------------------------------------------------------- DB
@dataclass
class HasilClusteringEmbedding:
    diproses: int = 0
    cluster_baru: int = 0
    anggota_ditambahkan: int = 0
    singleton: int = 0
    ukuran_maks: int = 0
    ambang: float = 0.0
    silhouette: Optional[float] = None
    embedding_baru: int = 0
    cluster_dihapus: int = 0
    ringkasan: List[dict] = field(default_factory=list)


def _default_queryset():
    return HasilEkstraksi.objects.filter(cluster_set__isnull=True).exclude(
        status_validasi=HasilEkstraksi.StatusValidasi.DIHAPUS).exclude(teks_what='').order_by('id')


def pastikan_embedding(items, embedder):
    """
    Isi `embedding_what` untuk item yang belum punya (atau dari model lain). Mengembalikan jumlah baru.
    Disimpan PER BATCH: bila kuota habis (429) di tengah jalan, batch yang sudah berhasil tidak dihitung ulang
    pada percobaan berikutnya (penting untuk kuota harian free tier).
    """
    perlu = [h for h in items if not h.embedding_what or h.model_embedding != embedder.nama]
    if not perlu:
        return 0
    ukuran = getattr(embedder, 'batch', None) or settings.CLUSTERING.get('batch_embedding', 100)
    jeda = float(settings.CLUSTERING.get('jeda_embedding_detik', 0) or 0)
    for awal in range(0, len(perlu), ukuran):
        potong = perlu[awal:awal + ukuran]
        if awal and jeda:
            time.sleep(jeda)
        vektor = embedder.embed([h.teks_what for h in potong])
        for h, v in zip(potong, vektor):
            h.embedding_what = [round(float(x), 6) for x in v]
            h.model_embedding = embedder.nama
        HasilEkstraksi.objects.bulk_update(potong, ['embedding_what', 'model_embedding'], batch_size=200)
    return len(perlu)


def pusatkan(vektor):
    """Kurangi vektor rata-rata lalu normalisasi ulang. Embedding teks pendek sejenis cenderung rapat
    (anisotropik); pemusatan memperlebar jarak relatif antar-topik. Perlu n >= 2."""
    v = np.asarray(vektor, dtype=float)
    if len(v) < 2:
        return v
    return _normalisasi(v - v.mean(axis=0))


def _pakai_pusat(pusat):
    return pusat if pusat is not None else bool(getattr(settings, 'CLUSTERING', {}).get('pusatkan', False))


def _matriks(items, pusat=None):
    X = np.array([h.embedding_what for h in items], dtype=float)
    return pusatkan(X) if _pakai_pusat(pusat) else X


def sweep(ambang_list, queryset=None, embedder=None, pusat=None):
    """Untuk tiap ambang: jumlah cluster, singleton, ukuran terbesar, silhouette. Tidak menyimpan cluster."""
    embedder = embedder or GeminiEmbedder()
    items = list(queryset if queryset is not None else _default_queryset())
    if not items:
        return []
    pastikan_embedding(items, embedder)
    X = _matriks(items, pusat)
    baris = []
    for a in ambang_list:
        label = bentuk_label(X, a)
        ukuran = np.bincount(label)
        baris.append({'ambang': a, 'cluster': int(len(ukuran)), 'singleton': int((ukuran == 1).sum()),
                      'ukuran_maks': int(ukuran.max()), 'silhouette': skor_silhouette(X, label)})
    return baris


@transaction.atomic
def kelompokkan_embedding(queryset=None, distance_threshold=None, dry_run=False, embedder=None,
                          bangun_ulang=False, pusat=None):
    """
    Kelompokkan HasilEkstraksi (yang belum ber-cluster) berdasarkan embedding WHAT.
    `bangun_ulang`: hapus dulu cluster berstatus MENUNGGU_VALIDASI (yang belum disentuh analis)
    agar anggotanya ikut dikelompokkan ulang, mis. setelah ambang diubah.
    """
    cfg = getattr(settings, 'CLUSTERING', {})
    ambang = distance_threshold if distance_threshold is not None else cfg.get('ambang_embedding', 0.10)
    hasil = HasilClusteringEmbedding(ambang=ambang)

    if bangun_ulang and not dry_run and queryset is None:
        hapus = Cluster.objects.filter(status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI)
        hasil.cluster_dihapus = hapus.count()
        hapus.delete()

    if queryset is None:
        qs = _default_queryset()
        if bangun_ulang and dry_run:  # simulasi: anggap cluster menunggu validasi sudah dilepas
            qs = HasilEkstraksi.objects.exclude(
                status_validasi=HasilEkstraksi.StatusValidasi.DIHAPUS).exclude(teks_what='').exclude(
                cluster_set__cluster__status_cluster__in=[
                    s for s, _ in Cluster.StatusCluster.choices
                    if s != Cluster.StatusCluster.MENUNGGU_VALIDASI]).order_by('id')
        items = list(qs.distinct())
    else:
        items = list(queryset)
    hasil.diproses = len(items)
    if not items:
        return hasil

    embedder = embedder or GeminiEmbedder()
    hasil.embedding_baru = pastikan_embedding(items, embedder)  # cache embedding disimpan walau dry-run
    if dry_run and hasil.embedding_baru:
        logger.warning('dry_run: %s embedding baru TETAP ditulis ke basis data (cache embedding_what); '
                       'cluster tidak disimpan.', hasil.embedding_baru)
    X = _matriks(items, pusat)
    label = bentuk_label(X, ambang)
    hasil.silhouette = skor_silhouette(X, label)

    kelompok = {}
    for idx, lb in enumerate(label):
        kelompok.setdefault(int(lb), []).append(idx)
    hasil.cluster_baru = len(kelompok)
    hasil.anggota_ditambahkan = len(items)
    hasil.singleton = sum(1 for v in kelompok.values() if len(v) == 1)
    hasil.ukuran_maks = max(len(v) for v in kelompok.values())

    for idxs in sorted(kelompok.values(), key=len, reverse=True):
        sub = X[idxs]
        rep = idxs[indeks_representatif(sub)]
        rata = rata_jarak_internal(sub)
        hasil.ringkasan.append({
            'ukuran': len(idxs), 'representatif': items[rep].teks_what, 'rata_jarak': round(rata, 3),
            'anggota': [items[i].teks_what for i in idxs if i != rep][:5]})
        if dry_run:
            continue
        cluster = Cluster.objects.create(
            # label ringkas gaya Sprint 3 (frontend); story perwakilan disimpan di `representatif`
            nama_topik=bentuk_label_topik(items[rep].teks_what, items[rep].teks_why)[:200],
            jumlah_anggota=len(idxs),
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI, representatif=items[rep],
            metode=METODE, ambang_jarak=ambang, rata_jarak=rata)
        ClusterAnggota.objects.bulk_create(
            [ClusterAnggota(cluster=cluster, hasil_ekstraksi=items[i]) for i in idxs])
    logger.info('clustering embedding: n=%s cluster=%s singleton=%s ambang=%s silhouette=%s dry_run=%s',
                hasil.diproses, hasil.cluster_baru, hasil.singleton, ambang, hasil.silhouette, dry_run)
    return hasil
