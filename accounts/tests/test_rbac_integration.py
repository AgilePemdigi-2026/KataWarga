"""
Uji integrasi RBAC, sidebar per peran, dan alur autentikasi KataWarga.

Cakupan:
- redirect login per peran dan pengalihan pengguna anonim;
- sidebar yang berbeda per peran, penanda menu aktif, dan identitas pengguna;
- penolakan lintas peran pada halaman maupun aksi POST;
- validasi Analyst dan mode monitoring read-only Requirements Engineer;
- persetujuan User Story oleh Product Owner;
- eksekusi Sprint Backlog oleh Tim Developer;
- simulasi peran hanya untuk staf pada DEBUG, tanpa mengubah role database;
- logout berbasis POST yang membersihkan sesi simulasi;
- pendaftaran mandiri tidak dapat memilih role istimewa atau is_staff.
"""
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import pytest
from django.urls import reverse

from accounts.models import User
from backlog.models import BacklogItem
from extraction.models import Cluster, ClusterAnggota, HasilEkstraksi
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


pytestmark = pytest.mark.django_db

PASSWORD = "Xk9!pQ2#mL7v"


def _make_user(username, role, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@katawarga.test",
        password=PASSWORD,
        role=role,
        **extra,
    )


@pytest.fixture
def users(db):
    """Satu pengguna aktif untuk setiap peran, plus satu staf untuk simulasi."""
    return {
        "re": _make_user(
            "re_user", User.RolePengguna.REQUIREMENTS_ENGINEER
        ),
        "analyst": _make_user("analyst_user", User.RolePengguna.ANALYST),
        "po": _make_user("po_user", User.RolePengguna.PRODUCT_OWNER),
        "dev": _make_user("dev_user", User.RolePengguna.TIM_DEVELOPER),
        "staff_po": _make_user(
            "staff_po",
            User.RolePengguna.PRODUCT_OWNER,
            is_staff=True,
        ),
    }


@pytest.fixture
def rbac_data(users):
    """
    Data minimal untuk menguji detail cluster, approval, dan eksekusi backlog.

    1. Cluster menunggu validasi (untuk Analyst).
    2. User Story menunggu persetujuan PO.
    3. User Story yang sudah disetujui + item backlog siap dieksekusi.
    """
    app = Aplikasi.objects.create(
        nama_aplikasi="KataWarga Test",
        package_name="com.example.katawarga",
        kategori="Utilitas",
    )

    def buat_cluster(nama_topik, tanggal, status_cluster):
        ulasan = Ulasan.objects.create(
            aplikasi=app,
            username_reviewer="pengulas",
            isi_ulasan=f"Keluhan untuk topik {nama_topik}",
            tanggal_ulasan=tanggal,
            skor_bintang=1,
            status_filter=Ulasan.StatusFilter.LOLOS,
        )
        hasil = HasilEkstraksi.objects.create(
            ulasan=ulasan,
            teks_who="pengguna",
            teks_what=f"mengalami masalah {nama_topik.lower()}",
            teks_why="agar dapat memakai aplikasi dengan lancar",
            skor_confidence=0.91,
        )
        cluster = Cluster.objects.create(
            nama_topik=nama_topik,
            jumlah_anggota=1,
            skor_signifikansi=5.0,
            status_cluster=status_cluster,
        )
        ClusterAnggota.objects.create(
            cluster=cluster, hasil_ekstraksi=hasil
        )
        return cluster, hasil

    cluster_waiting, hasil_waiting = buat_cluster(
        "Gagal Login",
        "2026-10-01",
        Cluster.StatusCluster.MENUNGGU_VALIDASI,
    )
    cluster_review, _ = buat_cluster(
        "Notifikasi Lambat",
        "2026-10-02",
        Cluster.StatusCluster.TERVALIDASI,
    )
    cluster_approved, _ = buat_cluster(
        "Fitur Gelap",
        "2026-10-03",
        Cluster.StatusCluster.TERVALIDASI,
    )

    story_review = UserStory.objects.create(
        cluster=cluster_review,
        peran="pengguna aplikasi",
        kebutuhan="mendapat notifikasi lebih cepat",
        alasan="informasi penting tidak terlambat diterima",
        skor_prioritas=80.0,
        kategori_prioritas=UserStory.LevelPrioritas.TINGGI,
        status_persetujuan=UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN,
    )
    story_approved = UserStory.objects.create(
        cluster=cluster_approved,
        peran="pengguna aplikasi",
        kebutuhan="mendapat tema gelap",
        alasan="lebih nyaman digunakan pada malam hari",
        skor_prioritas=70.0,
        kategori_prioritas=UserStory.LevelPrioritas.SEDANG,
        status_persetujuan=UserStory.StatusPersetujuan.DISETUJUI,
    )
    backlog_item = BacklogItem.objects.create(
        user_story=story_approved,
        status_eksekusi=BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI,
    )

    return {
        "app": app,
        "cluster_waiting": cluster_waiting,
        "hasil_waiting": hasil_waiting,
        "cluster_review": cluster_review,
        "cluster_approved": cluster_approved,
        "story_review": story_review,
        "story_approved": story_approved,
        "backlog_item": backlog_item,
    }


# ---------------------------------------------------------------------------
# Autentikasi dan redirect
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "user_key,url_name",
    [
        ("re", "extraction:pipeline"),
        ("analyst", "extraction:validasi_list"),
        ("po", "stories:board"),
        ("dev", "backlog:list"),
    ],
)
def test_login_redirects_each_role_to_its_home(
    client, users, user_key, url_name
):
    response = client.post(
        reverse("accounts:login"),
        {"username": users[user_key].username, "password": PASSWORD},
    )

    assert response.status_code == 302
    assert response.url == reverse(url_name)


def test_login_ignores_unsafe_next_parameter(client, users):
    response = client.post(
        reverse("accounts:login"),
        {
            "username": "re_user",
            "password": PASSWORD,
            "next": "https://evil.example/ambil-alih",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("extraction:pipeline")


@pytest.mark.parametrize(
    "url_name",
    [
        "dashboard:overview",
        "extraction:pipeline",
        "extraction:validasi_list",
        "stories:susun",
        "stories:board",
        "backlog:list",
        "accounts:kelola_role",
    ],
)
def test_anonymous_users_are_redirected_to_login(client, url_name):
    protected_url = reverse(url_name)
    response = client.get(protected_url)

    assert response.status_code == 302

    parsed = urlparse(response.url)
    assert parsed.path == reverse("accounts:login")
    assert parse_qs(parsed.query).get("next") == [protected_url]


# ---------------------------------------------------------------------------
# Sidebar per peran
# ---------------------------------------------------------------------------


SIDEBAR_CASES = [
    (
        "re",
        {"dashboard", "pipeline", "clustering", "compose", "roles"},
        {"validasi", "stories", "story_detail", "backlog", "backlog_detail"},
        "Requirements Engineer",
    ),
    (
        "analyst",
        {"dashboard", "pipeline", "validasi", "clustering"},
        {"compose", "stories", "story_detail", "backlog", "backlog_detail", "roles"},
        "Analyst",
    ),
    (
        "po",
        {"dashboard", "stories", "story_detail"},
        {"pipeline", "clustering", "validasi", "compose", "backlog", "backlog_detail", "roles"},
        "Product Owner",
    ),
    (
        "dev",
        {"dashboard", "backlog", "backlog_detail"},
        {"pipeline", "clustering", "validasi", "compose", "stories", "story_detail", "roles"},
        "Tim Developer",
    ),
]


@pytest.mark.parametrize(
    "user_key,expected_navs,forbidden_navs,role_label",
    SIDEBAR_CASES,
)
def test_sidebar_is_role_specific_and_shows_identity(
    client,
    users,
    user_key,
    expected_navs,
    forbidden_navs,
    role_label,
):
    user = users[user_key]
    client.force_login(user)
    response = client.get(reverse("dashboard:overview"))

    assert response.status_code == 200
    body = response.content.decode("utf-8")

    for nav in expected_navs:
        assert f'data-nav="{nav}"' in body, f"menu {nav} hilang"
    for nav in forbidden_navs:
        assert f'data-nav="{nav}"' not in body, f"menu {nav} tidak boleh tampil"

    assert user.username in body
    assert role_label in body
    assert response.context["effective_role"] == user.role


@pytest.mark.parametrize(
    "user_key,url_name,active_section",
    [
        ("re", "extraction:pipeline", "pipeline"),
        ("analyst", "extraction:validasi_list", "validasi"),
        ("po", "stories:board", "stories"),
        ("dev", "backlog:list", "backlog"),
    ],
)
def test_sidebar_marks_the_current_section_active(
    client, users, user_key, url_name, active_section
):
    client.force_login(users[user_key])
    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert response.context["active_section"] == active_section
    assert response.content.decode("utf-8").count('aria-current="page"') == 1


# ---------------------------------------------------------------------------
# Matriks akses halaman dan detail
# ---------------------------------------------------------------------------


PAGE_ACCESS_CASES = [
    # Dashboard: semua peran yang login.
    ("re", "dashboard:overview", 200),
    ("analyst", "dashboard:overview", 200),
    ("po", "dashboard:overview", 200),
    ("dev", "dashboard:overview", 200),
    # Pipeline: RE dan Analyst (monitoring).
    ("re", "extraction:pipeline", 200),
    ("analyst", "extraction:pipeline", 200),
    ("po", "extraction:pipeline", 403),
    ("dev", "extraction:pipeline", 403),
    # Validasi: Analyst saja.
    ("analyst", "extraction:validasi_list", 200),
    ("re", "extraction:validasi_list", 403),
    ("po", "extraction:validasi_list", 403),
    ("dev", "extraction:validasi_list", 403),
    # Susun User Story: RE saja.
    ("re", "stories:susun", 200),
    ("analyst", "stories:susun", 403),
    ("po", "stories:susun", 403),
    ("dev", "stories:susun", 403),
    # Board: PO saja.
    ("po", "stories:board", 200),
    ("re", "stories:board", 403),
    ("analyst", "stories:board", 403),
    ("dev", "stories:board", 403),
    # Backlog: PO (read-only) dan Developer.
    ("po", "backlog:list", 200),
    ("dev", "backlog:list", 200),
    ("re", "backlog:list", 403),
    ("analyst", "backlog:list", 403),
    # Kelola role: RE dan staf; staf diuji terpisah.
    ("re", "accounts:kelola_role", 200),
    ("analyst", "accounts:kelola_role", 403),
    ("po", "accounts:kelola_role", 403),
    ("dev", "accounts:kelola_role", 403),
]


@pytest.mark.parametrize("user_key,url_name,expected", PAGE_ACCESS_CASES)
def test_page_access_matrix(client, users, user_key, url_name, expected):
    client.force_login(users[user_key])
    response = client.get(reverse(url_name))

    assert response.status_code == expected


@pytest.mark.parametrize(
    "user_key,page,expected",
    [
        ("re", "story", 200),
        ("po", "story", 200),
        ("dev", "story", 200),
        ("analyst", "story", 403),
        ("re", "cluster", 200),
        ("analyst", "cluster", 200),
        ("po", "cluster", 403),
        ("dev", "cluster", 403),
        ("po", "backlog", 200),
        ("dev", "backlog", 200),
        ("re", "backlog", 403),
        ("analyst", "backlog", 403),
    ],
)
def test_detail_page_access_matrix(
    client, users, rbac_data, user_key, page, expected
):
    if page == "story":
        url = reverse(
            "stories:detail",
            kwargs={"pk": rbac_data["story_review"].pk},
        )
    elif page == "cluster":
        url = reverse(
            "extraction:cluster_detail",
            kwargs={"pk": rbac_data["cluster_waiting"].pk},
        )
    else:
        url = reverse(
            "backlog:detail",
            kwargs={"pk": rbac_data["backlog_item"].pk},
        )

    client.force_login(users[user_key])
    assert client.get(url).status_code == expected


def test_non_requirements_engineer_cannot_change_roles(client, users):
    client.force_login(users["po"])
    response = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": users["dev"].pk}),
        {"role": User.RolePengguna.ANALYST},
    )

    assert response.status_code == 403
    users["dev"].refresh_from_db()
    assert users["dev"].role == User.RolePengguna.TIM_DEVELOPER


# ---------------------------------------------------------------------------
# Validasi Analyst dan monitoring RE
# ---------------------------------------------------------------------------


def test_analyst_validates_cluster_while_re_only_monitors(
    client, users, rbac_data
):
    cluster = rbac_data["cluster_waiting"]
    hasil = rbac_data["hasil_waiting"]

    # RE dapat memantau pipeline, cluster, dan komentar tanpa tombol validasi.
    client.force_login(users["re"])
    pipeline = client.get(reverse("extraction:pipeline"))
    assert pipeline.status_code == 200
    assert "Jalankan Ekstraksi" in pipeline.content.decode("utf-8")

    assert client.get(reverse("extraction:cluster_list")).status_code == 200
    detail = client.get(
        reverse("extraction:cluster_detail", kwargs={"pk": cluster.pk})
    )
    assert detail.status_code == 200
    detail_body = detail.content.decode("utf-8")
    assert "Mode monitoring" in detail_body
    assert "Setujui Cluster (Tervalidasi)" not in detail_body

    # RE tidak boleh masuk antrean validasi atau menjalankan aksi validasi.
    assert client.get(reverse("extraction:validasi_list")).status_code == 403
    assert (
        client.post(
            reverse(
                "extraction:setujui_cluster",
                kwargs={"pk": cluster.pk},
            )
        ).status_code
        == 403
    )
    cluster.refresh_from_db()
    assert cluster.status_cluster == Cluster.StatusCluster.MENUNGGU_VALIDASI

    # Analyst melihat antrean validasi dan dapat menyetujui cluster.
    client.force_login(users["analyst"])
    analyst_pipeline = client.get(reverse("extraction:pipeline"))
    assert analyst_pipeline.status_code == 200
    assert "Read-only" in analyst_pipeline.content.decode("utf-8")

    validasi = client.get(reverse("extraction:validasi_list"))
    assert validasi.status_code == 200
    validasi_body = validasi.content.decode("utf-8")
    assert cluster.nama_topik in validasi_body
    assert "Setujui Cluster (Tervalidasi)" in validasi_body

    response = client.post(
        reverse(
            "extraction:setujui_cluster",
            kwargs={"pk": cluster.pk},
        ),
        follow=True,
    )
    assert response.status_code == 200

    cluster.refresh_from_db()
    hasil.refresh_from_db()
    assert cluster.status_cluster == Cluster.StatusCluster.TERVALIDASI
    assert hasil.status_validasi == HasilEkstraksi.StatusValidasi.TERVALIDASI
    assert hasil.pengguna == users["analyst"]
    assert hasil.tanggal_validasi is not None


def test_only_re_can_run_extraction_pipeline(client, users):
    client.force_login(users["analyst"])
    assert client.post(reverse("extraction:run_pipeline")).status_code == 403

    client.force_login(users["re"])
    with patch("extraction.views.call_command") as call_command:
        response = client.post(reverse("extraction:run_pipeline"))

    assert response.status_code == 302
    assert response.url == reverse("extraction:pipeline")
    assert call_command.call_count == 2


# ---------------------------------------------------------------------------
# Persetujuan Product Owner
# ---------------------------------------------------------------------------


def test_po_approves_story_and_re_is_read_only(client, users, rbac_data):
    story = rbac_data["story_review"]
    cluster_url = reverse(
        "extraction:cluster_detail",
        kwargs={"pk": rbac_data["cluster_review"].pk},
    )

    # RE dapat membaca detail dan membuka cluster sumber, tetapi tidak menyetujui.
    client.force_login(users["re"])
    re_detail = client.get(
        reverse("stories:detail", kwargs={"pk": story.pk})
    )
    assert re_detail.status_code == 200
    re_body = re_detail.content.decode("utf-8")
    assert cluster_url in re_body
    assert "Setujui" not in re_body
    assert (
        client.post(
            reverse("stories:setujui", kwargs={"pk": story.pk})
        ).status_code
        == 403
    )

    # PO melihat board dan dapat menyetujui User Story.
    client.force_login(users["po"])
    board = client.get(reverse("stories:board"))
    assert board.status_code == 200
    assert story.kalimat in board.content.decode("utf-8")

    po_detail = client.get(
        reverse("stories:detail", kwargs={"pk": story.pk})
    )
    assert po_detail.status_code == 200
    po_body = po_detail.content.decode("utf-8")
    assert "Setujui" in po_body
    assert "Abaikan" in po_body
    assert cluster_url not in po_body

    response = client.post(
        reverse("stories:setujui", kwargs={"pk": story.pk})
    )
    assert response.status_code == 302
    assert response.url == reverse("backlog:list")

    story.refresh_from_db()
    assert (
        story.status_persetujuan
        == UserStory.StatusPersetujuan.DISETUJUI
    )
    assert BacklogItem.objects.filter(user_story=story).exists()


# ---------------------------------------------------------------------------
# Eksekusi Sprint Backlog
# ---------------------------------------------------------------------------


def test_developer_executes_backlog_while_po_cannot(client, users, rbac_data):
    item = rbac_data["backlog_item"]

    # PO hanya membaca status dan tombol eksekusi tidak ditampilkan/diizinkan.
    client.force_login(users["po"])
    po_list = client.get(reverse("backlog:list"))
    assert po_list.status_code == 200
    po_body = po_list.content.decode("utf-8")
    assert "Mode Product Owner" in po_body
    assert "Mulai Kerjakan" not in po_body
    assert (
        client.post(
            reverse("backlog:mulai", kwargs={"pk": item.pk})
        ).status_code
        == 403
    )
    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI

    # Developer dapat memulai lalu menyelesaikan item.
    client.force_login(users["dev"])
    dev_list = client.get(reverse("backlog:list"))
    assert dev_list.status_code == 200
    assert "Mulai Kerjakan" in dev_list.content.decode("utf-8")

    response = client.post(
        reverse("backlog:mulai", kwargs={"pk": item.pk})
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN
    assert item.pengguna == users["dev"]
    assert item.tanggal_mulai_dikerjakan is not None

    response = client.post(
        reverse("backlog:selesai", kwargs={"pk": item.pk})
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SELESAI
    assert item.tanggal_selesai is not None


# ---------------------------------------------------------------------------
# Simulasi peran staf
# ---------------------------------------------------------------------------


def test_staff_can_simulate_roles_without_changing_database_role(
    client, users, settings
):
    settings.DEBUG = True
    staff = users["staff_po"]
    client.force_login(staff)

    response = client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.REQUIREMENTS_ENGINEER},
    )
    assert response.status_code == 302
    assert response.url == reverse("extraction:pipeline")
    assert (
        client.session.get("acting_role")
        == User.RolePengguna.REQUIREMENTS_ENGINEER
    )

    staff.refresh_from_db()
    assert staff.role == User.RolePengguna.PRODUCT_OWNER

    pipeline = client.get(reverse("extraction:pipeline"))
    assert pipeline.status_code == 200
    pipeline_body = pipeline.content.decode("utf-8")
    assert "Mode simulasi" in pipeline_body
    assert "Peran asli: Product Owner" in pipeline_body

    # Staf tetap dapat membuka Kelola Role meski sedang menyimulasikan Analyst.
    response = client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.ANALYST},
    )
    assert response.status_code == 302
    assert response.url == reverse("extraction:validasi_list")
    assert client.get(reverse("accounts:kelola_role")).status_code == 200

    # Namun backend tetap menolak halaman khusus RE pada simulasi Analyst.
    assert client.get(reverse("stories:susun")).status_code == 403

    # Mengosongkan pilihan mengembalikan peran asli dan membersihkan simulasi.
    response = client.post(
        reverse("accounts:switch_role"), {"acting_role": ""}
    )
    assert response.status_code == 302
    assert response.url == reverse("stories:board")
    assert "acting_role" not in client.session

    staff.refresh_from_db()
    assert staff.role == User.RolePengguna.PRODUCT_OWNER


def test_non_staff_cannot_simulate_roles(client, users, settings):
    settings.DEBUG = True
    client.force_login(users["re"])
    response = client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.PRODUCT_OWNER},
    )

    assert response.status_code == 403
    assert "acting_role" not in client.session


def test_staff_cannot_simulate_when_debug_is_disabled(
    client, users, settings
):
    settings.DEBUG = False
    client.force_login(users["staff_po"])

    response = client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.REQUIREMENTS_ENGINEER},
    )

    assert response.status_code == 403
    assert "acting_role" not in client.session


def test_staff_simulating_developer_can_execute_backlog(
    client, users, rbac_data, settings
):
    settings.DEBUG = True
    staff = users["staff_po"]
    item = rbac_data["backlog_item"]
    client.force_login(staff)

    response = client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.TIM_DEVELOPER},
    )
    assert response.status_code == 302
    assert response.url == reverse("backlog:list")

    response = client.post(
        reverse("backlog:mulai", kwargs={"pk": item.pk})
    )
    assert response.status_code == 302

    item.refresh_from_db()
    assert item.status_eksekusi == BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN
    assert item.pengguna == staff

    staff.refresh_from_db()
    assert staff.role == User.RolePengguna.PRODUCT_OWNER


# ---------------------------------------------------------------------------
# Logout dan pendaftaran
# ---------------------------------------------------------------------------


def test_logout_requires_post_and_clears_simulation(client, users, settings):
    settings.DEBUG = True
    staff = users["staff_po"]
    client.force_login(staff)
    client.post(
        reverse("accounts:switch_role"),
        {"acting_role": User.RolePengguna.TIM_DEVELOPER},
    )
    assert "acting_role" in client.session

    # GET tidak boleh menghapus sesi.
    assert client.get(reverse("accounts:logout")).status_code == 403
    assert "acting_role" in client.session

    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")
    assert "_auth_user_id" not in client.session
    assert "acting_role" not in client.session

    protected = client.get(reverse("backlog:list"))
    assert protected.status_code == 302
    assert urlparse(protected.url).path == reverse("accounts:login")


def test_signup_cannot_choose_privileged_role_and_needs_activation(
    client, users
):
    username = "pendaftar_baru"
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": username,
            "email": "pendaftar@katawarga.test",
            "password1": PASSWORD,
            "password2": PASSWORD,
            # Upaya menaikkan hak akses harus diabaikan oleh form.
            "role": User.RolePengguna.REQUIREMENTS_ENGINEER,
            "is_staff": "on",
            "is_superuser": "on",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")

    new_user = User.objects.get(username=username)
    assert new_user.role == User.RolePengguna.TIM_DEVELOPER
    assert new_user.is_active is False
    assert new_user.is_staff is False
    assert new_user.is_superuser is False

    # Akun nonaktif belum dapat login.
    inactive_login = client.post(
        reverse("accounts:login"),
        {"username": username, "password": PASSWORD},
    )
    assert inactive_login.status_code == 200
    assert "_auth_user_id" not in client.session

    # RE mengaktifkan akun melalui Kelola Role.
    client.force_login(users["re"])
    activation = client.post(
        reverse(
            "accounts:toggle_active",
            kwargs={"pk": new_user.pk},
        ),
        follow=True,
    )
    assert activation.status_code == 200
    new_user.refresh_from_db()
    assert new_user.is_active is True

    # Setelah aktivasi, login diarahkan ke halaman utama Developer.
    client.logout()
    active_login = client.post(
        reverse("accounts:login"),
        {"username": username, "password": PASSWORD},
    )
    assert active_login.status_code == 302
    assert active_login.url == reverse("backlog:list")
