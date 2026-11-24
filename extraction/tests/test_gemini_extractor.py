"""Tes ekstraktor Gemini dengan klien palsu (tanpa jaringan)."""
from django.test import TestCase

from extraction.models import GalatEkstraksi, HasilEkstraksi
from extraction.services import registry, runner
from extraction.services.gemini import EkstraktorGemini
from extraction.services.llm import LLMTimeoutError
from extraction.services.llm.pii import samarkan_pii
from extraction.services.llm.prompt import VERSI_PROMPT, susun_prompt
from extraction.services.llm.verifikasi import Ditolak, susun_user_story, verifikasi_objek
from reviews.models import Aplikasi, Ulasan

TEKS = 'Saya tidak bisa login karena OTP tidak pernah masuk, jadi tidak bisa lapor SPT'


def obj(**kw):
    dasar = dict(review_id='0', who='wajib pajak', what='login ke aplikasi',
                 why='bisa lapor SPT', as_a_i_want_so_that='As a wajib pajak, I want to login ke aplikasi, so that bisa lapor SPT', why_evidence='tidak bisa lapor SPT',
                 evidence='tidak bisa login karena OTP tidak pernah masuk', sentiment='negative', confidence=0.9)
    dasar.update(kw)
    return dasar


class KlienPalsu:
    model = 'palsu-1'

    def __init__(self, jawaban):
        self.jawaban, self.prompt = jawaban, []

    def generate_json(self, prompt, schema, *, system_instruction=None):
        self.prompt.append(prompt)
        if isinstance(self.jawaban, Exception):
            raise self.jawaban
        return self.jawaban


class PiiTest(TestCase):
    def test_samarkan(self):
        t = samarkan_pii('NIK 3578 1234 5678 9012, hub 0812-3456-7890 / +628123456789, a.b@mail.co.id')
        self.assertEqual(t, 'NIK [NIK], hub [TELEPON] / [TELEPON], [EMAIL]')

    def test_angka_biasa_tidak_disamarkan(self):
        self.assertEqual(samarkan_pii('update versi 2.1.3 gagal 3 kali'), 'update versi 2.1.3 gagal 3 kali')


class VerifikasiTest(TestCase):
    def test_valid(self):
        h, catatan = verifikasi_objek(obj(), TEKS)
        self.assertIsNone(catatan)
        self.assertEqual((h.who, h.what, h.why), ('wajib pajak', 'login ke aplikasi', 'bisa lapor SPT'))
        self.assertTrue(h.user_story.startswith('As a wajib pajak, I want to login'))

    def test_evidence_harus_ada_di_ulasan(self):
        with self.assertRaises(Ditolak) as c:
            verifikasi_objek(obj(evidence='aplikasi sangat lambat'), TEKS)
        self.assertEqual(c.exception.jenis, 'evidence_tidak_ditemukan')

    def test_evidence_dua_potongan_dengan_elipsis(self):
        teks = 'ruwet, tidak bisa login. banyak hal lain. OTP tidak pernah masuk padahal sudah coba'
        h, _ = verifikasi_objek(obj(evidence='tidak bisa login ... OTP tidak pernah masuk',
                                    as_a_i_want_so_that='As a wajib pajak, I want to login ke aplikasi'), teks)
        self.assertIn('...', h.evidence)

    def test_elipsis_dengan_potongan_karangan_ditolak(self):
        with self.assertRaises(Ditolak):
            verifikasi_objek(obj(evidence='tidak bisa login ... layar putih terus'), TEKS)

    def test_evidence_kosong_dan_what_kosong(self):
        with self.assertRaises(Ditolak):
            verifikasi_objek(obj(evidence=''), TEKS)
        with self.assertRaises(Ditolak):
            verifikasi_objek(obj(what=''), TEKS)

    def test_format_template_salah(self):
        with self.assertRaises(Ditolak) as c:
            verifikasi_objek(obj(as_a_i_want_so_that='Saya ingin login'), TEKS)
        self.assertEqual(c.exception.jenis, 'format_template')

    def test_why_tanpa_kutipan_dasar_dikosongkan(self):
        h, catatan = verifikasi_objek(obj(why='menghemat waktu perjalanan', why_evidence='ke kantor pajak jauh'), TEKS)
        self.assertEqual(catatan, 'why_tanpa_dasar')
        self.assertEqual((h.why, h.evidence_why), ('', ''))
        self.assertEqual(h.user_story, 'As a wajib pajak, I want to login ke aplikasi')

    def test_why_kalimat_orang_pertama_dikosongkan(self):
        h, catatan = verifikasi_objek(obj(why='saya tidak bisa lapor SPT', why_evidence='tidak bisa lapor SPT'), TEKS)
        self.assertEqual(catatan, 'why_orang_pertama')
        self.assertEqual(h.why, '')

    def test_why_salinan_ulasan_dikosongkan(self):
        salinan = 'tidak bisa login karena OTP tidak pernah masuk jadi tidak bisa lapor'
        h, catatan = verifikasi_objek(obj(why=salinan, why_evidence='tidak bisa lapor SPT'), TEKS)
        self.assertEqual(catatan, 'why_salinan_ulasan')

    def test_why_mengulang_what_dikosongkan(self):
        teks = 'sangat membantu jadi gak ribet cari data'
        h, catatan = verifikasi_objek(obj(
            what='mencari data dengan mudah', why='tidak ribet mencari data', why_evidence='gak ribet cari data',
            as_a_i_want_so_that='As a pengguna, I want to mencari data dengan mudah, so that tidak ribet mencari data',
            evidence='sangat membantu jadi gak ribet cari data'), teks)
        self.assertEqual(catatan, 'why_ulang_what')
        self.assertEqual(h.user_story, 'As a wajib pajak, I want to mencari data dengan mudah')

    def test_why_netral_dengan_dasar_dipertahankan(self):
        h, catatan = verifikasi_objek(obj(), TEKS)
        self.assertIsNone(catatan)
        self.assertEqual(h.evidence_why, 'tidak bisa lapor SPT')
        self.assertEqual(h.user_story, 'As a wajib pajak, I want to login ke aplikasi, so that bisa lapor SPT')

    def test_why_kosong_story_tanpa_so_that(self):
        h, _ = verifikasi_objek(obj(why='', why_evidence='', as_a_i_want_so_that='As a wajib pajak, I want to login ke aplikasi'), TEKS)
        self.assertEqual(h.why, '')

    def test_who_kosong_jadi_pengguna_dan_confidence_dijepit(self):
        h, _ = verifikasi_objek(obj(who='', confidence=7), TEKS)
        self.assertEqual((h.who, h.confidence), ('pengguna', 1.0))

    def test_susun(self):
        self.assertEqual(susun_user_story('a', 'b'), 'As a a, I want to b')
        self.assertEqual(susun_user_story('a', 'b', 'c'), 'As a a, I want to b, so that c')


class EkstraktorGeminiTest(TestCase):
    def test_terdaftar(self):
        self.assertIn('gemini', registry.REGISTRI)

    def test_batch_dan_pii_tidak_bocor(self):
        klien = KlienPalsu({'userStories': [obj(review_id='0')]})
        e = EkstraktorGemini(client=klien)
        hasil = e.ekstrak_batch([TEKS + ' hubungi 081234567890', 'bagus'])
        self.assertEqual(len(hasil), 2)
        self.assertEqual(len(hasil[0]), 1)
        self.assertEqual(hasil[1], [])  # model tidak mengembalikan apa pun: tanpa kebutuhan
        self.assertNotIn('081234567890', klien.prompt[0])
        self.assertIn('[TELEPON]', klien.prompt[0])

    def test_dipecah_per_batch_llm(self):
        klien = KlienPalsu({'userStories': []})
        EkstraktorGemini(client=klien, batch_llm=2).ekstrak_batch(['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(len(klien.prompt), 3)

    def test_error_api_jadi_exception_per_ulasan(self):
        e = EkstraktorGemini(client=KlienPalsu(LLMTimeoutError('lama')))
        hasil = e.ekstrak_batch(['a', 'b'])
        self.assertTrue(all(isinstance(h, LLMTimeoutError) for h in hasil))

    def test_semua_objek_ditolak_jadi_gagal_bukan_kosong(self):
        e = EkstraktorGemini(client=KlienPalsu({'userStories': [obj(evidence='karangan')]}))
        (h,) = e.ekstrak_batch([TEKS])
        self.assertIsInstance(h, Exception)
        self.assertEqual(e.ambil_galat()[0][1], 'evidence_tidak_ditemukan')
        self.assertEqual(e.ambil_galat(), [])

    def test_review_id_asing_dicatat(self):
        e = EkstraktorGemini(client=KlienPalsu({'userStories': [obj(review_id='99')]}))
        e.ekstrak_batch([TEKS])
        self.assertEqual(e.ambil_galat()[0][1], 'review_id_tidak_dikenal')

    def test_prompt_berversi(self):
        self.assertTrue(VERSI_PROMPT)
        self.assertIn('"review_id": "0"', susun_prompt([('0', 'halo')]))


class UlangiTanpaKebutuhanTest(TestCase):
    def test_command_membuka_kembali(self):
        from django.core.management import call_command
        app = Aplikasi.objects.create(nama_aplikasi='X', package_name='x.z')
        u = Ulasan.objects.create(aplikasi=app, isi_ulasan=TEKS, tanggal_ulasan='2026-01-01', skor_bintang=1,
                                  status_filter='DIBUANG', alasan_filter=Ulasan.AlasanFilter.TANPA_KEBUTUHAN)
        klien = KlienPalsu({'userStories': [obj(review_id='0')]})
        from unittest import mock
        with mock.patch('extraction.services.registry.get_ekstraktor', return_value=EkstraktorGemini(client=klien)):
            call_command('extract_reviews', '--extractor', 'gemini', '--ulangi-tanpa-kebutuhan', stdout=__import__('io').StringIO())
        u.refresh_from_db()
        self.assertEqual(u.status_filter, 'LOLOS')
        self.assertEqual(HasilEkstraksi.objects.filter(ulasan=u).count(), 1)


class RunnerGeminiTest(TestCase):
    def setUp(self):
        app = Aplikasi.objects.create(nama_aplikasi='X', package_name='x.y')
        mk = lambda teks, rid: Ulasan.objects.create(aplikasi=app, review_id=rid, isi_ulasan=teks,
                                                      tanggal_ulasan='2026-01-01', skor_bintang=1)
        self.u1, self.u2 = mk(TEKS, 'a'), mk('terima kasih bagus', 'b')

    def test_simpan_metadata_dan_idempoten(self):
        klien = KlienPalsu({'userStories': [obj(review_id='0')]})
        r = runner.ekstrak_ulasan_baru(EkstraktorGemini(client=klien))
        self.assertEqual((r.diproses, r.hasil, r.tanpa_hasil, r.gagal), (2, 1, 1, 0))
        h = HasilEkstraksi.objects.get()
        self.assertEqual((h.nama_ekstraktor, h.model_llm, h.versi_prompt), ('gemini', 'palsu-1', VERSI_PROMPT))
        self.assertTrue(h.kalimat_user_story.startswith('As a'))
        self.assertTrue(h.evidence)
        self.u2.refresh_from_db()
        self.assertEqual(self.u2.alasan_filter, Ulasan.AlasanFilter.TANPA_KEBUTUHAN)
        # jalan kedua: tidak ada kandidat lagi
        self.assertEqual(runner.ekstrak_ulasan_baru(EkstraktorGemini(client=klien)).diproses, 0)
        self.assertEqual(len(klien.prompt), 1)

    def test_galat_api_dicatat_dan_dicoba_ulang(self):
        r = runner.ekstrak_ulasan_baru(EkstraktorGemini(client=KlienPalsu(LLMTimeoutError('lama'))))
        self.assertEqual((r.gagal, r.hasil), (2, 0))
        self.assertEqual(GalatEkstraksi.objects.filter(jenis='LLMTimeoutError').count(), 2)
        self.assertEqual(Ulasan.objects.filter(status_filter='LOLOS').count(), 2)  # tidak dibuang

    def test_penolakan_verifikasi_masuk_log(self):
        klien = KlienPalsu({'userStories': [obj(evidence='karangan')]})
        r = runner.ekstrak_ulasan_baru(EkstraktorGemini(client=klien))
        self.assertEqual(r.gagal, 1)
        g = GalatEkstraksi.objects.get(jenis='evidence_tidak_ditemukan')
        self.assertEqual(g.ulasan_id, self.u1.id)
        self.assertEqual(g.versi_prompt, VERSI_PROMPT)


class CatatDevsetTest(TestCase):
    def test_tulis_union_dan_tidak_menghapus(self):
        import tempfile, os
        from django.core.management import call_command
        app = Aplikasi.objects.create(nama_aplikasi='X', package_name='x.d')
        u = Ulasan.objects.create(aplikasi=app, review_id='r1', isi_ulasan=TEKS, tanggal_ulasan='2026-01-01', skor_bintang=1)
        Ulasan.objects.create(aplikasi=app, review_id='r2', isi_ulasan='lain', tanggal_ulasan='2026-01-01', skor_bintang=1)
        runner.ekstrak_ulasan_baru(EkstraktorGemini(client=KlienPalsu({'userStories': [obj(review_id='0')]})), batas=1)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'dev.txt')
            open(f, 'w').write('x.lama\told1\n')
            call_command('catat_devset', '--file', f, stdout=__import__('io').StringIO())
            baris = open(f).read().split()
        self.assertIn('x.d', baris)
        self.assertIn('r1', baris)
        self.assertNotIn('r2', baris)
        self.assertIn('old1', baris)


class FilterBintangTest(TestCase):
    def setUp(self):
        app = Aplikasi.objects.create(nama_aplikasi='X', package_name='x.b')
        for i, b in enumerate([1, 2, 5]):
            Ulasan.objects.create(aplikasi=app, review_id=f'b{i}', isi_ulasan=TEKS, tanggal_ulasan='2026-01-01', skor_bintang=b)

    def test_bintang_maks(self):
        klien = KlienPalsu({'userStories': []})
        r = runner.ekstrak_ulasan_baru(EkstraktorGemini(client=klien), bintang_maks=2)
        self.assertEqual(r.diproses, 2)

    def test_bintang_min(self):
        klien = KlienPalsu({'userStories': []})
        r = runner.ekstrak_ulasan_baru(EkstraktorGemini(client=klien), bintang_min=5)
        self.assertEqual(r.diproses, 1)


class DuaKebutuhanSatuUlasanTest(TestCase):
    def test_dua_objek_untuk_satu_ulasan_disimpan_dua(self):
        teks = 'setelah update jadi logout. dan harus foto ulang. tolong dibuat lebih sederhana'
        klien = KlienPalsu({'userStories': [
            obj(review_id='0', what='tetap login setelah pembaruan', evidence='setelah update jadi logout',
                why='proses lebih sederhana', why_evidence='tolong dibuat lebih sederhana',
                as_a_i_want_so_that='As a pengguna, I want to tetap login setelah pembaruan, so that proses lebih sederhana'),
            obj(review_id='0', what='tidak perlu foto ulang', evidence='harus foto ulang',
                why='proses lebih sederhana', why_evidence='tolong dibuat lebih sederhana',
                as_a_i_want_so_that='As a pengguna, I want to tidak perlu foto ulang, so that proses lebih sederhana'),
        ]})
        (hasil,) = EkstraktorGemini(client=klien).ekstrak_batch([teks])
        self.assertEqual([h.what for h in hasil], ['tetap login setelah pembaruan', 'tidak perlu foto ulang'])
