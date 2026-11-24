"""Uji bagian E: validasi per user story + jejak revisi + API JSON."""
import json

import numpy as np
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi, LogValidasi
from extraction.services import validation
from extraction.services.clustering_embedding import pusatkan
from reviews.models import Aplikasi, Ulasan


class Dasar(TestCase):
    def setUp(self):
        self.app = Aplikasi.objects.create(nama_aplikasi='IKD', package_name='gov.dukcapil.mobile_id')
        mk = lambda n, r: User.objects.create_user(username=n, email=f'{n}@x.id', password='p', role=r)  # noqa: E731
        self.analyst = mk('analis', User.RolePengguna.ANALYST)
        self.re = mk('re', User.RolePengguna.REQUIREMENTS_ENGINEER)
        self.dev = mk('dev', User.RolePengguna.TIM_DEVELOPER)
        self.u1 = Ulasan.objects.create(aplikasi=self.app, isi_ulasan='tidak bisa login terus', tanggal_ulasan='2026-10-01',
                                        skor_bintang=1)
        self.u2 = Ulasan.objects.create(aplikasi=self.app, isi_ulasan='verifikasi wajah gagal', tanggal_ulasan='2026-10-02',
                                        skor_bintang=2)
        self.u3 = Ulasan.objects.create(aplikasi=self.app, isi_ulasan='aplikasi sampah', tanggal_ulasan='2026-10-02',
                                        skor_bintang=1, status_filter='DIBUANG', alasan_filter='generik')
        self.h1 = HasilEkstraksi.objects.create(ulasan=self.u1, teks_who='warga', teks_what='login ke aplikasi',
                                                teks_why='bisa mengakses layanan', embedding_what=[1.0, 0.0],
                                                model_embedding='m', kalimat_user_story='x')
        self.h2 = HasilEkstraksi.objects.create(ulasan=self.u2, teks_who='warga', teks_what='verifikasi wajah')
        self.c = Cluster.objects.create(nama_topik='Login', jumlah_anggota=2, representatif=self.h1)
        ClusterAnggota.objects.create(cluster=self.c, hasil_ekstraksi=self.h1)
        ClusterAnggota.objects.create(cluster=self.c, hasil_ekstraksi=self.h2)


class TestValidasiPerStory(Dasar):
    def test_perbaiki_mencatat_lama_baru_dan_susun_ulang(self):
        h = validation.perbaiki_ekstraksi(self.h1, self.analyst, what='masuk ke aplikasi dengan lancar', why='',
                                          catatan='disederhanakan')
        self.assertEqual(h.kalimat_user_story, 'As a warga, I want to masuk ke aplikasi dengan lancar')
        self.assertIsNone(h.embedding_what)  # WHAT berubah -> embedding dibuang
        log = LogValidasi.objects.get(objek_jenis='EKSTRAKSI', objek_id=h.pk)
        self.assertEqual(log.aksi, 'PERBAIKI')
        self.assertEqual(log.nilai_lama['what'], 'login ke aplikasi')
        self.assertEqual(log.nilai_baru['why'], '')
        self.assertEqual(log.pengguna, self.analyst)

    def test_perbaiki_why_saja_mempertahankan_embedding(self):
        h = validation.perbaiki_ekstraksi(self.h1, self.analyst, why='layanan dapat diakses kapan saja')
        self.assertEqual(h.embedding_what, [1.0, 0.0])

    def test_perbaiki_menolak_kosong_atau_tanpa_perubahan(self):
        with self.assertRaises(validation.ValidationError):
            validation.perbaiki_ekstraksi(self.h1, self.analyst, what='  ')
        with self.assertRaises(validation.ValidationError):
            validation.perbaiki_ekstraksi(self.h1, self.analyst, what='login ke aplikasi')

    def test_tolak_ekstraksi_mengurangi_jumlah_dan_setujui_cluster_melewatinya(self):
        validation.tolak_ekstraksi(self.h2, self.analyst, 'bukan kebutuhan')
        self.c.refresh_from_db()
        self.assertEqual(self.c.jumlah_anggota, 1)
        validation.setujui_cluster(self.c, self.analyst)
        self.h1.refresh_from_db(); self.h2.refresh_from_db()
        self.assertEqual(self.h1.status_validasi, 'TERVALIDASI')
        self.assertEqual(self.h2.status_validasi, 'DIHAPUS')  # tidak ikut "disetujui"

    def test_state_machine_per_story(self):
        validation.setujui_ekstraksi(self.h1, self.analyst)
        with self.assertRaises(validation.ValidationError):
            validation.tolak_ekstraksi(self.h1, self.analyst)
        with self.assertRaises(validation.ValidationError):
            validation.perbaiki_ekstraksi(self.h1, self.analyst, what='lain')

    def test_aksi_cluster_tercatat(self):
        validation.tolak_cluster(self.c, self.analyst, 'campuran')
        log = LogValidasi.objects.get(objek_jenis='CLUSTER', objek_id=self.c.pk)
        self.assertEqual((log.aksi, log.catatan), ('TOLAK', 'campuran'))


class TestApi(Dasar):
    def _post(self, nama, pk, data=None):
        return self.client.post(reverse(f'extraction:{nama}', args=[pk]), json.dumps(data or {}),
                                content_type='application/json')

    def test_amplop_sukses_dan_galat(self):
        self.client.force_login(self.analyst)
        r = self.client.get(reverse('extraction:api_ekstraksi_list'))
        j = r.json()
        self.assertEqual((r.status_code, j['status'], j['error']), (200, 'success', None))
        self.assertEqual(set(j), {'status', 'data', 'error', 'meta'})
        self.assertEqual(j['meta']['total'], 2)
        r = self.client.get(reverse('extraction:api_ekstraksi_detail', args=[9999]))
        j = r.json()
        self.assertEqual((r.status_code, j['status'], j['error']['code'], j['data']), (404, 'error', 'tidak_ditemukan', None))

    def test_akses_json_bukan_redirect(self):
        r = self.client.get(reverse('extraction:api_cluster_list'))
        self.assertEqual((r.status_code, r.json()['error']['code']), (401, 'tidak_login'))
        self.client.force_login(self.dev)
        r = self.client.get(reverse('extraction:api_cluster_list'))
        self.assertEqual((r.status_code, r.json()['error']['code']), (403, 'akses_ditolak'))

    def test_re_boleh_baca_tidak_boleh_validasi(self):
        self.client.force_login(self.re)
        self.assertEqual(self.client.get(reverse('extraction:api_cluster_list')).status_code, 200)
        r = self._post('api_cluster_setujui', self.c.pk)
        self.assertEqual(r.status_code, 403)
        self.c.refresh_from_db()
        self.assertEqual(self.c.status_cluster, 'MENUNGGU_VALIDASI')

    def test_metode_salah(self):
        self.client.force_login(self.analyst)
        r = self.client.get(reverse('extraction:api_cluster_setujui', args=[self.c.pk]))
        self.assertEqual((r.status_code, r.json()['error']['code']), (405, 'metode_tidak_diizinkan'))

    def test_perbaiki_lalu_riwayat(self):
        self.client.force_login(self.analyst)
        r = self._post('api_ekstraksi_perbaiki', self.h1.pk, {'what': 'masuk ke aplikasi', 'catatan': 'c'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['data']['user_story'], 'As a warga, I want to masuk ke aplikasi, so that bisa mengakses layanan')
        riw = self.client.get(reverse('extraction:api_ekstraksi_riwayat', args=[self.h1.pk])).json()
        self.assertEqual(riw['meta']['total'], 1)
        self.assertEqual(riw['data'][0]['nilai_lama']['what'], 'login ke aplikasi')

    def test_perbaiki_body_tidak_valid(self):
        self.client.force_login(self.analyst)
        r = self.client.post(reverse('extraction:api_ekstraksi_perbaiki', args=[self.h1.pk]), 'bukan json',
                             content_type='application/json')
        self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'permintaan_tidak_valid'))
        r = self._post('api_ekstraksi_perbaiki', self.h1.pk, {'what': 5})
        self.assertEqual(r.status_code, 400)

    def test_konflik_status_409(self):
        self.client.force_login(self.analyst)
        self.assertEqual(self._post('api_ekstraksi_setujui', self.h1.pk).status_code, 200)
        r = self._post('api_ekstraksi_setujui', self.h1.pk)
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'status_tidak_valid'))

    def test_setujui_cluster_dan_filter_status(self):
        self.client.force_login(self.analyst)
        r = self._post('api_cluster_setujui', self.c.pk)
        self.assertEqual(r.json()['data']['status'], 'TERVALIDASI')
        j = self.client.get(reverse('extraction:api_cluster_list') + '?status=MENUNGGU_VALIDASI').json()
        self.assertEqual(j['meta']['total'], 0)
        self.assertEqual(self.client.get(reverse('extraction:api_cluster_list') + '?status=ngawur').status_code, 400)

    def test_detail_cluster_memuat_anggota_dan_ulasan(self):
        self.client.force_login(self.re)
        d = self.client.get(reverse('extraction:api_cluster_detail', args=[self.c.pk])).json()['data']
        self.assertEqual(len(d['anggota']), 2)
        self.assertIn('isi_ulasan', d['anggota'][0])
        self.assertEqual(d['representatif']['what'], 'login ke aplikasi')

    def test_status_tahap_ulasan(self):
        self.client.force_login(self.re)
        d = {x['id']: x for x in self.client.get(reverse('extraction:api_ulasan')).json()['data']}
        self.assertEqual(d[self.u1.pk]['tahap']['ekstraksi']['status'], 'BERHASIL')
        self.assertEqual(d[self.u1.pk]['tahap']['clustering']['cluster_id'], [self.c.pk])
        self.assertEqual(d[self.u3.pk]['tahap']['filter'], {'status': 'DIBUANG', 'alasan': 'generik'})
        self.assertEqual(d[self.u3.pk]['tahap']['ekstraksi']['status'], 'TIDAK_DIPROSES')

    def test_ringkasan(self):
        self.client.force_login(self.re)
        d = self.client.get(reverse('extraction:api_ringkasan')).json()['data']
        self.assertEqual(d['ulasan']['total'], 3)
        self.assertEqual(d['ulasan_dibuang_per_alasan'], {'generik': 1})


def test_pusatkan_menormalkan_dan_memperlebar_jarak():
    X = np.array([[1, 0.1], [1, -0.1], [0.9, 0.0]], dtype=float)
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    P = pusatkan(X)
    assert np.allclose(np.linalg.norm(P, axis=1), 1.0)
    assert (P @ P.T).min() < (X @ X.T).min()
    assert pusatkan(X[:1]).shape == (1, 2)
