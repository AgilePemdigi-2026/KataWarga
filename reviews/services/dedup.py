"""Deteksi duplikasi teks ulasan (Sprint 3 bagian B).

Dua ulasan dianggap duplikat bila teksnya sama setelah normalisasi pada aplikasi yang sama.
Duplikat dibuang agar frekuensi kebutuhan tidak digelembungkan oleh satu pengguna/penyebar yang sama.
"""
from reviews.models import Ulasan
from reviews.services.filtering import kunci_duplikat


def kunci_teks_lolos(aplikasi):
    """Kunci teks semua ulasan LOLOS yang sudah tersimpan untuk satu aplikasi."""
    if aplikasi is None or aplikasi.pk is None:
        return set()
    teks = Ulasan.objects.filter(
        aplikasi=aplikasi, status_filter=Ulasan.StatusFilter.LOLOS,
    ).values_list('isi_ulasan', flat=True)
    return {kunci_duplikat(t) for t in teks.iterator()}
