"""
Menyimpan ulasan hasil scraping ke basis data (FR-EKS-03/04/05, TBD-10).
"""
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import transaction

from reviews.models import Ulasan
from reviews.services import dedup, filtering


@dataclass
class Hasil:
    diterima: int = 0   # ulasan valid yang diproses
    baru: int = 0       # benar-benar tersimpan (atau akan, pada dry-run)
    duplikat: int = 0   # sudah ada di basis data / berulang dalam satu batch
    lolos: int = 0      # dari yang baru: status LOLOS
    dibuang: int = 0    # dari yang baru: status DIBUANG
    dilewati: int = 0   # data rusak (tanpa id/isi/tanggal)

    def tambah(self, lain):
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(self, f) + getattr(lain, f))


def samarkan_username(username, kunci=None):
    """Pseudonim satu arah (HMAC-SHA256): konsisten per pengguna, tidak bisa dibalik. # TBD-10"""
    if not username:
        return ''
    kunci = (kunci or settings.SECRET_KEY).encode()
    digest = hmac.new(kunci, username.strip().lower().encode(), hashlib.sha256).hexdigest()
    return f'pengguna-{digest[:10]}'


def _tanggal(nilai):
    if isinstance(nilai, datetime):
        return nilai.date()
    return nilai  # sudah date, atau None


def simpan_batch(aplikasi, batch, *, dry_run=False, cfg=None):
    """Simpan satu batch ulasan. Idempoten: ulasan yang sama tidak tersimpan dua kali."""
    cfg = cfg or settings.SCRAPING
    hasil = Hasil()

    kandidat = {}
    for item in batch:
        review_id = item.get('reviewId')
        isi = (item.get('content') or '').strip()
        tanggal = _tanggal(item.get('at'))
        skor = item.get('score')
        if not review_id or not isi or tanggal is None or not skor:
            hasil.dilewati += 1
            continue
        hasil.diterima += 1
        if review_id in kandidat:
            hasil.duplikat += 1
            continue
        kandidat[review_id] = (item, isi, tanggal, skor)

    sudah_ada = set(
        Ulasan.objects.filter(aplikasi=aplikasi, review_id__in=list(kandidat))
        .values_list('review_id', flat=True)
    )

    teks_lolos = dedup.kunci_teks_lolos(aplikasi) if kandidat else set()

    baru = []
    for review_id, (item, isi, tanggal, skor) in kandidat.items():
        if review_id in sudah_ada:
            hasil.duplikat += 1
            continue
        skor_int = max(1, min(5, int(skor)))
        keputusan = filtering.evaluasi_ulasan(isi, skor_int, cfg)
        lolos, alasan = keputusan.lolos, keputusan.alasan
        if lolos:
            kunci = filtering.kunci_duplikat(isi)
            if kunci in teks_lolos:
                lolos, alasan = False, filtering.ALASAN_DUPLIKAT
            else:
                teks_lolos.add(kunci)
        username = item.get('userName') or ''
        if cfg.get('samarkan_username', True):
            username = samarkan_username(username)
        baru.append(Ulasan(
            aplikasi=aplikasi,
            review_id=review_id,
            username_reviewer=username[:150],
            isi_ulasan=isi,
            tanggal_ulasan=tanggal,
            skor_bintang=skor_int,
            status_filter=Ulasan.StatusFilter.LOLOS if lolos else Ulasan.StatusFilter.DIBUANG,
            alasan_filter=alasan,
        ))
        hasil.baru += 1
        if lolos:
            hasil.lolos += 1
        else:
            hasil.dibuang += 1

    if baru and not dry_run:
        with transaction.atomic():
            Ulasan.objects.bulk_create(baru, ignore_conflicts=True)
    return hasil
