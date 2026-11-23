"""
Test suite untuk pembentukan label topik klaster dan management command refresh_cluster_labels (P0.3 & Follow-up).
Kompatibel dengan pytest dan django.test.runner.DiscoverRunner.
"""

from io import StringIO
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from sklearn.feature_extraction.text import TfidfVectorizer

from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from extraction.services.clustering import (
    bentuk_label_topik,
    cari_topik_representatif,
    bersihkan_teks,
    kelompokkan_ekstraksi,
)
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


class TopicLabelsAndRefreshTestCase(TestCase):
    def test_bentuk_label_topik_rule_mappings(self):
        """Menguji kecocokan aturan rule-based pembentukan label topik."""
        cases = [
            ("Tidak bisa menerima kode otp lewat sms", "", "Kendala Kode OTP"),
            ("Aplikasi selalu gagal saat verifikasi nomor handphone", "", "Kendala Kode OTP"),
            ("Gagal login masuk ke dalam aplikasi", "akun terkunci", "Masalah Login Aplikasi"),
            ("Aplikasi tiba-tiba force close dan keluar sendiri", "", "Aplikasi Sering Crash"),
            ("Tidak bisa mendaftar akun baru pengguna", "", "Gangguan Pendaftaran Akun"),
            ("Kamera tidak bisa mendeteksi wajah saat selfie foto ktp", "", "Masalah Kamera & Foto"),
            ("Aplikasi sangat lambat dan lemot sekali ketika dibuka", "", "Performa Aplikasi Lambat"),
            ("Server error dan koneksi selalu gagal terputus", "", "Gangguan Server & Koneksi"),
            ("NIK KTP tidak ditemukan saat validasi data kependudukan", "", "Verifikasi NIK & Data Kependudukan"),
            ("Gagal update versi terbaru di playstore", "", "Kendala Pembaruan Aplikasi"),
            ("Notifikasi pesan baru tidak pernah muncul", "", "Kendala Notifikasi Layanan"),
            ("Antrean faskes bpjs tidak bisa dipilih", "", "Layanan Faskes & Rujukan"),
            ("Gagal melakukan pembayaran iuran tagihan", "", "Kendala Pembayaran & Tagihan"),
            ("Akurasi titik lokasi gps tidak tepat", "", "Kendala GPS & Lokasi"),
        ]

        for what, why, expected in cases:
            label = bentuk_label_topik(what, why)
            self.assertEqual(label, expected, f"Input '{what}' should yield '{expected}', got '{label}'")

    def test_bentuk_label_topik_fallback_cleans_fillers(self):
        """Menguji pembersihan filler dan formatting pada kasus fallback."""
        what = "tolong min ini tombol simpan tidak bisa diklik sama sekali"
        label = bentuk_label_topik(what)
        self.assertTrue(label != "")
        self.assertLessEqual(len(label), 45)
        self.assertNotIn("tolong", label.lower())
        self.assertNotIn("min", label.lower().split())
        self.assertIn("tombol", label.lower())
        self.assertIn("simpan", label.lower())

    def test_clustering_applies_concise_labels(self):
        """
        Menguji bahwa kelompokkan_ekstraksi memberikan label ringkas untuk
        single-item maupun multi-item cluster.
        """
        app = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Layanan",
            package_name="id.go.layanan",
        )
        ulasan = Ulasan.objects.create(
            aplikasi=app,
            isi_ulasan="Aplikasi selalu force close saat mau buka form",
            tanggal_ulasan="2026-11-01",
            skor_bintang=1,
            status_filter=Ulasan.StatusFilter.LOLOS,
        )
        HasilEkstraksi.objects.create(
            ulasan=ulasan,
            teks_who="pengguna",
            teks_what="aplikasi force close keluar tiba-tiba",
            teks_why="tidak bisa buka formulir",
            skor_confidence=0.85,
        )

        hasil = kelompokkan_ekstraksi()
        self.assertEqual(hasil.cluster_baru, 1)

        c = Cluster.objects.first()
        self.assertIsNotNone(c)
        self.assertEqual(c.nama_topik, "Aplikasi Sering Crash")
        self.assertEqual(c.status_cluster, Cluster.StatusCluster.MENUNGGU_VALIDASI)
        self.assertEqual(c.jumlah_anggota, 1)

    def test_refresh_cluster_labels_command_dry_run_and_execution(self):
        """
        Menguji management command refresh_cluster_labels:
        1. --dry-run tidak mengubah database.
        2. Eksekusi nyata memperbarui label klaster MENUNGGU_VALIDASI.
        3. Klaster TERVALIDASI / DIABAIKAN tidak diubah.
        4. Klaster yang sudah punya UserStory tidak diubah.
        5. Keanggotaan ClusterAnggota tidak tersentuh.
        """
        app = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Uji",
            package_name="id.go.uji",
        )
        u = Ulasan.objects.create(
            aplikasi=app,
            isi_ulasan="review teks",
            tanggal_ulasan="2026-11-01",
            skor_bintang=1,
            status_filter=Ulasan.StatusFilter.LOLOS,
        )

        # 1. Klaster aman untuk di-refresh
        h1 = HasilEkstraksi.objects.create(
            ulasan=u, teks_who="w", teks_what="tidak bisa menerima kode otp sms", teks_why="", skor_confidence=0.9
        )
        c_aman = Cluster.objects.create(
            nama_topik="tidak bisa menerima kode otp sms sejak kemarin sore",
            jumlah_anggota=1,
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )
        ca1 = ClusterAnggota.objects.create(cluster=c_aman, hasil_ekstraksi=h1)

        # 2. Klaster tervalidasi (harus dilindungi)
        h2 = HasilEkstraksi.objects.create(
            ulasan=u, teks_who="w", teks_what="gagal login ke akun", teks_why="", skor_confidence=0.9
        )
        c_tervalidasi = Cluster.objects.create(
            nama_topik="Label Khusus Hasil Review Analyst",
            jumlah_anggota=1,
            status_cluster=Cluster.StatusCluster.TERVALIDASI,
        )
        ca2 = ClusterAnggota.objects.create(cluster=c_tervalidasi, hasil_ekstraksi=h2)

        # 3. Klaster dengan UserStory (harus dilindungi)
        h3 = HasilEkstraksi.objects.create(
            ulasan=u, teks_who="w", teks_what="kamera buram tidak bisa selfie", teks_why="", skor_confidence=0.9
        )
        c_bercerita = Cluster.objects.create(
            nama_topik="Label Topik Yang Sudah Disusun Story",
            jumlah_anggota=1,
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )
        ca3 = ClusterAnggota.objects.create(cluster=c_bercerita, hasil_ekstraksi=h3)
        UserStory.objects.create(
            cluster=c_bercerita,
            peran="pengguna",
            kebutuhan="bisa foto",
            alasan="verifikasi",
            skor_prioritas=50,
        )

        # --- Test Dry Run ---
        out_dry = StringIO()
        call_command("refresh_cluster_labels", dry_run=True, stdout=out_dry)
        dry_output = out_dry.getvalue()

        self.assertIn("[DRY-RUN]", dry_output)
        self.assertIn("Kendala Kode OTP", dry_output)

        c_aman.refresh_from_db()
        self.assertEqual(c_aman.nama_topik, "tidak bisa menerima kode otp sms sejak kemarin sore")

        # --- Test Real Run ---
        out_real = StringIO()
        call_command("refresh_cluster_labels", stdout=out_real)
        real_output = out_real.getvalue()

        self.assertIn("Selesai: 1 cluster diperiksa", real_output)

        c_aman.refresh_from_db()
        self.assertEqual(c_aman.nama_topik, "Kendala Kode OTP")
        self.assertEqual(c_aman.jumlah_anggota, 1)

        c_tervalidasi.refresh_from_db()
        self.assertEqual(c_tervalidasi.nama_topik, "Label Khusus Hasil Review Analyst")

        c_bercerita.refresh_from_db()
        self.assertEqual(c_bercerita.nama_topik, "Label Topik Yang Sudah Disusun Story")

        self.assertEqual(ClusterAnggota.objects.count(), 3)
        self.assertEqual(ClusterAnggota.objects.filter(cluster=c_aman).first(), ca1)
        self.assertEqual(ClusterAnggota.objects.filter(cluster=c_tervalidasi).first(), ca2)
        self.assertEqual(ClusterAnggota.objects.filter(cluster=c_bercerita).first(), ca3)

    def test_cari_topik_representatif_same_what_different_why(self):
        """
        Memastikan cari_topik_representatif mengembalikan objek HasilEkstraksi utuh
        (bukan sekadar teks_what) sehingga WHAT dan WHY selalu berasal dari objek yang sama.
        """
        app = Aplikasi.objects.create(nama_aplikasi="App Uji", package_name="id.go.test")
        u1 = Ulasan.objects.create(aplikasi=app, isi_ulasan="Ulasan 1", skor_bintang=1, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS)
        u2 = Ulasan.objects.create(aplikasi=app, isi_ulasan="Ulasan 2", skor_bintang=1, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS)

        h1 = HasilEkstraksi.objects.create(
            ulasan=u1, teks_who="warga", teks_what="gagal login ke dalam aplikasi", teks_why="kata sandi salah", skor_confidence=0.88
        )
        h2 = HasilEkstraksi.objects.create(
            ulasan=u2, teks_who="warga", teks_what="gagal login ke dalam aplikasi", teks_why="akun terkunci oleh sistem", skor_confidence=0.92
        )

        items = [h1, h2]
        korpus = [f"{bersihkan_teks(it.teks_what)} {bersihkan_teks(it.teks_why)}" for it in items]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        X = vectorizer.fit_transform(korpus)

        best_item = cari_topik_representatif(items, X, [0, 1])

        self.assertIsInstance(best_item, HasilEkstraksi)
        self.assertIn(best_item.pk, (h1.pk, h2.pk))
        self.assertEqual(best_item.teks_what, "gagal login ke dalam aplikasi")
        if best_item.pk == h1.pk:
            self.assertEqual(best_item.teks_why, "kata sandi salah")
        else:
            self.assertEqual(best_item.teks_why, "akun terkunci oleh sistem")

    def test_analyst_manual_label_is_protected_from_refresh(self):
        """
        Memastikan klaster yang ditandai nama_topik_manual=True tidak pernah ditimpa
        oleh management command refresh_cluster_labels.
        """
        app = Aplikasi.objects.create(nama_aplikasi="App Manual", package_name="id.go.manual")
        u = Ulasan.objects.create(aplikasi=app, isi_ulasan="review teks", skor_bintang=1, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS)
        h = HasilEkstraksi.objects.create(
            ulasan=u, teks_who="w", teks_what="tidak bisa menerima kode otp", teks_why="", skor_confidence=0.9
        )

        c_manual = Cluster.objects.create(
            nama_topik="Label Buatan Khusus Analis Manual",
            nama_topik_manual=True,
            jumlah_anggota=1,
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )
        ClusterAnggota.objects.create(cluster=c_manual, hasil_ekstraksi=h)

        out = StringIO()
        call_command("refresh_cluster_labels", stdout=out)
        output = out.getvalue()

        c_manual.refresh_from_db()
        self.assertEqual(c_manual.nama_topik, "Label Buatan Khusus Analis Manual")
        self.assertTrue(c_manual.nama_topik_manual)
        self.assertIn("0 label cluster diperbarui", output)

    def test_cluster_admin_marks_manual_on_edit(self):
        """
        Memastikan Django Admin menandai nama_topik_manual=True ketika
        nama_topik diubah melalui antarmuka admin.
        """
        from django.contrib.admin.sites import AdminSite
        from extraction.admin import ClusterAdmin

        admin_site = AdminSite()
        cluster_admin = ClusterAdmin(Cluster, admin_site)

        cluster = Cluster.objects.create(
            nama_topik="Topik Otomatis",
            nama_topik_manual=False,
            jumlah_anggota=1,
        )

        class DummyForm:
            changed_data = ["nama_topik"]

        rf = RequestFactory()
        request = rf.post("/admin/extraction/cluster/")
        cluster.nama_topik = "Topik Diubah Analis di Admin"
        cluster_admin.save_model(request, cluster, DummyForm(), change=True)

        cluster.refresh_from_db()
        self.assertEqual(cluster.nama_topik, "Topik Diubah Analis di Admin")
        self.assertTrue(cluster.nama_topik_manual)
