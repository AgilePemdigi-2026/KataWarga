"""
Uji scraping (FR-EKS-03/04/05/10/11). Tanpa jaringan: fetcher Play Store diganti tiruan.
"""
from datetime import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from reviews.models import Aplikasi, Ulasan
from reviews.services import filtering, ingest, scraper

CFG_CEPAT = {
    'lang': 'id', 'country': 'id', 'jumlah_default': 10, 'batch_size': 5,
    'jeda_detik': 0, 'max_retry': 2, 'backoff_dasar_detik': 0,
    'min_kata': 3, 'pola_generik': ['bagus', 'mantap'], 'samarkan_username': True,
}


def ulasan_palsu(n, awal=0, isi='Aplikasi sering gagal login saat dibuka'):
    return [{
        'reviewId': f'rid-{awal + i}', 'userName': f'Budi {awal + i}',
        'content': f'{isi} {awal + i}', 'score': 1,
        'at': datetime(2026, 10, 1, 12, 0),
    } for i in range(n)]


class FilterTest(TestCase):
    def test_pendek_dan_generik_dibuang_ulasan_biasa_lolos(self):
        pola = ['bagus', 'mantap']
        self.assertEqual(filtering.periksa_ulasan('bagus', 3, pola), (False, filtering.ALASAN_PENDEK))
        self.assertEqual(filtering.periksa_ulasan('Bagusss!!!', 1, pola), (False, filtering.ALASAN_GENERIK))
        self.assertEqual(filtering.periksa_ulasan('mantap  ', 1, pola)[0], False)
        self.assertEqual(filtering.periksa_ulasan('👍👍', 1, pola)[0], False)
        self.assertEqual(filtering.periksa_ulasan('gagal login terus', 3, pola), (True, ''))

    def test_bagus_untuk_satu_sehat_tidak_lolos_filter(self):
        a = Aplikasi.objects.create(nama_aplikasi='SATU SEHAT', package_name='x.satusehat')
        batch = [{'reviewId': 'r1', 'userName': 'a', 'content': 'bagus', 'score': 5,
                  'at': datetime(2026, 10, 1)}]
        ingest.simpan_batch(a, batch, cfg=CFG_CEPAT)
        self.assertEqual(Ulasan.objects.get().status_filter, Ulasan.StatusFilter.DIBUANG)


class IngestTest(TestCase):
    def setUp(self):
        self.app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')

    def test_penarikan_berulang_tidak_menggandakan_data(self):
        batch = ulasan_palsu(4)
        h1 = ingest.simpan_batch(self.app, batch, cfg=CFG_CEPAT)
        h2 = ingest.simpan_batch(self.app, batch, cfg=CFG_CEPAT)
        self.assertEqual((h1.baru, h1.duplikat), (4, 0))
        self.assertEqual((h2.baru, h2.duplikat), (0, 4))
        self.assertEqual(Ulasan.objects.count(), 4)

    def test_duplikat_dalam_satu_batch_hanya_disimpan_sekali(self):
        batch = ulasan_palsu(2) + ulasan_palsu(1)
        h = ingest.simpan_batch(self.app, batch, cfg=CFG_CEPAT)
        self.assertEqual(Ulasan.objects.count(), 2)
        self.assertEqual(h.duplikat, 1)

    def test_username_disamarkan_dan_konsisten(self):
        ingest.simpan_batch(self.app, ulasan_palsu(1), cfg=CFG_CEPAT)
        u = Ulasan.objects.get()
        self.assertNotIn('Budi', u.username_reviewer)
        self.assertTrue(u.username_reviewer.startswith('pengguna-'))
        self.assertEqual(ingest.samarkan_username('Budi 0'), ingest.samarkan_username(' budi 0 '))

    def test_data_rusak_dilewati(self):
        h = ingest.simpan_batch(self.app, [{'reviewId': None, 'content': 'x'}, {}], cfg=CFG_CEPAT)
        self.assertEqual((h.dilewati, Ulasan.objects.count()), (2, 0))

    def test_dry_run_tidak_menulis(self):
        h = ingest.simpan_batch(self.app, ulasan_palsu(3), dry_run=True, cfg=CFG_CEPAT)
        self.assertEqual((h.baru, Ulasan.objects.count()), (3, 0))


class ScraperTest(TestCase):
    def test_retry_dengan_backoff_bertahap_lalu_berhasil(self):
        panggilan, jeda = [], []

        def fetcher(pkg, lang, country, count, token):
            panggilan.append(1)
            if len(panggilan) < 3:
                raise ConnectionError('putus')
            return ulasan_palsu(2), None

        batches = list(scraper.tarik_ulasan(
            'x', jumlah=2, max_retry=3, backoff_dasar=2.0, fetcher=fetcher, sleep=jeda.append))
        self.assertEqual(len(batches), 1)
        self.assertEqual(jeda, [2.0, 4.0])  # backoff: 2, 4 detik

    def test_gagal_setelah_retry_habis(self):
        def fetcher(*a):
            raise TimeoutError('lambat')
        with self.assertRaises(scraper.ScrapingError):
            list(scraper.tarik_ulasan('x', jumlah=5, max_retry=1, backoff_dasar=0,
                                      fetcher=fetcher, sleep=lambda s: None))

    def test_paginasi_dan_batas_jumlah(self):
        def fetcher(pkg, lang, country, count, token):
            awal = token or 0
            return ulasan_palsu(count, awal=awal), awal + count
        hasil = [u for b in scraper.tarik_ulasan(
            'x', jumlah=12, batch_size=5, fetcher=fetcher, sleep=lambda s: None) for u in b]
        self.assertEqual(len(hasil), 12)
        self.assertEqual(len({u['reviewId'] for u in hasil}), 12)


@override_settings(SCRAPING=CFG_CEPAT)
class CommandTest(TestCase):
    def setUp(self):
        self.a = Aplikasi.objects.create(nama_aplikasi='A', package_name='pkg.a')
        self.b = Aplikasi.objects.create(nama_aplikasi='B', package_name='pkg.b')

    def _jalankan(self, **kw):
        out, err = StringIO(), StringIO()
        call_command('scrape_reviews', stdout=out, stderr=err, **kw)
        return out.getvalue()

    def test_happy_path_dan_jalan_ulang_tidak_menggandakan(self):
        def fetcher(pkg, lang, country, count, token):
            return ulasan_palsu(count), None
        with patch.object(scraper, '_fetcher_play_store', fetcher):
            self._jalankan(count=3)
            self._jalankan(count=3)
        self.assertEqual(Ulasan.objects.filter(aplikasi=self.a).count(), 3)
        self.assertEqual(Ulasan.objects.filter(aplikasi=self.b).count(), 3)

    def test_gagal_di_satu_aplikasi_tidak_menghentikan_yang_lain_dan_data_lama_aman(self):
        Ulasan.objects.create(aplikasi=self.a, review_id='lama', isi_ulasan='data lama',
                              tanggal_ulasan='2026-09-01', skor_bintang=3)

        def fetcher(pkg, lang, country, count, token):
            if pkg == 'pkg.a':
                raise ConnectionError('Play Store tidak dapat diakses')
            return ulasan_palsu(count), None

        with patch.object(scraper, '_fetcher_play_store', fetcher):
            with self.assertRaises(CommandError):  # kode keluar != 0 untuk cron
                self._jalankan(count=3)
        self.assertTrue(Ulasan.objects.filter(review_id='lama').exists())
        self.assertEqual(Ulasan.objects.filter(aplikasi=self.b).count(), 3)

    def test_dry_run_tidak_menyimpan(self):
        with patch.object(scraper, '_fetcher_play_store',
                          lambda *a: (ulasan_palsu(3), None)):
            self._jalankan(count=3, dry_run=True)
        self.assertEqual(Ulasan.objects.count(), 0)

    def test_filter_app(self):
        with patch.object(scraper, '_fetcher_play_store', lambda *a: (ulasan_palsu(2), None)):
            self._jalankan(count=2, app=['pkg.b'])
        self.assertEqual(Ulasan.objects.filter(aplikasi=self.a).count(), 0)
        self.assertEqual(Ulasan.objects.filter(aplikasi=self.b).count(), 2)

    @override_settings(SCRAPER_TARGET_APPS=[
        {'nama_aplikasi': 'Lengkap', 'package_name': 'pkg.ok', 'kategori': 'X'},
        {'nama_aplikasi': 'Kosong', 'package_name': '', 'kategori': 'Y'},
    ])
    def test_seed_melewati_package_kosong(self):
        Aplikasi.objects.all().delete()
        with patch.object(scraper, '_fetcher_play_store', lambda *a: ([], None)):
            self._jalankan(seed=True)
        self.assertEqual(list(Aplikasi.objects.values_list('package_name', flat=True)), ['pkg.ok'])

    def test_tanpa_aplikasi_memberi_pesan_jelas(self):
        Aplikasi.objects.all().delete()
        with self.assertRaises(CommandError):
            self._jalankan()


def test_skor_diteruskan_ke_fetcher():
    panggilan = []

    def fetcher(pkg, lang, country, count, token, skor=None):
        panggilan.append(skor)
        return [{'reviewId': 'a'}], None

    list(scraper.tarik_ulasan('x', jumlah=1, fetcher=fetcher, sleep=lambda s: None, skor=1))
    list(scraper.tarik_ulasan('x', jumlah=1, fetcher=fetcher, sleep=lambda s: None))
    assert panggilan == [1, None]
