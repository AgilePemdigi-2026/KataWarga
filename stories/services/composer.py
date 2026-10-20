"""
Layanan penyusunan user story dari cluster tervalidasi (§6.3, FR-USR-01 s/d 10).
"""
import re
from collections import defaultdict, Counter
from django.db import transaction
from extraction.models import Cluster
from stories.models import UserStory
from stories.services import scoring


def normalisasi_teks(teks):
    """Lowercase, strip, dan rapikan spasi berlebih."""
    if not teks:
        return ''
    return re.sub(r'\s+', ' ', str(teks).strip().lower())


def pilih_elemen_representatif(ekstraksi_list, field_name):
    """
    Pilih elemen paling representatif dari daftar HasilEkstraksi (# TBD-03):
    1. Kelompokkan berdasarkan normalisasi teks
    2. Ambil kelompok dengan frekuensi kemunculan terbanyak
    3. Jika seri, pilih yang rata-rata skor_confidence tertinggi
    4. Kembalikan teks asli (representatif) dari kelompok terpilih
    """
    valid_items = []
    for item in ekstraksi_list:
        raw_val = getattr(item, field_name, '') or ''
        norm_val = normalisasi_teks(raw_val)
        if norm_val:
            conf = float(item.skor_confidence or 0.0)
            valid_items.append((norm_val, raw_val.strip(), conf))

    if not valid_items:
        return ''

    # Kelompokkan data
    groups = defaultdict(list)
    for norm_val, raw_val, conf in valid_items:
        groups[norm_val].append((raw_val, conf))

    # Cari kandidat dengan (frekuensi, avg_conf) tertinggi
    kandidat = []
    for norm_val, entries in groups.items():
        freq = len(entries)
        avg_conf = sum(c for _, c in entries) / freq
        # Pilih representasi teks asli pertama atau yang skornya tertinggi
        best_raw = max(entries, key=lambda x: x[1])[0]
        kandidat.append((freq, avg_conf, best_raw))

    # Urutkan: frekuensi menurun, lalu avg_conf menurun
    kandidat.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return kandidat[0][2]


def cari_aplikasi_terbanyak(cluster):
    """Cari nama aplikasi dengan ulasan terbanyak di cluster untuk fallback who (§6.3, FR-USR-04)."""
    counter = Counter()
    for anggota in cluster.anggota_set.select_related('hasil_ekstraksi__ulasan__aplikasi'):
        ekstraksi = anggota.hasil_ekstraksi
        if ekstraksi and ekstraksi.ulasan and ekstraksi.ulasan.aplikasi:
            counter[ekstraksi.ulasan.aplikasi.nama_aplikasi] += 1
    if counter:
        return counter.most_common(1)[0][0]
    return 'terkait'


def susun_kalimat(who, what, why):
    """
    Format: 'Sebagai {who}, saya ingin {what}, supaya {why}'.
    Jika why kosong: hilangkan ', supaya ...'.
    """
    kalimat = f"Sebagai {who}, saya ingin {what}"
    if why:
        kalimat += f", supaya {why}"
    return kalimat


@transaction.atomic
def compose_cluster(cluster):
    """
    Susun satu cluster menjadi UserStory.
    Idempoten: jika cluster sudah punya UserStory, kembalikan user story yang sudah ada.
    Jika ulasan unik < min_ulasan, tandai cluster DIABAIKAN, tanpa membuat story.
    """
    # Cek apakah sudah pernah dibuat (idempoten)
    if hasattr(cluster, 'user_story') and cluster.user_story:
        return cluster.user_story

    existing = UserStory.objects.filter(cluster=cluster).first()
    if existing:
        return existing

    # Hitung skor dan signifikansi
    metrik = scoring.hitung_skor_cluster(cluster)
    cluster.skor_signifikansi = metrik['n']

    if not metrik['cukup_signifikan']:
        cluster.status_cluster = Cluster.StatusCluster.DIABAIKAN
        cluster.save(update_fields=['skor_signifikansi', 'status_cluster'])
        return None

    # Ambil semua hasil ekstraksi anggota cluster
    ekstraksi_list = [
        anggota.hasil_ekstraksi
        for anggota in cluster.anggota_set.select_related('hasil_ekstraksi')
        if anggota.hasil_ekstraksi
    ]

    who = pilih_elemen_representatif(ekstraksi_list, 'teks_who')
    what = pilih_elemen_representatif(ekstraksi_list, 'teks_what')
    why = pilih_elemen_representatif(ekstraksi_list, 'teks_why')

    # Fallback who jika kosong (FR-USR-04)
    if not who:
        nama_app = cari_aplikasi_terbanyak(cluster)
        who = f"pengguna aplikasi {nama_app}"

    # Jika what kosong (fallback darurat dari nama topik cluster)
    if not what:
        what = cluster.nama_topik

    story = UserStory.objects.create(
        cluster=cluster,
        peran=who,
        kebutuhan=what,
        alasan=why,
        skor_prioritas=metrik['skor'],
        kategori_prioritas=metrik['kategori'],
        status_persetujuan=UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN,
    )

    cluster.status_cluster = Cluster.StatusCluster.SIGNIFIKAN
    cluster.save(update_fields=['skor_signifikansi', 'status_cluster'])

    return story


def compose_pending():
    """
    Susun semua cluster berstatus TERVALIDASI yang belum memiliki user story.
    Mengembalikan daftar UserStory yang berhasil dibuat.
    """
    clusters = Cluster.objects.filter(
        status_cluster=Cluster.StatusCluster.TERVALIDASI,
        user_story__isnull=True,
    ).order_by('id')

    stories_created = []
    for c in clusters:
        story = compose_cluster(c)
        if story:
            stories_created.append(story)
    return stories_created
