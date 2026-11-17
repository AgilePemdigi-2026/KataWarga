"""Uji dashboard overview dan pencarian global berbasis peran."""
import pytest
from django.urls import reverse

from accounts.models import User
from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


pytestmark = pytest.mark.django_db


def _user(username, role):
    return User.objects.create_user(
        username=username,
        email=f"{username}@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=role,
    )


@pytest.fixture
def search_data(db):
    app = Aplikasi.objects.create(
        nama_aplikasi="Aplikasi Notifikasi",
        package_name="com.example.notifikasi",
    )
    ulasan = Ulasan.objects.create(
        aplikasi=app,
        isi_ulasan="Notifikasi sering terlambat masuk sehingga informasi penting terlewat",
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
    ClusterAnggota.objects.create(cluster=cluster, hasil_ekstraksi=hasil)
    story = UserStory.objects.create(
        cluster=cluster,
        peran="pengguna aplikasi",
        kebutuhan="mendapat notifikasi lebih cepat",
        alasan="informasi penting tidak terlambat diterima",
        skor_prioritas=80,
        status_persetujuan=UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN,
    )
    return {"app": app, "ulasan": ulasan, "cluster": cluster, "story": story}


def test_overview_renders_kpi_and_honest_empty_chart(client):
    user = _user("dev_overview", User.RolePengguna.TIM_DEVELOPER)
    client.force_login(user)

    response = client.get(reverse("dashboard:overview"))
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Total Scraped Reviews" in body
    assert "Status Pipeline" in body
    assert "Tren belum dapat ditampilkan" in body
    assert "dashboard-chart-data" not in body


def test_overview_embeds_real_chart_payload(client, search_data):
    user = _user("re_overview", User.RolePengguna.REQUIREMENTS_ENGINEER)
    client.force_login(user)

    response = client.get(reverse("dashboard:overview"))
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'id="dashboard-chart-data"' in body
    assert "data-chart-source" in body
    assert "Notifikasi Lambat" in body
    assert "Aplikasi Notifikasi" in body


def test_search_is_scoped_for_each_role(client, search_data):
    expectations = {
        User.RolePengguna.REQUIREMENTS_ENGINEER: {
            "reviews", "clusters", "stories",
        },
        User.RolePengguna.ANALYST: {"reviews", "clusters"},
        User.RolePengguna.PRODUCT_OWNER: {"stories"},
    }

    for index, (role, expected_keys) in enumerate(expectations.items()):
        user = _user(f"search_{index}", role)
        client.force_login(user)
        response = client.get(reverse("dashboard:search"), {"q": "Notifikasi"})
        keys = {group["key"] for group in response.context["groups"]}

        assert response.status_code == 200
        assert keys == expected_keys
        assert response.context["total"] >= 1


def test_short_query_shows_prompt_not_results(client):
    user = _user("re_short", User.RolePengguna.REQUIREMENTS_ENGINEER)
    client.force_login(user)

    response = client.get(reverse("dashboard:search"), {"q": "n"})

    assert response.status_code == 200
    assert response.context["groups"] == []
    assert response.context["searched"] is False


def test_search_empty_result_is_honest(client):
    user = _user("po_empty", User.RolePengguna.PRODUCT_OWNER)
    client.force_login(user)

    response = client.get(reverse("dashboard:search"), {"q": "tidakadayangcocok"})
    body = response.content.decode("utf-8")

    assert response.status_code == 200
    assert response.context["total"] == 0
    assert "Tidak ada hasil" in body
