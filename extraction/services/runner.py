"""
Menjalankan ekstraksi atas ulasan yang lolos filter dan belum punya hasil (FR-EKS-06).

- Idempoten: hanya memproses ulasan LOLOS yang belum punya HasilEkstraksi.
- Kegagalan pada satu ulasan dicatat dan dilewati; pipeline tetap jalan (graceful degradation).
- Ulasan yang tidak menghasilkan apa pun ditandai DIBUANG, sehingga O-1 terpenuhi
  ("punya hasil ekstraksi atau status filter tercatat").
"""
import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from extraction.models import GalatEkstraksi, HasilEkstraksi
from reviews.models import Ulasan

logger = logging.getLogger('extraction.pipeline')


@dataclass
class Ringkasan:
    diproses: int = 0      # ulasan yang dicoba
    hasil: int = 0         # baris HasilEkstraksi yang dibuat (atau akan, pada dry-run)
    tanpa_hasil: int = 0   # ulasan tanpa hasil, ditandai DIBUANG
    gagal: int = 0         # ulasan yang memicu error ekstraktor (dibiarkan untuk percobaan berikutnya)


def _kandidat(aplikasi_pkg=None, bintang_min=None, bintang_maks=None):
    qs = Ulasan.objects.filter(
        status_filter=Ulasan.StatusFilter.LOLOS, hasil_ekstraksi_set__isnull=True,
    ).order_by('id')
    if aplikasi_pkg:
        qs = qs.filter(aplikasi__package_name__in=aplikasi_pkg)
    if bintang_min:
        qs = qs.filter(skor_bintang__gte=bintang_min)
    if bintang_maks:
        qs = qs.filter(skor_bintang__lte=bintang_maks)
    return qs


def ekstrak_ulasan_baru(ekstraktor, *, batas=None, aplikasi_pkg=None, batch_size=100, dry_run=False,
                        bintang_min=None, bintang_maks=None):
    ringkasan = Ringkasan()
    terakhir_id = 0
    sisa = batas
    while sisa is None or sisa > 0:
        ukuran = batch_size if sisa is None else min(batch_size, sisa)
        batch = list(_kandidat(aplikasi_pkg, bintang_min, bintang_maks).filter(id__gt=terakhir_id).select_related('aplikasi')[:ukuran])
        if not batch:
            break
        terakhir_id = batch[-1].id
        if sisa is not None:
            sisa -= len(batch)

        baru, kosong, galat = [], [], []
        daftar_hasil = ekstraktor.ekstrak_batch([u.isi_ulasan for u in batch])
        meta = dict(nama_ekstraktor=ekstraktor.nama, model_llm=ekstraktor.model,
                    versi_prompt=ekstraktor.versi_prompt)
        for ulasan, daftar in zip(batch, daftar_hasil):
            ringkasan.diproses += 1
            if isinstance(daftar, Exception):  # error satu ulasan tidak boleh menghentikan pipeline
                ringkasan.gagal += 1
                logger.error('ulasan=%s ekstraksi gagal: %s: %s', ulasan.id, type(daftar).__name__, daftar)
                galat.append(GalatEkstraksi(ulasan=ulasan, jenis=type(daftar).__name__,
                                            pesan=str(daftar)[:1000], nama_ekstraktor=ekstraktor.nama,
                                            versi_prompt=ekstraktor.versi_prompt))
                continue
            if not daftar:
                ringkasan.tanpa_hasil += 1
                kosong.append(ulasan.id)
                continue
            for h in daftar:
                baru.append(HasilEkstraksi(
                    ulasan=ulasan, teks_who=h.who, teks_what=h.what, teks_why=h.why,
                    skor_confidence=Decimal(str(round(max(0.0, min(1.0, h.confidence)), 4))),
                    kalimat_user_story=h.user_story, evidence=h.evidence, evidence_why=h.evidence_why,
                    sentimen=h.sentimen,
                    status_validasi=HasilEkstraksi.StatusValidasi.MENUNGGU_VALIDASI, **meta,
                ))
            ringkasan.hasil += len(daftar)
        for idx, jenis, pesan in ekstraktor.ambil_galat():
            galat.append(GalatEkstraksi(ulasan=batch[idx] if idx is not None else None, jenis=jenis,
                                        pesan=pesan[:1000], nama_ekstraktor=ekstraktor.nama,
                                        versi_prompt=ekstraktor.versi_prompt))

        if not dry_run:
            with transaction.atomic():
                if baru:
                    HasilEkstraksi.objects.bulk_create(baru)
                if galat:
                    GalatEkstraksi.objects.bulk_create(galat)
                if kosong:
                    Ulasan.objects.filter(id__in=kosong).update(
                        status_filter=Ulasan.StatusFilter.DIBUANG,
                        alasan_filter=Ulasan.AlasanFilter.TANPA_KEBUTUHAN,
                    )
    return ringkasan
