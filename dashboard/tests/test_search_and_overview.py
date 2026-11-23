"""Uji dashboard overview dan pencarian global berbasis peran.
Kompatibel dengan pytest dan django.test.runner.DiscoverRunner.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


def _user(username, role):
    return User.objects.create_user(
        username=username,
        email=f"{username}@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=role,
    )


class SearchAndOverviewTestCase(TestCase):
    def _create_search_data(self):
        app = Aplikasi.objects.create(
            nama_aplikasi="Aplikasi Notifikasi",
            package_name="com.example.notifikasi",
        )

        ulasan = Ulasan.objects.create(
            aplikasi=app,
            isi_ulasan=(
                "Notifikasi sering terlambat masuk "
                "sehingga informasi penting terlewat"
            ),
            tanggal_ulasan="2024-11-01",
            skor_bintang=2,
            status_filter=Ulasan.StatusFilter.LOLOS,
        )

        hasil = HasilEkstraksi.objects.create(
            ulasan=ulasan,
            teks_who="pengguna aplikasi",
            teks_what="menerima notifikasi terlambat",
            teks_why="informasi penting terlewat",
            skor_confidence=0.88,
        )

        cluster = Cluster.objects.create(
            nama_topik="Notifikasi Lambat",
            jumlah_anggota=1,
            skor_signifikansi=4.5,
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
        )

        ClusterAnggota.objects.create(
            cluster=cluster,
            hasil_ekstraksi=hasil,
        )

        story = UserStory.objects.create(
            cluster=cluster,
            peran="pengguna aplikasi",
            kebutuhan="mendapat notifikasi lebih cepat",
            alasan="informasi penting tidak terlambat diterima",
            skor_prioritas=80,
            status_persetujuan=(
                UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN
            ),
        )

        return {
            "app": app,
            "ulasan": ulasan,
            "cluster": cluster,
            "story": story,
        }

    def test_overview_renders_kpi_and_honest_empty_chart(self):
        user = _user(
            "dev_overview",
            User.RolePengguna.TIM_DEVELOPER,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("dashboard:overview")
        )
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)

        # KPI Dashboard tetap ditampilkan
        self.assertIn("Total Scraped Reviews", body)
        self.assertIn("Filtered Noise Rate", body)
        self.assertIn("Extracted User Stories", body)
        self.assertIn("Model Confidence Score", body)

        # Komponen Dashboard utama tetap tersedia
        self.assertIn("Review Sentiment vs. User Story Generation", body)
        self.assertIn("Biggest Topic Cluster", body)
        self.assertIn("Rata-rata Rating Aplikasi", body)

        # Status Pipeline sengaja dihapus dari desain Dashboard
        self.assertNotIn("Status Pipeline", body)

        # Saat belum ada data, grafik menampilkan empty state
        self.assertIn("Tren belum dapat ditampilkan", body)
        self.assertNotIn("dashboard-chart-data", body)

    def test_overview_embeds_real_chart_payload(self):
        self._create_search_data()
        user = _user(
            "re_overview",
            User.RolePengguna.REQUIREMENTS_ENGINEER,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("dashboard:overview")
        )
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)

        # Grafik menggunakan data aktual dari backend
        self.assertIn('id="dashboard-chart-data"', body)
        self.assertIn("data-chart-source", body)

        # Data cluster dan aplikasi berasal dari database pengujian
        self.assertIn("Notifikasi Lambat", body)
        self.assertIn("Aplikasi Notifikasi", body)

    def test_search_is_scoped_for_each_role(self):
        self._create_search_data()
        expectations = {
            User.RolePengguna.REQUIREMENTS_ENGINEER: {
                "reviews",
                "clusters",
                "stories",
            },
            User.RolePengguna.ANALYST: {
                "reviews",
                "clusters",
            },
            User.RolePengguna.PRODUCT_OWNER: {
                "stories",
            },
        }

        for index, (role, expected_keys) in enumerate(
            expectations.items()
        ):
            user = _user(
                f"search_{index}",
                role,
            )

            self.client.force_login(user)

            response = self.client.get(
                reverse("dashboard:search"),
                {"q": "Notifikasi"},
            )

            keys = {
                group["key"]
                for group in response.context["groups"]
            }

            self.assertEqual(response.status_code, 200)
            self.assertEqual(keys, expected_keys)
            self.assertGreaterEqual(response.context["total"], 1)

    def test_short_query_shows_prompt_not_results(self):
        user = _user(
            "re_short",
            User.RolePengguna.REQUIREMENTS_ENGINEER,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("dashboard:search"),
            {"q": "n"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["groups"], [])
        self.assertFalse(response.context["searched"])

    def test_search_empty_result_is_honest(self):
        user = _user(
            "po_empty",
            User.RolePengguna.PRODUCT_OWNER,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("dashboard:search"),
            {"q": "tidakadayangcocok"},
        )

        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 0)
        self.assertIn("Tidak ada hasil", body)
