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

# Kata henti / filler temporal & frekuensi dalam ulasan pengguna
STOPWORDS_POLA = r'\b(saat|waktu|ketika|selalu|sering|terus|tiap|setiap|pas)\b'

# Pola pemetaan topik keluhan e-government berdasarkan kata kunci WHAT dan WHY
POLA_LABEL_TOPIK = [
    # 1. Otentikasi, Akun & Registrasi
    (r'\b(otp|kode otp|sms otp|sms verifikasi|kode verifikasi|token|verifikasi nomor|verifikasi nomor handphone|verifikasi no hp|nomor handphone|nomor hp|handphone)\b', 'Kendala Kode OTP'),
    (r'\b(nik|nomor induk|e-?ktp|ktp elektronik|data kependudukan|kartu keluarga|\bkk\b)\b', 'Verifikasi NIK & Data Kependudukan'),
    (r'\b(daftar|mendaftar|registrasi|buat akun|bikin akun|aktivasi akun|sign up|pendaftaran)\b', 'Gangguan Pendaftaran Akun'),
    (r'\b(login|log in|masuk|sign in|kata sandi|password|lupa sandi|ganti sandi|\bpin\b|lupa pin|akun terkunci)\b', 'Masalah Login Aplikasi'),

    # 2. Crash & Stabilitas
    (r'\b(keluar sendiri|tutup sendiri|force close|force_close|\bfc\b|crash|tiba tiba keluar|layar hitam|blank|freeze|hang|macet)\b', 'Aplikasi Sering Crash'),

    # 3. Performa & Jaringan
    (r'\b(lambat|lemot|lelet|loading terus|loading lama|muter terus|stuck di loading|buffering)\b', 'Performa Aplikasi Lambat'),
    (r'\b(server|server down|gangguan server|koneksi|sinyal|jaringan|internet|timeout|rto|tidak terhubung)\b', 'Gangguan Server & Koneksi'),

    # 4. Kamera, Biometrik & Scan
    (r'\b(scan wajah|rekam wajah|face recognition|deteksi wajah|biometrik|sidik jari|fingerprint)\b', 'Verifikasi Wajah & Biometrik'),
    (r'\b(kamera|ambil foto|foto ktp|pas foto|kamera tidak bisa|izin kamera|buka kamera|foto buram)\b', 'Masalah Kamera & Foto'),
    (r'\b(scan qr|barcode|kode qr|pindai qr|pindai barcode|scan barcode)\b', 'Pemindaian QR & Barcode'),

    # 5. Lokasi, GPS & Presensi
    (r'\b(lokasi|gps|titik koordinat|radius|luar radius|presensi|absen|kehadiran)\b', 'Kendala GPS & Lokasi'),

    # 6. Fitur Layanan & Dokumen
    (r'\b(sertifikat|kartu vaksin|unduh|download|cetak dokumen|file pdf|buka pdf)\b', 'Unduh & Akses Dokumen'),
    (r'\b(update|perbarui|versi baru|gagal update|pembaruan|unduh versi)\b', 'Kendala Pembaruan Aplikasi'),
    (r'\b(notifikasi|pemberitahuan|notif|pesan masuk)\b', 'Kendala Notifikasi Layanan'),
    (r'\b(faskes|bpjs|rujukan|klaim|berobat|antrean|nomor antrean)\b', 'Layanan Faskes & Rujukan'),
    (r'\b(pembayaran|bayar|tagihan|transaksi|\bva\b|virtual account)\b', 'Kendala Pembayaran & Tagihan'),
]

KATA_FILLER_AWAL = re.compile(
    r'^(tidak bisa|tidak dapat|gabisa|ga bisa|gagal|susah|sulit|mohon|tolong|kenapa|mengapa|kok|selalu|sering|aplikasi|di aplikasi|saat|ketika|waktu)\s+',
    re.IGNORECASE,
)

FILLER_KATA = re.compile(
    r'\b(saya|aku|kami|aplikasi ini|aplikasi|di|ke|pada|untuk|banget|sekali|sama sekali|terus|sudah|udah|dari kemarin|sejak kemarin|sejak|hari ini|min|admin|halo|ini|itu|tidak bisa|tidak dapat|gabisa|ga bisa|gagal|susah|sulit|mohon|tolong)\b',
    re.IGNORECASE,
)


def bentuk_label_topik(teks_what: str, teks_why: str = '') -> str:
    """
    Menghasilkan label topik yang ringkas, deterministik, dan representatif
    untuk cluster berdasarkan konteks elemen WHAT dan WHY.
    """
    gabungan = f"{teks_what or ''} {teks_why or ''}".strip().lower()
    if not gabungan:
        return "Topik Umum"

    # 1. Cek pola domain yang spesifik
    for pola, label in POLA_LABEL_TOPIK:
        if re.search(pola, gabungan, re.IGNORECASE):
            return label

    # 2. Fallback cerdas: bersihkan filler percakapan dan bentuk frasa ringkas
    t = str(teks_what or teks_why or '').strip()
    t = KATA_FILLER_AWAL.sub('', t)
    t = FILLER_KATA.sub(' ', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    kata = [w for w in t.split() if len(w) > 2 and not w.isdigit()]

    if kata:
        frasa = ' '.join(kata[:3]).title()
        if len(frasa) > 35:
            frasa = frasa[:32].rstrip() + '…'
        return f"Kendala {frasa}"

    return "Keluhan Layanan Pengguna"


def bersihkan_teks(teks: str) -> str:
    """Bersihkan teks dan terapkan penyelarasan sinonim keluhan."""
    if not teks:
        return ''
    t = str(teks).lower()
    for pola, pengganti in SINONIM_POLA:
        t = re.sub(pola, pengganti, t)
    t = re.sub(STOPWORDS_POLA, ' ', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def cari_topik_representatif(items: List[HasilEkstraksi], X_tfidf, indices: List[int]) -> HasilEkstraksi:
    """
    Pilih objek HasilEkstraksi paling sentral/representatif dalam cluster.
    Jika 1 item, kembalikan item tersebut.
    Jika banyak, pilih item dengan rata-rata cosine similarity tertinggi ke sesama anggota cluster.
    """
    if len(items) == 1:
        return items[0]

    sub_matrix = X_tfidf[indices]
    sim_matrix = cosine_similarity(sub_matrix)
    avg_sim = sim_matrix.mean(axis=1)
    best_idx = int(avg_sim.argmax())
    return items[best_idx]


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
            nama_topik = bentuk_label_topik(items[0].teks_what, items[0].teks_why)
            c = Cluster.objects.create(
                nama_topik=nama_topik[:200],
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
        item_representatif = cari_topik_representatif(cluster_items, X, indices)
        nama_topik = bentuk_label_topik(
            item_representatif.teks_what,
            item_representatif.teks_why
        )

        cluster = Cluster.objects.create(
            nama_topik=nama_topik[:200],
            jumlah_anggota=len(cluster_items),
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )

        ClusterAnggota.objects.bulk_create([
            ClusterAnggota(cluster=cluster, hasil_ekstraksi=it)
            for it in cluster_items
        ])

    return hasil
