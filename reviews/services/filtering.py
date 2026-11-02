"""
Filter ulasan terlalu pendek / generik (FR-EKS-05, Project_Context §8, TBD-01).

Aturan (semua dapat diatur lewat settings.SCRAPING):
- jumlah kata < min_kata            -> DIBUANG
- isi ulasan hanya berupa pola generik (mis. "bagus", "mantap!!!") -> DIBUANG
- selain itu                        -> LOLOS
"""
import re

ALASAN_PENDEK = 'terlalu pendek'
ALASAN_GENERIK = 'generik'


def normalisasi(teks):
    """Huruf kecil, buang tanda baca/emoji, rapikan spasi, dan ringkas huruf berulang."""
    if not teks:
        return ''
    teks = str(teks).lower()
    teks = re.sub(r'[^\w\s]|_', ' ', teks)
    teks = re.sub(r'(\w)\1+', r'\1', teks)  # "bagusss" -> "bagus", "mantapp" -> "mantap"
    return re.sub(r'\s+', ' ', teks).strip()


def hitung_kata(teks):
    return len(re.findall(r'\w+', teks or ''))


def periksa_ulasan(teks, min_kata, pola_generik):
    """
    Kembalikan (lolos: bool, alasan: str).
    `alasan` kosong bila lolos.
    """
    if hitung_kata(teks) < min_kata:
        return False, ALASAN_PENDEK
    pola = {normalisasi(p) for p in pola_generik}
    if normalisasi(teks) in pola:
        return False, ALASAN_GENERIK
    return True, ''
