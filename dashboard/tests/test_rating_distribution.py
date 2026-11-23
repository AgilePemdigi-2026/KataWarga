"""
Test suite untuk distribusi rating dan metrik dashboard (P0.2 & Follow-up).
Memastikan:
- Distribusi bintang 1-5 dihitung akurat dari database aktual.
- Pemisahan distribusi antar aplikasi (tidak bercampur/bocor).
- Rating null atau di luar rentang 1-5 ditangani dengan benar.
- Perhitungan persentase konsisten dengan total ulasan valid.
- Aplikasi tanpa ulasan menghasilkan fallback aman tanpa error pembagian nol.
Kompatibel dengan pytest dan django.test.runner.DiscoverRunner.
"""

from django.test import TestCase
from reviews.models import Aplikasi, Ulasan
from dashboard.services.metrics import ringkasan_dashboard, _distribusi_rating


class RatingDistributionTestCase(TestCase):
    def setUp(self):
        self.app1 = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Satu",
            package_name="id.go.app.satu",
            kategori="Pelayanan Publik",
        )
        self.app2 = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Dua",
            package_name="id.go.app.dua",
            kategori="Kesehatan",
        )
        self.app_empty = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Kosong",
            package_name="id.go.app.kosong",
            kategori="Sosial",
        )

        # Ulasan untuk Aplikasi Satu:
        # 1 bintang: 1
        # 2 bintang: 2
        # 3 bintang: 3
        # 4 bintang: 4
        # 5 bintang: 10
        # Total ulasan valid: 20, Total poin: 80, Avg valid = 4.0
        star_counts_1 = {1: 1, 2: 2, 3: 3, 4: 4, 5: 10}
        for star, count in star_counts_1.items():
            for i in range(count):
                Ulasan.objects.create(
                    aplikasi=self.app1,
                    isi_ulasan=f"Review app1 star {star} - {i}",
                    tanggal_ulasan="2026-11-01",
                    skor_bintang=star,
                    status_filter=Ulasan.StatusFilter.LOLOS,
                )
        # Review dengan rating di luar rentang 1-5 (skor 0 dan 6)
        for i in range(2):
            Ulasan.objects.create(
                aplikasi=self.app1,
                isi_ulasan=f"Review app1 zero star - {i}",
                tanggal_ulasan="2026-11-01",
                skor_bintang=0,
                status_filter=Ulasan.StatusFilter.LOLOS,
            )
        for i in range(2):
            Ulasan.objects.create(
                aplikasi=self.app1,
                isi_ulasan=f"Review app1 six star - {i}",
                tanggal_ulasan="2026-11-01",
                skor_bintang=6,
                status_filter=Ulasan.StatusFilter.LOLOS,
            )

        # Ulasan untuk Aplikasi Dua:
        # 1 bintang: 5
        # 5 bintang: 15
        # Total ulasan valid: 20
        star_counts_2 = {1: 5, 5: 15}
        for star, count in star_counts_2.items():
            for i in range(count):
                Ulasan.objects.create(
                    aplikasi=self.app2,
                    isi_ulasan=f"Review app2 star {star} - {i}",
                    tanggal_ulasan="2026-11-01",
                    skor_bintang=star,
                    status_filter=Ulasan.StatusFilter.LOLOS,
                )

    def test_distribusi_rating_raw_service(self):
        """Memastikan _distribusi_rating mengembalikan key (aplikasi_id, skor_bintang) yang tepat."""
        dist = _distribusi_rating()

        # app1 checks
        self.assertEqual(dist.get((self.app1.pk, 1)), 1)
        self.assertEqual(dist.get((self.app1.pk, 2)), 2)
        self.assertEqual(dist.get((self.app1.pk, 3)), 3)
        self.assertEqual(dist.get((self.app1.pk, 4)), 4)
        self.assertEqual(dist.get((self.app1.pk, 5)), 10)

        # app2 checks
        self.assertEqual(dist.get((self.app2.pk, 1)), 5)
        self.assertNotIn((self.app2.pk, 2), dist)
        self.assertNotIn((self.app2.pk, 3), dist)
        self.assertNotIn((self.app2.pk, 4), dist)
        self.assertEqual(dist.get((self.app2.pk, 5)), 15)

    def test_ringkasan_dashboard_rating_distribution(self):
        """
        Memastikan ringkasan_dashboard() menghitung jumlah dan persentase
        bintang 1-5 secara terpisah per aplikasi.
        """
        data = ringkasan_dashboard()
        rating_per_app = {app.nama_aplikasi: app for app in data["aplikasi"]}

        # --- Verifikasi App 1 ---
        row1 = rating_per_app[self.app1.nama_aplikasi]
        # Denominator harus 20 (hanya ulasan yang memiliki skor_bintang 1..5)
        # Rata-rata dari Django Avg dengan filter valid 1-5 menghasilkan tepat 80 / 20 = 4.0
        self.assertEqual(float(row1.rata_rating), 4.0)
        # Jumlah ulasan tersimpan tetap mempertahankan seluruh ulasan di DB (20 valid + 4 di luar rentang = 24)
        self.assertEqual(row1.jumlah_ulasan, 24)

        dist1 = row1.distribusi_bintang
        stars_map_1 = {item["bintang"]: item for item in dist1}
        self.assertEqual(stars_map_1[1]["jumlah"], 1)
        self.assertEqual(stars_map_1[1]["persen"], 5.0)  # 1 / 20 * 100
        self.assertEqual(stars_map_1[2]["jumlah"], 2)
        self.assertEqual(stars_map_1[2]["persen"], 10.0)  # 2 / 20 * 100
        self.assertEqual(stars_map_1[3]["jumlah"], 3)
        self.assertEqual(stars_map_1[3]["persen"], 15.0)  # 3 / 20 * 100
        self.assertEqual(stars_map_1[4]["jumlah"], 4)
        self.assertEqual(stars_map_1[4]["persen"], 20.0)  # 4 / 20 * 100
        self.assertEqual(stars_map_1[5]["jumlah"], 10)
        self.assertEqual(stars_map_1[5]["persen"], 50.0)  # 10 / 20 * 100

        total_persen_1 = sum(item["persen"] for item in dist1)
        self.assertAlmostEqual(total_persen_1, 100.0, places=1)

        # --- Verifikasi App 2 ---
        row2 = rating_per_app[self.app2.nama_aplikasi]
        self.assertEqual(float(row2.rata_rating), 4.0)
        dist2 = row2.distribusi_bintang
        stars_map_2 = {item["bintang"]: item for item in dist2}
        self.assertEqual(stars_map_2[1]["jumlah"], 5)
        self.assertEqual(stars_map_2[1]["persen"], 25.0)  # 5 / 20 * 100
        self.assertEqual(stars_map_2[2]["jumlah"], 0)
        self.assertEqual(stars_map_2[2]["persen"], 0.0)
        self.assertEqual(stars_map_2[3]["jumlah"], 0)
        self.assertEqual(stars_map_2[3]["persen"], 0.0)
        self.assertEqual(stars_map_2[4]["jumlah"], 0)
        self.assertEqual(stars_map_2[4]["persen"], 0.0)
        self.assertEqual(stars_map_2[5]["jumlah"], 15)
        self.assertEqual(stars_map_2[5]["persen"], 75.0)  # 15 / 20 * 100

        total_persen_2 = sum(item["persen"] for item in dist2)
        self.assertAlmostEqual(total_persen_2, 100.0, places=1)

        # --- Verifikasi App Kosong (Zero reviews) ---
        row_empty = rating_per_app[self.app_empty.nama_aplikasi]
        self.assertEqual(float(row_empty.rata_rating or 0.0), 0.0)
        self.assertEqual(row_empty.jumlah_ulasan, 0)
        for item in row_empty.distribusi_bintang:
            self.assertEqual(item["jumlah"], 0)
            self.assertEqual(item["persen"], 0.0)

    def test_rating_out_of_range_and_isolation(self):
        """
        Memastikan rating di luar rentang 1-5 (skor 0, 6, 99) tidak mencemari
        rata_rating maupun distribusi bintang, dan jumlah ulasan tersimpan tetap akurat.
        """
        app = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Filter Rating",
            package_name="id.go.filter.rating",
        )

        Ulasan.objects.create(
            aplikasi=app, isi_ulasan="Good 4", skor_bintang=4, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS
        )
        Ulasan.objects.create(
            aplikasi=app, isi_ulasan="Great 5", skor_bintang=5, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS
        )
        Ulasan.objects.create(
            aplikasi=app, isi_ulasan="Invalid 0", skor_bintang=0, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS
        )
        Ulasan.objects.create(
            aplikasi=app, isi_ulasan="Invalid 7", skor_bintang=7, tanggal_ulasan="2026-11-01", status_filter=Ulasan.StatusFilter.LOLOS
        )

        data = ringkasan_dashboard()
        rating_per_app = {a.nama_aplikasi: a for a in data["aplikasi"]}
        row = rating_per_app[app.nama_aplikasi]

        self.assertEqual(float(row.rata_rating), 4.5)
        self.assertEqual(row.jumlah_ulasan, 4)

        stars = {item["bintang"]: item for item in row.distribusi_bintang}
        self.assertEqual(stars[5]["jumlah"], 1)
        self.assertEqual(stars[5]["persen"], 50.0)
        self.assertEqual(stars[4]["jumlah"], 1)
        self.assertEqual(stars[4]["persen"], 50.0)
        self.assertEqual(stars[3]["jumlah"], 0)
        self.assertEqual(stars[3]["persen"], 0.0)
        self.assertEqual(stars[2]["jumlah"], 0)
        self.assertEqual(stars[2]["persen"], 0.0)
        self.assertEqual(stars[1]["jumlah"], 0)
        self.assertEqual(stars[1]["persen"], 0.0)
