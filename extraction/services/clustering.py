"""
Layanan pengelompokan (clustering) hasil ekstraksi berdasarkan kemiripan semantik (FR-EKS-08, FR-EKS-09).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi


@dataclass
class HasilClustering:
    diproses: int = 0
    cluster_baru: int = 0
    anggota_ditambahkan: int = 0


# Pemetaan sinonim keluhan/masalah ulasan e-gov umum untuk penguatan semantik
SINONIM_POLA = [
    (r'\b(keluar sendiri|keluar tiba tiba|tutup sendiri|fc|force close|crash)\b', 'force_close'),
    (r'\b(tidak bisa|gabisa|ga bisa|gagal|error|eror)\b', 'gagal'),
    (r'\b(masuk|login|log in)\b', 'login'),
    (r'\b(lambat|lemot|lelet|loading terus|buffering)\b', 'lambat'),
    (r'\b(sulit|susah|ribet)\b', 'sulit'),
]


def bersihkan_teks(teks: str) -> str:
    """Bersihkan teks dan terapkan penyelarasan sinonim keluhan."""
    if not teks:
        return ''
    t = str(teks).lower()
    for pola, pengganti in SINONIM_POLA:
        t = re.sub(pola, pengganti, t)
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def cari_topik_representatif(items: List[HasilEkstraksi], X_tfidf, indices: List[int]) -> str:
    """
    Pilih teks_what paling sentral/representatif dalam cluster.
    Jika 1 item, kembalikan teks_what item tersebut.
    Jika banyak, pilih item dengan rata-rata cosine similarity tertinggi ke sesama anggota cluster.
    """
    if len(items) == 1:
        return items[0].teks_what

    sub_matrix = X_tfidf[indices]
    sim_matrix = cosine_similarity(sub_matrix)
    avg_sim = sim_matrix.mean(axis=1)
    best_idx = int(avg_sim.argmax())
    return items[best_idx].teks_what


@transaction.atomic
def kelompokkan_ekstraksi(
    queryset=None,
    distance_threshold: Optional[float] = None,
    dry_run: bool = False,
) -> HasilClustering:
    """
    Mengelompokkan HasilEkstraksi yang belum masuk ke dalam cluster.
    - Menggunakan TF-IDF + Agglomerative Clustering (Cosine Distance).
    - Status cluster awal: MENUNGGU_VALIDASI (FR-EKS-09).
    """
    cfg = getattr(settings, 'CLUSTERING', {})
    threshold = distance_threshold if distance_threshold is not None else cfg.get('distance_threshold', 0.55)

    if queryset is None:
        queryset = HasilEkstraksi.objects.filter(
            cluster_set__isnull=True
        ).exclude(
            status_validasi=HasilEkstraksi.StatusValidasi.DIHAPUS
        ).order_by('id')

    items = list(queryset)
    hasil = HasilClustering(diproses=len(items))

    if not items:
        return hasil

    if len(items) == 1:
        hasil.cluster_baru = 1
        hasil.anggota_ditambahkan = 1
        if not dry_run:
            c = Cluster.objects.create(
                nama_topik=items[0].teks_what[:200],
                jumlah_anggota=1,
                status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
            )
            ClusterAnggota.objects.create(cluster=c, hasil_ekstraksi=items[0])
        return hasil

    korpus = [
        f"{bersihkan_teks(it.teks_what)} {bersihkan_teks(it.teks_why)}"
        for it in items
    ]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(korpus)

    # Hitung matriks jarak cosine
    dist_matrix = cosine_distances(X)

    clustering_model = AgglomerativeClustering(
        n_clusters=None,
        metric='precomputed',
        linkage='average',
        distance_threshold=threshold,
    )
    labels = clustering_model.fit_predict(dist_matrix)

    clusters_dict = {}
    for idx, label in enumerate(labels):
        clusters_dict.setdefault(label, []).append(idx)

    hasil.cluster_baru = len(clusters_dict)
    hasil.anggota_ditambahkan = len(items)

    if dry_run:
        return hasil

    for label, indices in clusters_dict.items():
        cluster_items = [items[i] for i in indices]
        topik = cari_topik_representatif(cluster_items, X, indices)

        cluster = Cluster.objects.create(
            nama_topik=topik[:200],
            jumlah_anggota=len(cluster_items),
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )

        ClusterAnggota.objects.bulk_create([
            ClusterAnggota(cluster=cluster, hasil_ekstraksi=it)
            for it in cluster_items
        ])

    return hasil
