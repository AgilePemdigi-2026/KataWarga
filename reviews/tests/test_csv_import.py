"""Uji impor CSV ulasan (Requirements Engineer)."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest

from accounts.models import User
from reviews.models import Aplikasi, Ulasan


pytestmark = pytest.mark.django_db


def _csv(text):
    return SimpleUploadedFile(
        "ulasan.csv",
        text.encode("utf-8"),
        content_type="text/csv",
    )


@pytest.fixture
def re_user(db):
    return User.objects.create_user(
        username="re_csv",
        email="re_csv@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=User.RolePengguna.REQUIREMENTS_ENGINEER,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        username="analyst_csv",
        email="analyst_csv@katawarga.test",
        password="Xk9!pQ2#mL7v",
        role=User.RolePengguna.ANALYST,
    )


def test_import_page_is_re_only(client, re_user, analyst_user):
    client.force_login(analyst_user)
    assert client.get(reverse("reviews:import_csv")).status_code == 403

    client.force_login(re_user)
    response = client.get(reverse("reviews:import_csv"))
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Impor Ulasan dari CSV" in body
    assert "package_name" in body
    assert reverse("reviews:csv_template") in body


def test_csv_template_download_is_real_file(client, re_user):
    client.force_login(re_user)
    response = client.get(reverse("reviews:csv_template"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    assert "package_name" in response.content.decode("utf-8-sig")


def test_valid_csv_import_applies_existing_filters(client, re_user):
    client.force_login(re_user)
    payload = _csv(
        "package_name,nama_aplikasi,review_id,isi_ulasan,tanggal_ulasan,skor_bintang\n"
        "com.example.csv,Aplikasi CSV,csv-001,"
        "Aplikasi sering gagal menyimpan data penting,2024-11-01,2\n"
        "com.example.csv,Aplikasi CSV,csv-002,"
        "bagus,2024-11-01,5\n"
    )

    response = client.post(
        reverse("reviews:import_csv"),
        {"file": payload},
        follow=True,
    )

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "2 ulasan diimpor" in body
    assert "1 lolos filter" in body
    assert "1 ditandai dibuang" in body

    app = Aplikasi.objects.get(package_name="com.example.csv")
    ulasan = Ulasan.objects.filter(aplikasi=app).order_by("review_id")
    assert ulasan.count() == 2
    assert ulasan[0].status_filter == Ulasan.StatusFilter.LOLOS
    assert ulasan[1].status_filter == Ulasan.StatusFilter.DIBUANG


def test_invalid_row_rolls_back_entire_import(client, re_user):
    client.force_login(re_user)
    payload = _csv(
        "package_name,nama_aplikasi,review_id,isi_ulasan,tanggal_ulasan,skor_bintang\n"
        "com.example.csv,Aplikasi CSV,csv-001,"
        "Ulasan ini seharusnya valid dan cukup panjang,2024-11-01,4\n"
        "com.example.csv,Aplikasi CSV,csv-002,"
        "Ulasan valid tetapi tanggal salah,2026-99-99,4\n"
    )

    response = client.post(
        reverse("reviews:import_csv"),
        {"file": payload},
        follow=True,
    )

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Tidak ada data yang disimpan" in body
    assert "tanggal_ulasan harus valid" in body
    assert Ulasan.objects.count() == 0
    assert Aplikasi.objects.filter(package_name="com.example.csv").count() == 0


def test_duplicate_review_id_is_skipped(client, re_user):
    client.force_login(re_user)
    baris = "com.example.csv,Aplikasi CSV,csv-001,Ulasan yang cukup panjang untuk lolos filter,2024-11-01,4\n"
    header = "package_name,nama_aplikasi,review_id,isi_ulasan,tanggal_ulasan,skor_bintang\n"

    client.post(
        reverse("reviews:import_csv"),
        {"file": _csv(header + baris)},
        follow=True,
    )
    response = client.post(
        reverse("reviews:import_csv"),
        {"file": _csv(header + baris)},
        follow=True,
    )

    assert response.status_code == 200
    assert "1 duplikat dilewati" in response.content.decode("utf-8")
    assert Ulasan.objects.count() == 1
