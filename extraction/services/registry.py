"""Pemilihan ekstraktor berdasarkan nama terdaftar atau dotted path."""
from django.conf import settings
from django.utils.module_loading import import_string

from extraction.services.base import Ekstraktor

# nama -> dotted path (diimpor saat dibutuhkan, supaya library berat tidak dimuat bila tak dipakai)
REGISTRI = {
    'aturan': 'extraction.services.aturan.EkstraktorAturan',
    'gemini': 'extraction.services.gemini.EkstraktorGemini',
    'kampus': 'extraction.services.gemini.EkstraktorKampus',
}


def get_ekstraktor(nama=None):
    nama = nama or settings.EXTRACTION['ekstraktor']
    path = REGISTRI.get(nama, nama)
    try:
        kelas = import_string(path)
    except ImportError as exc:
        raise ValueError(
            f"Ekstraktor '{nama}' tidak dikenal. Pilihan terdaftar: {', '.join(REGISTRI)} "
            'atau dotted path ke kelas Ekstraktor.') from exc
    if not (isinstance(kelas, type) and issubclass(kelas, Ekstraktor)):
        raise ValueError(f"'{path}' bukan turunan Ekstraktor.")
    if kelas.__name__ == 'EkstraktorAturan':
        return kelas(max_hasil=settings.EXTRACTION.get('max_hasil_per_ulasan', 3))
    return kelas()
