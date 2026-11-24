"""
Penarikan ulasan dari Google Play Store (FR-EKS-03, FR-EKS-10).

- Jeda antar-permintaan dan backoff bertahap (§3.2.3) agar tidak kena pembatasan akses.
- Mengalirkan hasil per batch, sehingga kegagalan di tengah jalan tidak membuang
  batch yang sudah tersimpan (graceful degradation, §0 aturan 7).
- `fetcher` dan `sleep` dapat disuntikkan supaya mudah diuji tanpa jaringan.
"""
import logging
import time

logger = logging.getLogger('reviews.scraping')


class ScrapingError(Exception):
    """Penarikan ulasan gagal setelah seluruh percobaan ulang habis."""


def _fetcher_play_store(package_name, lang, country, count, token, skor=None):
    # Import di sini agar modul ini tetap bisa diimpor/diuji tanpa library terpasang.
    from google_play_scraper import Sort, reviews

    return reviews(
        package_name,
        lang=lang,
        country=country,
        sort=Sort.NEWEST,
        count=count,
        filter_score_with=skor,  # None = semua bintang; 1..5 = hanya bintang itu
        continuation_token=token,
    )


def _fetch_dengan_retry(fetcher, package_name, lang, country, count, token,
                        max_retry, backoff_dasar, sleep, skor=None):
    percobaan = 0
    while True:
        try:
            extra = {'skor': skor} if skor else {}
            return fetcher(package_name, lang, country, count, token, **extra)
        except Exception as exc:  # library eksternal: jenis error tidak seragam
            percobaan += 1
            if percobaan > max_retry:
                raise ScrapingError(f'{type(exc).__name__}: {exc}') from exc
            tunggu = backoff_dasar * (2 ** (percobaan - 1))
            logger.warning(
                'app=%s percobaan=%s/%s gagal (%s). Ulangi dalam %.1f detik.',
                package_name, percobaan, max_retry, exc, tunggu,
            )
            sleep(tunggu)


def tarik_ulasan(package_name, *, jumlah, lang='id', country='id', batch_size=200,
                 jeda=2.0, max_retry=4, backoff_dasar=2.0, fetcher=None, sleep=time.sleep, skor=None):
    """
    Generator: menghasilkan list ulasan (dict apa adanya dari google-play-scraper)
    per batch, paling banyak `jumlah` ulasan secara total, terbaru lebih dulu.
    """
    fetcher = fetcher or _fetcher_play_store
    sisa = jumlah
    token = None
    while sisa > 0:
        hasil, token = _fetch_dengan_retry(
            fetcher, package_name, lang, country, min(batch_size, sisa), token,
            max_retry, backoff_dasar, sleep, skor=skor,
        )
        if not hasil:
            break
        hasil = hasil[:sisa]
        sisa -= len(hasil)
        yield hasil
        if token is None or sisa <= 0:
            break
        sleep(jeda)
