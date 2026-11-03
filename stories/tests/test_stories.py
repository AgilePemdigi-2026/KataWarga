"""
Test suite untuk Backlog #7 (Menyusun User Story) dan #8 (Memvalidasi User Story).
Memenuhi seluruh kriteria acceptance Gherkin dan kontrak fungsi.
"""
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from extraction.models import Cluster
from stories.models import UserStory
from stories.services import scoring, composer, approval


class ScoringAndComposerTestCase(TestCase):
    """Uji 1 & 2: scoring, representative element, fallback who, dan idempotensi."""

    def setUp(self):
        call_command('seed_dummy')
        self.cluster_150 = Cluster.objects.get(nama_topik='Gagal Login')
        self.cluster_40 = Cluster.objects.get(nama_topik='Notifikasi Lambat')
        self.cluster_5 = Cluster.objects.get(nama_topik='Fitur Kecil')
        self.cluster_2 = Cluster.objects.get(nama_topik='Warna Tombol')

    def test_scoring_kategori_dan_signifikansi(self):
        # Cluster 150 ulasan -> Kategori TINGGI
        metrik_150 = scoring.hitung_skor_cluster(self.cluster_150)
        self.assertTrue(metrik_150['cukup_signifikan'])
        self.assertEqual(metrik_150['n'], 150)
        self.assertEqual(metrik_150['kategori'], UserStory.LevelPrioritas.TINGGI)

        # Cluster 40 ulasan -> Kategori SEDANG
        metrik_40 = scoring.hitung_skor_cluster(self.cluster_40)
        self.assertTrue(metrik_40['cukup_signifikan'])
        self.assertEqual(metrik_40['n'], 40)
        self.assertEqual(metrik_40['kategori'], UserStory.LevelPrioritas.SEDANG)

        # Cluster 5 ulasan -> Kategori RENDAH
        metrik_5 = scoring.hitung_skor_cluster(self.cluster_5)
        self.assertTrue(metrik_5['cukup_signifikan'])
        self.assertEqual(metrik_5['n'], 5)
        self.assertEqual(metrik_5['kategori'], UserStory.LevelPrioritas.RENDAH)

        # Cluster 2 ulasan -> Di bawah ambang (<5) -> Tidak signifikan
        metrik_2 = scoring.hitung_skor_cluster(self.cluster_2)
        self.assertFalse(metrik_2['cukup_signifikan'])
        self.assertEqual(metrik_2['n'], 2)

    def test_composer_kalimat_dan_fallback_who(self):
        # Compose cluster 150
        story_150 = composer.compose_cluster(self.cluster_150)
        self.assertIsNotNone(story_150)
        self.assertTrue(story_150.kalimat.startswith("Sebagai "))
        self.assertEqual(story_150.peran, "wajib pajak")
        self.assertEqual(story_150.status_persetujuan, UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN)

        # Compose cluster 5 (who kosong -> fallback nama aplikasi)
        story_5 = composer.compose_cluster(self.cluster_5)
        self.assertIsNotNone(story_5)
        self.assertTrue(story_5.kalimat.startswith("Sebagai "))
        self.assertIn("pengguna aplikasi", story_5.peran)

        # Compose cluster 2 (< ambang -> status DIABAIKAN, story None)
        story_2 = composer.compose_cluster(self.cluster_2)
        self.assertIsNone(story_2)
        self.cluster_2.refresh_from_db()
        self.assertEqual(self.cluster_2.status_cluster, Cluster.StatusCluster.DIABAIKAN)

    def test_composer_idempotensi(self):
        story_first = composer.compose_cluster(self.cluster_150)
        story_second = composer.compose_cluster(self.cluster_150)
        self.assertEqual(story_first.id, story_second.id)
        self.assertEqual(UserStory.objects.filter(cluster=self.cluster_150).count(), 1)


class SusunViewTestCase(TestCase):
    """Uji 3: view /susun-user-story dan RBAC."""

    def setUp(self):
        call_command('seed_dummy')
        self.client = Client()
        self.re_user = User.objects.get(username='re_user')
        self.po_user = User.objects.get(username='po_user')

    def test_post_susun_sebagai_requirements_engineer(self):
        self.client.force_login(self.re_user)
        response = self.client.post('/susun-user-story')
        self.assertEqual(response.status_code, 200)
        # Sesuai kontrak: hasilnya berisi story berawalan "Sebagai"
        self.assertContains(response, "Sebagai")
        self.assertContains(response, "daftar-user-story")

    def test_post_susun_sebagai_bukan_re_ditolak_403(self):
        self.client.force_login(self.po_user)
        response = self.client.post('/susun-user-story')
        self.assertEqual(response.status_code, 403)

    def test_get_susun_user_story(self):
        self.client.force_login(self.re_user)
        response = self.client.get('/susun-user-story')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Susun User Story")
        self.assertContains(response, 'id="daftar-user-story"')


class ApprovalAndBoardTestCase(TestCase):
    """Uji 4 & 5: approval, rollback transaksi saat hook error, dan filter papan board."""

    def setUp(self):
        call_command('seed_dummy')
        self.client = Client()
        self.po_user = User.objects.get(username='po_user')
        self.dev_user = User.objects.get(username='dev_user')
        self.re_user = User.objects.get(username='re_user')

        # Susun cerita
        composer.compose_pending()
        self.story_150 = UserStory.objects.get(cluster__nama_topik='Gagal Login')
        self.story_40 = UserStory.objects.get(cluster__nama_topik='Notifikasi Lambat')
        self.story_5 = UserStory.objects.get(cluster__nama_topik='Fitur Kecil')

    def test_setujui_oleh_po_sukses(self):
        self.client.force_login(self.po_user)
        response = self.client.post(f"/user-story/{self.story_150.id}/setujui")
        self.assertRedirects(response, '/backlog', status_code=302, target_status_code=200)

        self.story_150.refresh_from_db()
        self.assertEqual(self.story_150.status_persetujuan, UserStory.StatusPersetujuan.DISETUJUI)
        self.assertIsNotNone(self.story_150.tanggal_persetujuan)

    def test_setujui_oleh_po_via_htmx(self):
        self.client.force_login(self.po_user)
        response = self.client.post(
            f"/user-story/{self.story_40.id}/setujui",
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('HX-Redirect'), '/backlog')

    def test_setujui_oleh_non_po_ditolak_403(self):
        self.client.force_login(self.re_user)
        response = self.client.post(f"/user-story/{self.story_150.id}/setujui")
        self.assertEqual(response.status_code, 403)

    def test_abaikan_oleh_po(self):
        self.client.force_login(self.po_user)
        response = self.client.post(
            f"/user-story/{self.story_5.id}/abaikan",
            {'alasan': 'Kebutuhan minor'}
        )
        self.assertRedirects(response, f"/user-story/{self.story_5.id}")

        self.story_5.refresh_from_db()
        self.assertEqual(self.story_5.status_persetujuan, UserStory.StatusPersetujuan.DIABAIKAN)
        self.assertEqual(self.story_5.alasan_diabaikan, 'Kebutuhan minor')

        # Cek papan board: tidak boleh muncul di kolom Sprint Backlog
        board_res = self.client.get('/user-story')
        self.assertContains(board_res, 'Dismissed')

    def test_abaikan_oleh_non_po_ditolak_403(self):
        self.client.force_login(self.dev_user)
        response = self.client.post(f"/user-story/{self.story_150.id}/abaikan")
        self.assertEqual(response.status_code, 403)

    def test_hook_backlog_error_rollback_transaksi(self):
        """Uji atomik FR-SIM-04: jika saver gagal, status tetap MENUNGGU_PERSETUJUAN."""
        self.client.force_login(self.po_user)

        # approval.py memanggil save_to_backlog secara langsung (sejak #9 di-merge),
        # jadi yang di-patch adalah nama yang dipakai di modul approval.
        with patch('stories.services.approval.save_to_backlog',
                   side_effect=RuntimeError("Koneksi DB Backlog Terputus")):
            response = self.client.post(f"/user-story/{self.story_150.id}/setujui")
            self.story_150.refresh_from_db()

            # Status HARUS tetap MENUNGGU_PERSETUJUAN karena rollback
            self.assertEqual(self.story_150.status_persetujuan, UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN)

    def test_detail_view_elemen_kontrak(self):
        self.client.force_login(self.po_user)
        response = self.client.get(f"/user-story/{self.story_150.id}")
        self.assertEqual(response.status_code, 200)

        # Kontrak elemen: data-testid="prioritas" dan data-testid="status"
        self.assertContains(response, 'data-testid="prioritas"')
        self.assertContains(response, 'data-testid="status"')
        self.assertContains(response, 'Tinggi')
        self.assertContains(response, 'Menunggu Persetujuan')
        self.assertContains(response, 'Setujui')
        self.assertContains(response, 'Abaikan')

    def test_board_view_filter_dan_urutan(self):
        self.client.force_login(self.po_user)
        # Papan tanpa filter
        res = self.client.get('/user-story')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'To Review')
        self.assertContains(res, 'Sprint Backlog')
        self.assertContains(res, 'Dismissed')
        # Tidak ada kolom In Progress atau Done
        self.assertNotContains(res, 'In Progress')
        self.assertNotContains(res, 'Done</h2>')

        # Filter prioritas TINGGI
        res_tinggi = self.client.get('/user-story?prioritas=TINGGI')
        self.assertEqual(res_tinggi.status_code, 200)
        self.assertContains(res_tinggi, 'Gagal Login')
        self.assertNotContains(res_tinggi, 'Fitur Kecil')
