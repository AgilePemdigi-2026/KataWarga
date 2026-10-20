"""
Layanan perhitungan skor prioritas dan kategori user story (§7, TBD-02).
Rumus murni dan deterministik berdasarkan konfigurasi settings.STORY_SCORING.
"""
from django.conf import settings
from stories.models import UserStory


def get_scoring_config():
    """Ambil konfigurasi skor dari settings.STORY_SCORING (# USULAN / # TBD-02)."""
    default_config = {
        'min_ulasan': 5,
        'n_ref': 100,
        'bobot_f': 0.7,
        'bobot_s': 0.3,
        'batas_tinggi': 70,
        'batas_sedang': 35,
    }
    return getattr(settings, 'STORY_SCORING', default_config)


def hitung_frekuensi(n, n_ref):
    """F = min(n/n_ref, 1) * 100"""
    if n_ref <= 0:
        return 0.0
    return min(n / n_ref, 1.0) * 100.0


def hitung_sentimen(bintang_list):
    """
    S = rata-rata ((5 - skor_bintang) / 4 * 100) untuk ulasan unik.
    Rating 1 -> (4/4)*100 = 100 (sentimen negatif tertinggi)
    Rating 5 -> (0/4)*100 = 0
    """
    if not bintang_list:
        return 0.0
    total = sum(((5.0 - b) / 4.0 * 100.0) for b in bintang_list)
    return total / len(bintang_list)


def tentukan_kategori(skor, batas_tinggi, batas_sedang):
    """Kategori: >= batas_tinggi -> TINGGI, >= batas_sedang -> SEDANG, else RENDAH."""
    if skor >= batas_tinggi:
        return UserStory.LevelPrioritas.TINGGI
    elif skor >= batas_sedang:
        return UserStory.LevelPrioritas.SEDANG
    return UserStory.LevelPrioritas.RENDAH


def hitung_skor_cluster(cluster, config=None):
    """
    Hitung signifikansi dan metrik skor untuk sebuah cluster.
    Mengambil ulasan unik dari anggota cluster.
    Return dict metrik:
      {
        'n': int,
        'cukup_signifikan': bool,
        'f': float,
        's': float,
        'skor': float,
        'kategori': str,
        'bintang_list': list[int],
      }
    """
    cfg = config or get_scoring_config()
    min_ulasan = cfg.get('min_ulasan', 5)
    n_ref = cfg.get('n_ref', 100)
    bobot_f = cfg.get('bobot_f', 0.7)
    bobot_s = cfg.get('bobot_s', 0.3)
    batas_tinggi = cfg.get('batas_tinggi', 70)
    batas_sedang = cfg.get('batas_sedang', 35)

    # Ambil ulasan unik melalui ClusterAnggota -> HasilEkstraksi -> Ulasan
    # Menggunakan dict berdasarkan ulasan_id agar deduplikasi pasti dan mengambil skor bintang
    ulasan_map = {}
    for anggota in cluster.anggota_set.select_related('hasil_ekstraksi__ulasan'):
        ekstraksi = anggota.hasil_ekstraksi
        if ekstraksi and ekstraksi.ulasan:
            u = ekstraksi.ulasan
            if u.id not in ulasan_map:
                ulasan_map[u.id] = u

    n = len(ulasan_map)
    cluster.skor_signifikansi = n

    if n < min_ulasan:
        return {
            'n': n,
            'cukup_signifikan': False,
            'f': 0.0,
            's': 0.0,
            'skor': 0.0,
            'kategori': UserStory.LevelPrioritas.RENDAH,
            'bintang_list': [],
            'ulasan_list': [],
        }

    bintang_list = [u.skor_bintang for u in ulasan_map.values()]
    f = hitung_frekuensi(n, n_ref)
    s = hitung_sentimen(bintang_list)
    skor = round(bobot_f * f + bobot_s * s, 2)
    kategori = tentukan_kategori(skor, batas_tinggi, batas_sedang)

    return {
        'n': n,
        'cukup_signifikan': True,
        'f': round(f, 2),
        's': round(s, 2),
        'skor': skor,
        'kategori': kategori,
        'bintang_list': bintang_list,
        'ulasan_list': list(ulasan_map.values()),
    }
