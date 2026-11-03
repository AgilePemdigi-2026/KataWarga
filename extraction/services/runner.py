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

from extraction.models import HasilEkstraksi
from reviews.models import Ulasan

logger = logging.getLogger('extraction.pipeline')


@dataclass
class Ringkasan:
    diproses: int = 0      # ulasan yang dicoba
    hasil: int = 0         # baris HasilEkstraksi yang dibuat (atau akan, pada dry-run)
    tanpa_hasil: int = 0   # ulasan tanpa hasil, ditandai DIBUANG
    gagal: int = 0         # ulasan yang memicu error ekstraktor (dibiarkan untuk percobaan berikutnya)


def _kandidat(aplikasi_pkg=None):
    qs = Ulasan.objects.filter(
        status_filter=Ulasan.StatusFilter.LOLOS, hasil_ekstraksi_set__isnull=True,
    ).order_by('id')
    if aplikasi_pkg:
        qs = qs.filter(aplikasi__package_name__in=aplikasi_pkg)
    return qs


def ekstrak_ulasan_baru(ekstraktor, *, batas=None, aplikasi_pkg=None, batch_size=100, dry_run=False):
    ringkasan = Ringkasan()
    terakhir_id = 0
    sisa = batas
    while sisa is None or sisa > 0:
        ukuran = batch_size if sisa is None else min(batch_size, sisa)
        batch = list(_kandidat(aplikasi_pkg).filter(id__gt=terakhir_id).select_related('aplikasi')[:ukuran])
        if not batch:
            break
        terakhir_id = batch[-1].id
        if sisa is not None:
            sisa -= len(batch)

        baru, kosong = [], []
        for ulasan in batch:
            ringkasan.diproses += 1
            try:
                daftar = ekstraktor.ekstrak(ulasan.isi_ulasan)
            except Exception as exc:  # error satu ulasan tidak boleh menghentikan pipeline
                ringkasan.gagal += 1
                logger.error('ulasan=%s ekstraksi gagal: %s: %s', ulasan.id, type(exc).__name__, exc)
                continue
            if not daftar:
                ringkasan.tanpa_hasil += 1
                kosong.append(ulasan.id)
                continue
            for h in daftar:
                baru.append(HasilEkstraksi(
                    ulasan=ulasan, teks_who=h.who, teks_what=h.what, teks_why=h.why,
                    skor_confidence=Decimal(str(round(max(0.0, min(1.0, h.confidence)), 4))),
                    status_validasi=HasilEkstraksi.StatusValidasi.MENUNGGU_VALIDASI,
                ))
            ringkasan.hasil += len(daftar)

        if not dry_run:
            with transaction.atomic():
                if baru:
                    HasilEkstraksi.objects.bulk_create(baru)
                if kosong:
                    Ulasan.objects.filter(id__in=kosong).update(status_filter=Ulasan.StatusFilter.DIBUANG)
    return ringkasan
