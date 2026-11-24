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
    # Hanya diisi ekstraktor LLM:
    user_story: str = ''     # "As a [who], I want to [what], so that [why]"
    evidence: str = ''       # kutipan ulasan yang mendukung
    evidence_why: str = ''   # kutipan ulasan yang menjadi dasar WHY
    sentimen: str = ''


class Ekstraktor(ABC):
    nama = 'ekstraktor'
    versi_prompt = ''
    model = ''

    @abstractmethod
    def ekstrak(self, teks):
        """Kembalikan list[HasilEkstrak] untuk satu ulasan; list kosong bila tidak ada."""

    def ekstrak_batch(self, daftar_teks):
        """
        Kembalikan list sejajar dengan `daftar_teks`. Tiap elemen adalah list[HasilEkstrak]
        atau instance Exception bila ulasan itu gagal (pipeline mencatat dan melanjutkan).
        """
        hasil = []
        for t in daftar_teks:
            try:
                hasil.append(self.ekstrak(t))
            except Exception as exc:
                hasil.append(exc)
        return hasil

    def ambil_galat(self):
        """Kembalikan list[(indeks, jenis, pesan)] penolakan sejak panggilan terakhir, lalu kosongkan."""
        return []
