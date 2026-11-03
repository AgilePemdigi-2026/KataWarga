"""
Antarmuka ekstraktor who-what-why (FR-EKS-06).

Pipeline hanya bergantung pada kelas `Ekstraktor`. Untuk memasang model baru
(mis. IndoBERT token classification, format BIO):
  1. buat kelas turunan `Ekstraktor` dan implementasikan `ekstrak()`
     (override `ekstrak_batch()` bila model lebih efisien memproses banyak teks sekaligus);
  2. daftarkan di `REGISTRI` (extraction/services/registry.py) atau isi
     settings.EXTRACTION['ekstraktor'] dengan dotted path-nya.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class HasilEkstrak:
    """Satu hasil ekstraksi dari satu ulasan (belum disimpan ke basis data)."""
    what: str                # kebutuhan/masalah (wajib)
    who: str = ''            # pemangku kepentingan (boleh kosong)
    why: str = ''            # alasan/dampak (boleh kosong)
    confidence: float = 0.0  # 0..1; untuk ekstraktor aturan ini heuristik, bukan probabilitas model


class Ekstraktor(ABC):
    nama = 'ekstraktor'

    @abstractmethod
    def ekstrak(self, teks):
        """Kembalikan list[HasilEkstrak] untuk satu ulasan; list kosong bila tidak ada."""

    def ekstrak_batch(self, daftar_teks):
        """Kembalikan list[list[HasilEkstrak]] sejajar dengan `daftar_teks`."""
        return [self.ekstrak(t) for t in daftar_teks]
