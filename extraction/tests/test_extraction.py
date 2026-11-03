"""
Uji ekstraksi who-what-why (FR-EKS-06, O-1): ekstraktor aturan, registri, runner, dan command.
Tanpa jaringan dan tanpa model ML.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from extraction.models import HasilEkstraksi
from extraction.services import registry, runner
from extraction.services.aturan import EkstraktorAturan
from extraction.services.base import Ekstraktor, HasilEkstrak
from reviews.models import Aplikasi, Ulasan


class EkstraktorAturanTest(TestCase):
    def setUp(self):
        self.e = EkstraktorAturan()

    def test_what_dan_why_dipisah_dengan_penanda_tujuan(self):
        (h,) = self.e.ekstrak(
            'Saya ingin bisa download rekam medis saya langsung dari aplikasi ini agar lebih mudah saat ke dokter.')
        self.assertEqual(h.what, 'bisa download rekam medis saya langsung dari aplikasi ini')
        self.assertEqual(h.why, 'lebih mudah saat ke dokter')
        self.assertEqual(h.who, '')  # "ke dokter" bukan pemangku kepentingan

    def test_who_dari_pola_sebagai(self):
        (h,) = self.e.ekstrak('Sebagai wajib pajak, saya sulit login karena OTP tidak pernah masuk')
        self.assertEqual((h.who, h.what, h.why), ('wajib pajak', 'sulit login', 'OTP tidak pernah masuk'))

    def test_klausa_diawali_penyebab(self):
        (h,) = self.e.ekstrak('Karena sering error, saya jadi susah lapor SPT')
        self.assertEqual((h.what, h.why), ('susah lapor SPT', 'sering error'))

    def test_permintaan_umum_tidak_jadi_what_tapi_alasannya_dipakai(self):
        hasil = self.e.ekstrak('Aplikasi tidak bisa dibuka setelah update terbaru. '
                               'Tolong segera diperbaiki karena sangat mengganggu aktivitas.')
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0].what, 'Aplikasi tidak bisa dibuka setelah update terbaru')
        self.assertEqual(hasil[0].why, 'sangat mengganggu aktivitas')

    def test_satu_ulasan_bisa_banyak_hasil_dan_dibatasi(self):
        teks = 'Login gagal terus. OTP tidak masuk. Aplikasi sangat lambat. Data hilang semua.'
        self.assertEqual(len(EkstraktorAturan(max_hasil=3).ekstrak(teks)), 3)
        self.assertEqual(len(EkstraktorAturan(max_hasil=10).ekstrak(teks)), 4)

    def test_ulasan_tanpa_masalah_atau_kebutuhan_tidak_menghasilkan_apa_apa(self):
        self.assertEqual(self.e.ekstrak('Terima kasih banyak aplikasinya sangat membantu'), [])
        self.assertEqual(self.e.ekstrak(''), [])
        self.assertEqual(self.e.ekstrak(None), [])

    def test_confidence_dibatasi_dan_batas_panjang_model(self):
        panjang = 'tidak bisa ' + 'x' * 2000
        (h,) = self.e.ekstrak(f'Sebagai pasien, {panjang} agar {"y" * 2000}')
        self.assertLessEqual(h.confidence, EkstraktorAturan.CONFIDENCE_MAKS)
        self.assertLessEqual(len(h.what), 1000)
        self.assertLessEqual(len(h.why), 1000)
        self.assertLessEqual(len(h.who), 100)


class RegistriTest(TestCase):
    def test_nama_terdaftar_dan_dotted_path(self):
        self.assertIsInstance(registry.get_ekstraktor('aturan'), EkstraktorAturan)
        self.assertIsInstance(
            registry.get_ekstraktor('extraction.services.aturan.EkstraktorAturan'), EkstraktorAturan)

    def test_nama_tidak_dikenal_atau_bukan_ekstraktor(self):
        with self.assertRaises(ValueError):
            registry.get_ekstraktor('tidak.ada.modul.Kelas')
        with self.assertRaises(ValueError):
            registry.get_ekstraktor('decimal.Decimal')


class EkstraktorPalsu(Ekstraktor):
    nama = 'palsu'

    def ekstrak(self, teks):
        if 'RUSAK' in teks:
            raise RuntimeError('model gagal')
        if 'KOSONG' in teks:
            return []
        return [HasilEkstrak(what='masalah login', why='alasan', who='warga', confidence=0.9)]


class RunnerTest(TestCase):
    def setUp(self):
        self.app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')
        self.app2 = Aplikasi.objects.create(nama_aplikasi='SS', package_name='x.ss')

    def _ulasan(self, isi, app=None, status=Ulasan.StatusFilter.LOLOS):
        return Ulasan.objects.create(aplikasi=app or self.app, isi_ulasan=isi, tanggal_ulasan='2026-10-01',
                                     skor_bintang=1, status_filter=status)

    def test_hasil_tersimpan_menunggu_validasi_dan_idempoten(self):
        self._ulasan('login gagal terus')
        r1 = runner.ekstrak_ulasan_baru(EkstraktorPalsu())
        r2 = runner.ekstrak_ulasan_baru(EkstraktorPalsu())
        self.assertEqual((r1.diproses, r1.hasil, r2.diproses), (1, 1, 0))
        h = HasilEkstraksi.objects.get()
        self.assertEqual(h.status_validasi, HasilEkstraksi.StatusValidasi.MENUNGGU_VALIDASI)
        self.assertEqual((h.teks_who, h.teks_what, h.teks_why), ('warga', 'masalah login', 'alasan'))
        self.assertEqual(h.skor_confidence, Decimal('0.9000'))

    def test_ulasan_dibuang_tidak_diproses(self):
        self._ulasan('bagus', status=Ulasan.StatusFilter.DIBUANG)
        self.assertEqual(runner.ekstrak_ulasan_baru(EkstraktorPalsu()).diproses, 0)

    def test_tanpa_hasil_ditandai_dibuang_agar_o1_terpenuhi(self):
        u = self._ulasan('KOSONG')
        r = runner.ekstrak_ulasan_baru(EkstraktorPalsu())
        u.refresh_from_db()
        self.assertEqual(r.tanpa_hasil, 1)
        self.assertEqual(u.status_filter, Ulasan.StatusFilter.DIBUANG)

    def test_error_satu_ulasan_tidak_menghentikan_pipeline_dan_ulasan_tetap_lolos(self):
        rusak = self._ulasan('RUSAK')
        self._ulasan('login gagal')
        r = runner.ekstrak_ulasan_baru(EkstraktorPalsu(), batch_size=1)
        rusak.refresh_from_db()
        self.assertEqual((r.gagal, r.hasil), (1, 1))
        self.assertEqual(rusak.status_filter, Ulasan.StatusFilter.LOLOS)  # dicoba lagi pada jalan berikutnya
        self.assertEqual(HasilEkstraksi.objects.count(), 1)

    def test_dry_run_limit_dan_filter_app(self):
        for i in range(5):
            self._ulasan(f'ulasan {i}')
        self._ulasan('dari app lain', app=self.app2)
        runner.ekstrak_ulasan_baru(EkstraktorPalsu(), dry_run=True)
        self.assertEqual(HasilEkstraksi.objects.count(), 0)
        runner.ekstrak_ulasan_baru(EkstraktorPalsu(), batas=2, batch_size=1)
        self.assertEqual(HasilEkstraksi.objects.count(), 2)
        runner.ekstrak_ulasan_baru(EkstraktorPalsu(), aplikasi_pkg=['x.ss'])
        self.assertTrue(HasilEkstraksi.objects.filter(ulasan__aplikasi=self.app2).exists())
        self.assertEqual(HasilEkstraksi.objects.filter(ulasan__aplikasi=self.app).count(), 2)


class CommandTest(TestCase):
    def setUp(self):
        app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')
        Ulasan.objects.create(aplikasi=app, isi_ulasan='Aplikasi selalu force close saat login',
                              tanggal_ulasan='2026-10-01', skor_bintang=1)

    def test_command_dengan_ekstraktor_aturan(self):
        out = StringIO()
        call_command('extract_reviews', stdout=out)
        self.assertIn('hasil=1', out.getvalue())
        self.assertEqual(HasilEkstraksi.objects.count(), 1)

    def test_ekstraktor_tidak_dikenal_memberi_pesan_jelas(self):
        with self.assertRaises(CommandError):
            call_command('extract_reviews', extractor='tidak.ada.Kelas', stdout=StringIO())
