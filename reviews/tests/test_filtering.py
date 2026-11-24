"""Uji preprocessing & filter lengkap (Sprint 3 bagian B): alasan jelas, keluhan teknis tidak dibuang."""
from datetime import date, datetime
from io import StringIO

import pytest
from django.core.management import call_command

from extraction.services.runner import ekstrak_ulasan_baru
from extraction.services.base import Ekstraktor
from reviews.models import Aplikasi, Ulasan
from reviews.services import filtering, ingest

CFG = {
    'min_kata': 3, 'min_kata_keluhan': 2, 'maks_kata_tanpa_sinyal': 5,
    'pola_generik': ['bagus', 'mantap', 'mantap jiwa'], 'samarkan_username': True,
}


def ev(teks, skor=None):
    return filtering.evaluasi_ulasan(teks, skor, CFG)


@pytest.mark.parametrize('teks', [
    'Aplikasi sering force close saat login',
    'login gagal',                       # keluhan teknis singkat tetap lolos (B4)
    'error terus',
    'bagus tapi sering lemot',           # pujian + keluhan
    'tolong tambahkan fitur unduh sertifikat vaksin',
    'OTP tidak masuk padahal nomor benar',
    'Gak bisa login udah 3 hari',        # slang
    'mudah digunakan tapi kadang error',
    'Tidak bisa login, bantuan ada di https://contoh.id/bantuan',   # tautan + keluhan tidak jadi spam
    'Data NIK saya salah dan tidak bisa diubah',
])
def test_kebutuhan_dan_keluhan_teknis_lolos(teks):
    k = ev(teks, 1)
    assert k.lolos, (teks, k.alasan)
    assert k.alasan == ''


@pytest.mark.parametrize('teks,alasan', [
    ('ok', filtering.ALASAN_PENDEK),
    ('error', filtering.ALASAN_PENDEK),                       # 1 kata saja: belum cukup bukti
    ('👍👍', filtering.ALASAN_PENDEK),
    ('bagus banget aplikasinya', filtering.ALASAN_GENERIK),
    ('Terima kasih, sangat membantu', filtering.ALASAN_GENERIK),
    ('Aplikasi bagus sekali', filtering.ALASAN_GENERIK),
    ('Klik link www.promo-bonus.com untuk hadiah', filtering.ALASAN_SPAM),
    ('Hubungi 081234567890 sekarang juga', filtering.ALASAN_SPAM),
    ('slot gacor maxwin hari ini daftar sini', filtering.ALASAN_SPAM),   # promosi walau ada kata "daftar"
    ('bagus bagus bagus bagus bagus', filtering.ALASAN_SPAM),
    ('saya baru download aplikasi ini', filtering.ALASAN_TIDAK_RELEVAN),
])
def test_alasan_pembuangan_jelas(teks, alasan):
    k = ev(teks, 5)
    assert (k.lolos, k.alasan) == (False, alasan)


def test_pola_generik_persis_dibuang_walau_tanpa_kamus_pujian():
    cfg = {**CFG, 'min_kata': 1, 'pola_generik': ['mantap jiwa']}
    k = filtering.evaluasi_ulasan('Mantap Jiwaaa!!!', 5, cfg)
    assert (k.lolos, k.alasan) == (False, filtering.ALASAN_GENERIK)


def test_tidak_relevan_hanya_untuk_bintang_netral_atau_positif():
    assert ev('saya baru download aplikasi ini', 1).lolos          # bintang 1 = kemungkinan keluhan, jangan buang
    assert not ev('saya baru download aplikasi ini', 3).lolos


def test_periksa_ulasan_dasar_tetap_kompatibel():
    pola = ['bagus']
    assert filtering.periksa_ulasan('bagus', 3, pola) == (False, filtering.ALASAN_PENDEK)
    assert filtering.periksa_ulasan('gagal login terus', 3, pola) == (True, '')


def test_alasan_sinkron_dengan_pilihan_model():
    nilai = {c.value for c in Ulasan.AlasanFilter}
    assert nilai == {
        filtering.ALASAN_PENDEK, filtering.ALASAN_GENERIK, filtering.ALASAN_SPAM,
        filtering.ALASAN_TIDAK_RELEVAN, filtering.ALASAN_DUPLIKAT, filtering.ALASAN_TANPA_KEBUTUHAN,
    }


def test_normalisasi_untuk_duplikasi():
    assert filtering.kunci_duplikat('Gagal  LOGIN!!!') == filtering.kunci_duplikat('gagal login')
    assert filtering.kunci_duplikat('Gagal logiiin') == filtering.kunci_duplikat('gagal login')


def _item(rid, isi, skor=1):
    return {'reviewId': rid, 'userName': 'u', 'content': isi, 'score': skor, 'at': datetime(2026, 10, 1)}


@pytest.mark.django_db
class TestIngestMencatatAlasan:
    def setup_method(self):
        self.app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')

    def test_alasan_tersimpan_dan_duplikat_teks_dibuang(self):
        batch = [
            _item('1', 'Tidak bisa login sejak update terbaru'),
            _item('2', 'tidak bisa login sejak update terbaru!!!'),   # teks sama, id berbeda
            _item('3', 'bagus banget aplikasinya', 5),
            _item('4', 'slot gacor maxwin hari ini', 5),
        ]
        h = ingest.simpan_batch(self.app, batch, cfg=CFG)
        assert (h.baru, h.lolos, h.dibuang) == (4, 1, 3)
        alasan = dict(Ulasan.objects.values_list('review_id', 'alasan_filter'))
        assert alasan == {'1': '', '2': 'duplikat', '3': 'generik', '4': 'spam'}

    def test_duplikat_terhadap_data_yang_sudah_ada(self):
        ingest.simpan_batch(self.app, [_item('1', 'Tidak bisa login sejak update')], cfg=CFG)
        ingest.simpan_batch(self.app, [_item('9', 'tidak bisa login sejak update')], cfg=CFG)
        assert Ulasan.objects.get(review_id='9').alasan_filter == 'duplikat'

    def test_teks_sama_di_aplikasi_berbeda_bukan_duplikat(self):
        lain = Aplikasi.objects.create(nama_aplikasi='SATU SEHAT', package_name='x.ss')
        ingest.simpan_batch(self.app, [_item('1', 'Tidak bisa login sejak update')], cfg=CFG)
        ingest.simpan_batch(lain, [_item('1', 'Tidak bisa login sejak update')], cfg=CFG)
        assert not Ulasan.objects.filter(alasan_filter='duplikat').exists()


class _EkstraktorKosong(Ekstraktor):
    nama = 'kosong'

    def ekstrak(self, teks):
        return []


@pytest.mark.django_db
def test_runner_mencatat_alasan_tanpa_kebutuhan():
    app = Aplikasi.objects.create(nama_aplikasi='M-Pajak', package_name='x.mp')
    Ulasan.objects.create(aplikasi=app, isi_ulasan='Aplikasi digunakan untuk lapor SPT tahunan',
                          tanggal_ulasan=date(2026, 10, 1), skor_bintang=4)
    ekstrak_ulasan_baru(_EkstraktorKosong())
    u = Ulasan.objects.get()
    assert (u.status_filter, u.alasan_filter) == ('DIBUANG', 'tanpa kebutuhan')


@pytest.mark.django_db
class TestRefilterCommand:
    def setup_method(self):
        self.app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='x.ikd')
        mk = lambda isi, **kw: Ulasan.objects.create(  # noqa: E731
            aplikasi=self.app, isi_ulasan=isi, tanggal_ulasan=date(2026, 10, 1), skor_bintang=5, **kw)
        self.pujian = mk('bagus banget aplikasinya')
        self.keluhan = mk('Tidak bisa login sejak update')
        self.lama_dibuang = mk('ok', status_filter='DIBUANG')                  # dibuang tanpa alasan tercatat

    def _jalankan(self, *args):
        out = StringIO()
        call_command('refilter_reviews', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_tidak_menulis(self):
        self._jalankan()
        self.pujian.refresh_from_db()
        assert self.pujian.status_filter == 'LOLOS' and self.pujian.alasan_filter == ''

    def test_apply_membuang_pujian_mengisi_alasan_dan_menjaga_keluhan(self):
        self._jalankan('--apply')
        for u in (self.pujian, self.keluhan, self.lama_dibuang):
            u.refresh_from_db()
        assert (self.pujian.status_filter, self.pujian.alasan_filter) == ('DIBUANG', 'generik')
        assert (self.keluhan.status_filter, self.keluhan.alasan_filter) == ('LOLOS', '')
        assert (self.lama_dibuang.status_filter, self.lama_dibuang.alasan_filter) == ('DIBUANG', 'terlalu pendek')

    def test_tidak_mengubah_ulasan_yang_sudah_diekstraksi(self):
        from extraction.models import HasilEkstraksi
        HasilEkstraksi.objects.create(ulasan=self.pujian, teks_who='pengguna', teks_what='x', teks_why='')
        self._jalankan('--apply')
        self.pujian.refresh_from_db()
        assert self.pujian.status_filter == 'LOLOS'


@pytest.mark.parametrize('teks,skor', [
    ('aplikasi ikd sangat bagus', 2),
    ('sangat bermanfaat dan membantu bagi masyarakat', 5),
    ('aplikasi satu sehat sangat membantu warga', 5),
    ('mantap aplikasi m-pajak', 1),
])
def test_pujian_dengan_nama_aplikasi_atau_subjek_umum_dibuang(teks, skor):
    k = ev(teks, skor)
    assert (k.lolos, k.alasan) == (False, 'generik')


@pytest.mark.parametrize('teks', [
    'sangat membantu masyarakat tapi sering error saat login',
    'aplikasi ikd bagus, semoga ditambah fitur tanda tangan digital',
    'bagus tapi tidak bisa login',
])
def test_pujian_disertai_kebutuhan_tetap_lolos(teks):
    assert ev(teks, 3).lolos


def test_permintaan_fitur_whatsapp_bukan_spam():
    k = ev('tolong tambahkan fitur notifikasi lewat WhatsApp dan Telegram', 4)
    assert k.lolos, k.alasan


def test_tidak_sendirian_bukan_sinyal_teknis():
    for teks, skor in (('ga jelas', 1), ('ga guna', 1), ('Aman gak nihhh Bang?', 5)):
        assert not ev(teks, skor).lolos, teks
