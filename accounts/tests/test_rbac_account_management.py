"""
Pengujian komprehensif RBAC Akun dan Proteksi Superuser (§4, P0 Security Fix).

Cakupan:
- Matriks akses halaman Kelola Role (Superuser, PO, RE, Analyst, Dev, Anonim);
- Operasi pengguna biasa oleh Product Owner (aktivasi, nonaktivasi, ubah peran);
- Manajemen antar Product Owner;
- Proteksi mutlak superuser terhadap modifikasi atau penonaktifan oleh non-superuser (P0 bug fix);
- Larangan modifikasi diri sendiri (anti self-deactivation & anti self-role tampering);
- Kemampuan administratif Superuser dan proteksi superuser aktif terakhir (anti-lockout)
  yang diverifikasi langsung tanpa bercampur aturan self-deactivation;
- Ketahanan terhadap manipulasi parameter (is_superuser, is_staff);
- Penolakan metode HTTP GET pada endpoint state-changing;
- Penanganan ID pengguna tidak ditemukan (404);
- Validasi tampilan UI (indikator proteksi dan penyembunyian kontrol aksi);
- Regresi khusus smoke test kw_smoke_test01 (dengan default role TIM_DEVELOPER);
- Penolakan staf non-PO yang mencoba menyimulasikan Product Owner pada mode DEBUG;
- Penegakan proteksi CSRF menggunakan enforce_csrf_checks=True;
- Audit dan proteksi jalur Django Admin (CustomUserAdmin).
"""
import threading
from unittest.mock import MagicMock
import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.test import Client, RequestFactory
from django.urls import reverse

from accounts.admin import CustomUserAdmin
from accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "TestSecurePassword123!"


def _create_user(username, role, is_superuser=False, is_staff=False, is_active=True):
    if is_superuser:
        return User.objects.create_superuser(
            username=username,
            email=f"{username}@katawarga.test",
            password=PASSWORD,
            role=role,
            is_active=is_active,
        )
    return User.objects.create_user(
        username=username,
        email=f"{username}@katawarga.test",
        password=PASSWORD,
        role=role,
        is_staff=is_staff,
        is_active=is_active,
    )


@pytest.fixture
def rbac_users():
    return {
        "admin": _create_user("admin_root", User.RolePengguna.PRODUCT_OWNER, is_superuser=True, is_staff=True),
        "admin2": _create_user("admin_second", User.RolePengguna.REQUIREMENTS_ENGINEER, is_superuser=True, is_staff=True),
        "po": _create_user("po_lead", User.RolePengguna.PRODUCT_OWNER),
        "po2": _create_user("po_second", User.RolePengguna.PRODUCT_OWNER),
        "re": _create_user("re_analyst", User.RolePengguna.REQUIREMENTS_ENGINEER),
        "analyst": _create_user("analyst_qa", User.RolePengguna.ANALYST),
        "dev": _create_user("dev_engineer", User.RolePengguna.TIM_DEVELOPER),
        "target_ordinary": _create_user("target_other_user", User.RolePengguna.TIM_DEVELOPER),
        "smoke": _create_user("kw_smoke_test01", User.RolePengguna.TIM_DEVELOPER),
        "smoke_re": _create_user("kw_smoke_test02", User.RolePengguna.REQUIREMENTS_ENGINEER),
        "staff_re": _create_user("staff_non_po", User.RolePengguna.REQUIREMENTS_ENGINEER, is_staff=True),
    }


# ===========================================================================
# 1. Matriks Akses Halaman Kelola Role
# ===========================================================================

@pytest.mark.parametrize(
    "role_key,expected_status",
    [
        ("admin", 200),
        ("po", 200),
        ("re", 403),
        ("analyst", 403),
        ("dev", 403),
        ("smoke", 403),
        ("smoke_re", 403),
    ],
)
def test_access_kelola_role_matrix(client, rbac_users, role_key, expected_status):
    """Hanya Superuser dan Product Owner yang dapat mengakses halaman kelola role."""
    client.force_login(rbac_users[role_key])
    response = client.get(reverse("accounts:kelola_role"))
    assert response.status_code == expected_status


def test_anonymous_redirected_from_kelola_role(client):
    """Pengguna anonim dialihkan ke halaman login saat membuka /kelola-role/."""
    url = reverse("accounts:kelola_role")
    response = client.get(url)
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


# ===========================================================================
# 2. Penolakan Peran Non-Pengelola (RE, Analyst, Dev) pada POST
# ===========================================================================

@pytest.mark.parametrize("role_key", ["re", "analyst", "dev", "smoke", "smoke_re"])
def test_unauthorized_roles_forbidden_from_toggle_active(client, rbac_users, role_key):
    """
    Peran lain dilarang menonaktifkan akun pengguna lain (HTTP 403).
    Target adalah akun pihak ketiga (bukan akun aktor) untuk membuktikan penolakan
    terjadi murni karena hak akses RBAC, bukan karena aturan larangan mengubah akun sendiri.
    """
    target = rbac_users["target_ordinary"]
    actor = rbac_users[role_key]
    assert actor.pk != target.pk

    client.force_login(actor)

    response = client.post(reverse("accounts:toggle_active", kwargs={"pk": target.pk}))
    assert response.status_code == 403

    target.refresh_from_db()
    assert target.is_active is True


@pytest.mark.parametrize("role_key", ["re", "analyst", "dev", "smoke", "smoke_re"])
def test_unauthorized_roles_forbidden_from_ubah_role(client, rbac_users, role_key):
    """
    Peran lain dilarang mengubah peran pengguna lain (HTTP 403).
    Target adalah akun pihak ketiga (bukan akun aktor).
    """
    target = rbac_users["target_ordinary"]
    actor = rbac_users[role_key]
    assert actor.pk != target.pk

    client.force_login(actor)

    response = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": target.pk}),
        {"role": User.RolePengguna.ANALYST},
    )
    assert response.status_code == 403

    target.refresh_from_db()
    assert target.role == User.RolePengguna.TIM_DEVELOPER


# ===========================================================================
# 3. Product Owner Mengelola Pengguna Biasa dan Product Owner Lain
# ===========================================================================

def test_po_can_activate_and_deactivate_ordinary_user(client, rbac_users):
    """PO berwenang menonaktifkan dan mengaktifkan akun pengguna biasa."""
    target = rbac_users["dev"]
    client.force_login(rbac_users["po"])

    # Nonaktifkan
    resp1 = client.post(reverse("accounts:toggle_active", kwargs={"pk": target.pk}), follow=True)
    assert resp1.status_code == 200
    target.refresh_from_db()
    assert target.is_active is False

    # Aktifkan kembali
    resp2 = client.post(reverse("accounts:toggle_active", kwargs={"pk": target.pk}), follow=True)
    assert resp2.status_code == 200
    target.refresh_from_db()
    assert target.is_active is True


def test_po_can_change_ordinary_user_role(client, rbac_users):
    """PO berwenang mengubah peran pengguna biasa."""
    target = rbac_users["dev"]
    client.force_login(rbac_users["po"])

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": target.pk}),
        {"role": User.RolePengguna.ANALYST},
        follow=True,
    )
    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.role == User.RolePengguna.ANALYST


def test_po_can_manage_other_product_owner(client, rbac_users):
    """PO berwenang mengelola akun Product Owner lain (bukan akunnya sendiri)."""
    target_po = rbac_users["po2"]
    client.force_login(rbac_users["po"])

    # Nonaktifkan PO lain
    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": target_po.pk}), follow=True)
    assert resp.status_code == 200
    target_po.refresh_from_db()
    assert target_po.is_active is False

    # Ubah peran PO lain
    resp2 = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": target_po.pk}),
        {"role": User.RolePengguna.TIM_DEVELOPER},
        follow=True,
    )
    assert resp2.status_code == 200
    target_po.refresh_from_db()
    assert target_po.role == User.RolePengguna.TIM_DEVELOPER


# ===========================================================================
# 4. Proteksi Mutlak Superuser terhadap Product Owner (P0 Fix)
# ===========================================================================

def test_po_cannot_deactivate_superuser(client, rbac_users):
    """Product Owner DILARANG menonaktifkan superuser (HTTP 403)."""
    superuser = rbac_users["admin"]
    client.force_login(rbac_users["po"])

    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": superuser.pk}))
    assert resp.status_code == 403

    superuser.refresh_from_db()
    assert superuser.is_active is True


def test_po_cannot_activate_inactive_superuser(client, rbac_users):
    """Product Owner DILARANG mengaktifkan superuser (HTTP 403)."""
    superuser = rbac_users["admin2"]
    superuser.is_active = False
    superuser.save(update_fields=["is_active"])

    client.force_login(rbac_users["po"])
    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": superuser.pk}))
    assert resp.status_code == 403

    superuser.refresh_from_db()
    assert superuser.is_active is False


def test_po_cannot_change_superuser_role(client, rbac_users):
    """Product Owner DILARANG mengubah peran akun superuser (HTTP 403)."""
    superuser = rbac_users["admin"]
    original_role = superuser.role
    client.force_login(rbac_users["po"])

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": superuser.pk}),
        {"role": User.RolePengguna.TIM_DEVELOPER},
    )
    assert resp.status_code == 403

    superuser.refresh_from_db()
    assert superuser.role == original_role


# ===========================================================================
# 5. Anti-Self-Tampering (Pengguna Tidak Boleh Mengubah Akun Sendiri)
# ===========================================================================

def test_po_cannot_deactivate_themselves(client, rbac_users):
    """Product Owner DILARANG menonaktifkan akun sendiri (HTTP 403)."""
    po = rbac_users["po"]
    client.force_login(po)

    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": po.pk}))
    assert resp.status_code == 403

    po.refresh_from_db()
    assert po.is_active is True


def test_po_cannot_change_their_own_role(client, rbac_users):
    """Product Owner DILARANG mengubah peran akun sendiri (HTTP 403)."""
    po = rbac_users["po"]
    client.force_login(po)

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": po.pk}),
        {"role": User.RolePengguna.REQUIREMENTS_ENGINEER},
    )
    assert resp.status_code == 403

    po.refresh_from_db()
    assert po.role == User.RolePengguna.PRODUCT_OWNER


def test_superuser_cannot_change_own_role_via_kelola_role(client, rbac_users):
    """Superuser dilarang mengubah peran diri sendiri melalui endpoint kelola role."""
    admin = rbac_users["admin"]
    client.force_login(admin)

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": admin.pk}),
        {"role": User.RolePengguna.TIM_DEVELOPER},
    )
    assert resp.status_code == 403

    admin.refresh_from_db()
    assert admin.role == User.RolePengguna.PRODUCT_OWNER


# ===========================================================================
# 6. Kewenangan Superuser & Proteksi Superuser Aktif Terakhir (Anti-Lockout)
# ===========================================================================

def test_superuser_can_manage_ordinary_users(client, rbac_users):
    """Superuser dapat mengaktifkan/menonaktifkan dan mengubah peran pengguna biasa."""
    admin = rbac_users["admin"]
    dev = rbac_users["dev"]
    client.force_login(admin)

    # Ubah status
    resp1 = client.post(reverse("accounts:toggle_active", kwargs={"pk": dev.pk}), follow=True)
    assert resp1.status_code == 200
    dev.refresh_from_db()
    assert dev.is_active is False

    # Ubah peran
    resp2 = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": dev.pk}),
        {"role": User.RolePengguna.ANALYST},
        follow=True,
    )
    assert resp2.status_code == 200
    dev.refresh_from_db()
    assert dev.role == User.RolePengguna.ANALYST


def test_superuser_can_deactivate_another_superuser_if_multiple_exist(client, rbac_users):
    """Superuser dapat menonaktifkan superuser lain jika masih ada superuser aktif lain."""
    admin = rbac_users["admin"]
    admin2 = rbac_users["admin2"]
    client.force_login(admin)

    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": admin2.pk}), follow=True)
    assert resp.status_code == 200

    admin2.refresh_from_db()
    assert admin2.is_active is False


def test_last_active_superuser_cannot_be_deactivated(client, rbac_users):
    """
    Superuser aktif terakhir tidak dapat dinonaktifkan (anti-lockout).
    Guard proteksi anti-lockout dievaluasi sebelum aturan self-deactivation,
    sehingga penolakan terjadi secara spesifik karena mencegah hilangnya superuser aktif terakhir.
    """
    admin1 = rbac_users["admin"]
    admin2 = rbac_users["admin2"]

    # Pastikan admin2 inaktif sehingga admin1 adalah satu-satunya superuser aktif di database
    admin2.is_active = False
    admin2.save(update_fields=["is_active"])
    admin1.is_active = True
    admin1.save(update_fields=["is_active"])

    assert User.objects.filter(is_superuser=True, is_active=True).count() == 1

    client.force_login(admin1)
    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": admin1.pk}))

    assert resp.status_code == 403
    assert "superuser aktif terakhir" in resp.content.decode("utf-8")

    admin1.refresh_from_db()
    assert admin1.is_active is True


def test_superuser_cannot_deactivate_themselves_when_multiple_exist(client, rbac_users):
    """
    Ketika ada beberapa superuser aktif, superuser tetap dilarang menonaktifkan akunnya sendiri
    berdasarkan aturan self-deactivation.
    """
    admin1 = rbac_users["admin"]
    admin2 = rbac_users["admin2"]

    admin1.is_active = True
    admin1.save(update_fields=["is_active"])
    admin2.is_active = True
    admin2.save(update_fields=["is_active"])

    assert User.objects.filter(is_superuser=True, is_active=True).count() >= 2

    client.force_login(admin1)
    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": admin1.pk}))

    assert resp.status_code == 403
    assert "tidak dapat menonaktifkan akun sendiri" in resp.content.decode("utf-8")

    admin1.refresh_from_db()
    assert admin1.is_active is True


# ===========================================================================
# 7. Pencegahan Manipulasi Parameter & Validasi Peran
# ===========================================================================

def test_parameter_tampering_cannot_grant_superuser_or_staff(client, rbac_users):
    """
    Manipulasi parameter POST (is_superuser, is_staff) tidak berpengaruh ke target.
    Key diuji tanpa duplikasi key dalam dictionary.
    """
    dev = rbac_users["dev"]
    client.force_login(rbac_users["po"])

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": dev.pk}),
        {
            "role": User.RolePengguna.PRODUCT_OWNER,
            "is_superuser": "True",
            "is_staff": "True",
        },
        follow=True,
    )
    assert resp.status_code == 200

    dev.refresh_from_db()
    assert dev.role == User.RolePengguna.PRODUCT_OWNER
    assert dev.is_superuser is False
    assert dev.is_staff is False


def test_invalid_role_choice_rejected(client, rbac_users):
    """Pilihan peran yang tidak valid ditolak dan tidak mengubah peran di database."""
    dev = rbac_users["dev"]
    original_role = dev.role
    client.force_login(rbac_users["po"])

    resp = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": dev.pk}),
        {"role": "SUPER_ADMIN"},
        follow=True,
    )
    assert resp.status_code == 200

    dev.refresh_from_db()
    assert dev.role == original_role


# ===========================================================================
# 8. Penegakan Metode HTTP & ID Tidak Ditemukan
# ===========================================================================

def test_get_method_rejected_for_state_changing_views(client, rbac_users):
    """GET request pada endpoint state-changing ditolak dengan 403 Forbidden."""
    dev = rbac_users["dev"]
    client.force_login(rbac_users["po"])

    resp_toggle = client.get(reverse("accounts:toggle_active", kwargs={"pk": dev.pk}))
    assert resp_toggle.status_code == 403

    resp_ubah = client.get(reverse("accounts:ubah_role", kwargs={"pk": dev.pk}))
    assert resp_ubah.status_code == 403


def test_nonexistent_user_returns_404(client, rbac_users):
    """Target user ID yang tidak terdaftar menghasilkan HTTP 404."""
    client.force_login(rbac_users["po"])
    non_existent_pk = 999999

    resp_toggle = client.post(reverse("accounts:toggle_active", kwargs={"pk": non_existent_pk}))
    assert resp_toggle.status_code == 404

    resp_ubah = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": non_existent_pk}),
        {"role": User.RolePengguna.ANALYST},
    )
    assert resp_ubah.status_code == 404


# ===========================================================================
# 9. Verifikasi Elemen Tampilan UI (Frontend Protection)
# ===========================================================================

def test_ui_protection_for_po_viewer(client, rbac_users):
    """Ketika PO melihat halaman kelola role, superuser dilindungi dan tombol dinonaktifkan."""
    admin = rbac_users["admin"]
    po = rbac_users["po"]
    dev = rbac_users["dev"]
    client.force_login(po)

    resp = client.get(reverse("accounts:kelola_role"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # 1. Badge Superuser (Dilindungi) tampil pada akun admin
    assert "Superuser (Dilindungi)" in html

    # 2. Form toggle dan ubah role untuk superuser TIDAK muncul
    toggle_admin_action = reverse("accounts:toggle_active", kwargs={"pk": admin.pk})
    ubah_admin_action = reverse("accounts:ubah_role", kwargs={"pk": admin.pk})
    assert f'action="{toggle_admin_action}"' not in html
    assert f'action="{ubah_admin_action}"' not in html

    # 3. Baris akun PO sendiri tidak memiliki tombol ubah peran
    toggle_po_action = reverse("accounts:toggle_active", kwargs={"pk": po.pk})
    ubah_po_action = reverse("accounts:ubah_role", kwargs={"pk": po.pk})
    assert f'action="{toggle_po_action}"' not in html
    assert f'action="{ubah_po_action}"' not in html
    assert "Akun Anda" in html
    assert "Tidak dapat mengubah peran sendiri" in html

    # 4. Form untuk dev tetap tampil normal
    toggle_dev_action = reverse("accounts:toggle_active", kwargs={"pk": dev.pk})
    ubah_dev_action = reverse("accounts:ubah_role", kwargs={"pk": dev.pk})
    assert f'action="{toggle_dev_action}"' in html
    assert f'action="{ubah_dev_action}"' in html


# ===========================================================================
# 10. Regresi Khusus Smoke Test: kw_smoke_test01
# ===========================================================================

def test_kw_smoke_test01_cannot_deactivate_superuser(client, rbac_users):
    """
    Skenario eksplisit Sprint 3 Smoke Test:
    Akun reguler kw_smoke_test01 (dengan role default TIM_DEVELOPER)
    mencoba menonaktifkan superuser admin.
    Harus ditolak (403 Forbidden) dan status superuser tidak berubah!
    """
    smoke_user = rbac_users["smoke"]
    assert smoke_user.role == User.RolePengguna.TIM_DEVELOPER
    admin_user = rbac_users["admin"]

    client.force_login(smoke_user)
    resp = client.post(reverse("accounts:toggle_active", kwargs={"pk": admin_user.pk}))

    assert resp.status_code == 403
    admin_user.refresh_from_db()
    assert admin_user.is_active is True


# ===========================================================================
# 11. Staf Non-PO Tidak Dapat Menembus RBAC via Simulasi Role (Review #1 & #3)
# ===========================================================================

def test_staff_non_po_simulating_po_cannot_manage_accounts(client, rbac_users, settings):
    """
    Staf yang memiliki peran asli non-PO (misal: REQUIREMENTS_ENGINEER) pada mode DEBUG
    tidak dapat memperoleh hak kelola role meskipun menyimulasikan PRODUCT_OWNER.
    Kewenangan administratif wajib mengacu pada role database asli!
    """
    settings.DEBUG = True
    staff_user = rbac_users["staff_re"]
    assert staff_user.role == User.RolePengguna.REQUIREMENTS_ENGINEER
    assert staff_user.is_staff is True

    target = rbac_users["target_ordinary"]

    client.force_login(staff_user)

    # Set simulasi role PRODUCT_OWNER di session
    session = client.session
    session["acting_role"] = User.RolePengguna.PRODUCT_OWNER
    session.save()

    # 1. Halaman kelola role ditolak (403 Forbidden)
    resp_get = client.get(reverse("accounts:kelola_role"))
    assert resp_get.status_code == 403

    # 2. Aksi toggle_active ditolak (403 Forbidden)
    resp_toggle = client.post(reverse("accounts:toggle_active", kwargs={"pk": target.pk}))
    assert resp_toggle.status_code == 403
    target.refresh_from_db()
    assert target.is_active is True

    # 3. Aksi ubah_role ditolak (403 Forbidden)
    resp_ubah = client.post(
        reverse("accounts:ubah_role", kwargs={"pk": target.pk}),
        {"role": User.RolePengguna.ANALYST},
    )
    assert resp_ubah.status_code == 403
    target.refresh_from_db()
    assert target.role == User.RolePengguna.TIM_DEVELOPER

    # 4. Context processor overview memastikan can_manage_roles bernilai False dan menu roles tidak ada
    overview_resp = client.get(reverse("dashboard:overview"))
    assert overview_resp.status_code == 200
    assert overview_resp.context["can_manage_roles"] is False
    sidebar_keys = [item["key"] for item in overview_resp.context["sidebar_items"]]
    assert "roles" not in sidebar_keys


# ===========================================================================
# 12. Pengujian Penegakan CSRF (Review #3)
# ===========================================================================

def test_csrf_protection_on_account_management_endpoints(rbac_users):
    """
    Memverifikasi penegakan proteksi CSRF pada endpoint kelola role menggunakan
    Client(enforce_csrf_checks=True).
    Permintaan POST tanpa token CSRF wajib ditolak dengan HTTP 403.
    """
    csrf_client = Client(enforce_csrf_checks=True)
    po = rbac_users["po"]
    target = rbac_users["target_ordinary"]

    csrf_client.force_login(po)

    # POST tanpa token CSRF -> Ditolak (403 CSRF Failed)
    resp_no_csrf_toggle = csrf_client.post(reverse("accounts:toggle_active", kwargs={"pk": target.pk}))
    assert resp_no_csrf_toggle.status_code == 403

    resp_no_csrf_ubah = csrf_client.post(
        reverse("accounts:ubah_role", kwargs={"pk": target.pk}),
        {"role": User.RolePengguna.ANALYST},
    )
    assert resp_no_csrf_ubah.status_code == 403

    # Dapatkan token CSRF dari cookie setelah GET
    get_resp = csrf_client.get(reverse("accounts:kelola_role"))
    assert get_resp.status_code == 200
    csrf_token = csrf_client.cookies["csrftoken"].value

    # POST dengan token CSRF yang valid -> Berhasil (302 Redirect)
    resp_with_csrf = csrf_client.post(
        reverse("accounts:toggle_active", kwargs={"pk": target.pk}),
        {"csrfmiddlewaretoken": csrf_token},
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp_with_csrf.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


# ===========================================================================
# 13. Audit Jalur Django Admin & Concurrency (Review #4)
# ===========================================================================

def test_django_admin_superuser_protection(rbac_users):
    """
    Memverifikasi bahwa CustomUserAdmin melindungi akun superuser dari:
    - Modifikasi oleh staf non-superuser;
    - Penghapusan oleh staf non-superuser;
    - Penghapusan atau penonaktifan superuser aktif terakhir oleh siapapun.
    """
    admin_site = AdminSite()
    custom_admin = CustomUserAdmin(User, admin_site)
    rf = RequestFactory()

    admin_user = rbac_users["admin"]
    admin2_user = rbac_users["admin2"]
    staff_user = rbac_users["staff_re"]  # non-superuser dengan is_staff=True

    # 1. Non-superuser dilarang memiliki has_change_permission untuk superuser
    req_staff = rf.get("/admin/accounts/user/")
    req_staff.user = staff_user
    assert custom_admin.has_change_permission(req_staff, obj=admin_user) is False

    # Superuser memiliki has_change_permission untuk superuser lain
    req_admin = rf.get("/admin/accounts/user/")
    req_admin.user = admin_user
    assert custom_admin.has_change_permission(req_admin, obj=admin2_user) is True

    # 2. Non-superuser dilarang memiliki has_delete_permission untuk superuser
    assert custom_admin.has_delete_permission(req_staff, obj=admin_user) is False

    # 3. Superuser tidak boleh menghapus superuser aktif terakhir
    admin2_user.is_active = False
    admin2_user.save(update_fields=["is_active"])
    assert User.objects.filter(is_superuser=True, is_active=True).count() == 1
    assert custom_admin.has_delete_permission(req_admin, obj=admin_user) is False

    # 4. save_model menolak jika non-superuser mencoba menyimpan superuser
    with pytest.raises(PermissionDenied, match="Product Owner|Hanya superuser"):
        custom_admin.save_model(req_staff, admin_user, None, change=True)

    # 5. delete_model menolak jika non-superuser mencoba menghapus superuser
    with pytest.raises(PermissionDenied, match="Product Owner|Hanya superuser"):
        custom_admin.delete_model(req_staff, admin_user)

    # 6. delete_model menolak penghapusan superuser aktif terakhir
    with pytest.raises(PermissionDenied, match="superuser aktif terakhir"):
        custom_admin.delete_model(req_admin, admin_user)


def test_django_admin_non_po_staff_forbidden_from_managing_users(client, rbac_users):
    """
    Memverifikasi staf biasa non-PO (misal RE, Analyst, Dev dengan is_staff=True)
    dilarang keras mengelola User di Django Admin:
    - has_module_permission -> False
    - has_view_permission -> False
    - has_add_permission -> False
    - has_change_permission -> False
    - has_delete_permission -> False
    - get_actions -> {}
    - save_model / delete_model / delete_queryset -> PermissionDenied
    - GET /admin/accounts/user/ -> 403 Forbidden
    """
    admin_site = AdminSite()
    custom_admin = CustomUserAdmin(User, admin_site)
    rf = RequestFactory()

    staff_user = rbac_users["staff_re"]  # is_staff=True, role=REQUIREMENTS_ENGINEER
    target_user = rbac_users["target_ordinary"]

    req_staff = rf.get("/admin/accounts/user/")
    req_staff.user = staff_user

    assert custom_admin.has_module_permission(req_staff) is False
    assert custom_admin.has_view_permission(req_staff) is False
    assert custom_admin.has_add_permission(req_staff) is False
    assert custom_admin.has_change_permission(req_staff, obj=target_user) is False
    assert custom_admin.has_delete_permission(req_staff, obj=target_user) is False
    assert custom_admin.get_actions(req_staff) == {}

    with pytest.raises(PermissionDenied, match="Hanya superuser dan Product Owner"):
        custom_admin.save_model(req_staff, target_user, None, change=True)

    with pytest.raises(PermissionDenied, match="Hanya superuser dan Product Owner"):
        custom_admin.delete_model(req_staff, target_user)

    with pytest.raises(PermissionDenied, match="Hanya superuser dan Product Owner"):
        custom_admin.delete_queryset(req_staff, User.objects.filter(pk=target_user.pk))

    client.force_login(staff_user)
    resp = client.get("/admin/accounts/user/")
    assert resp.status_code == 403


def test_django_admin_product_owner_privilege_escalation_prevented(rbac_users):
    """
    Memverifikasi Product Owner di Django Admin tidak dapat:
    - Memberikan hak is_staff atau is_superuser (escalation);
    - Memberikan grup (groups) atau user_permissions;
    - Memodifikasi akun superuser;
    - Memodifikasi peran (role) akun sendiri;
    - Menonaktifkan akun sendiri.
    """
    admin_site = AdminSite()
    custom_admin = CustomUserAdmin(User, admin_site)
    rf = RequestFactory()

    po_staff = _create_user("po_staff_admin", User.RolePengguna.PRODUCT_OWNER, is_staff=True)
    admin_user = rbac_users["admin"]
    target_user = rbac_users["target_ordinary"]

    req_po = rf.get("/admin/accounts/user/")
    req_po.user = po_staff

    # 1. PO berhak mengakses module User, view, dan add
    assert custom_admin.has_module_permission(req_po) is True
    assert custom_admin.has_view_permission(req_po) is True
    assert custom_admin.has_add_permission(req_po) is True

    # 2. PO tidak berhak change atau delete superuser
    assert custom_admin.has_change_permission(req_po, obj=admin_user) is False
    assert custom_admin.has_delete_permission(req_po, obj=admin_user) is False

    # 3. PO tidak boleh delete akun sendiri
    assert custom_admin.has_delete_permission(req_po, obj=po_staff) is False

    # 4. Readonly fields mengunci flag privilege dan role sendiri
    readonly = custom_admin.get_readonly_fields(req_po, obj=po_staff)
    assert "is_superuser" in readonly
    assert "is_staff" in readonly
    assert "groups" in readonly
    assert "user_permissions" in readonly
    assert "role" in readonly
    assert "is_active" in readonly

    # 5. PO mencoba memberikan is_staff=True -> Ditolak PermissionDenied
    new_staff_attempt = User(username="newbie_staff", role=User.RolePengguna.TIM_DEVELOPER, is_staff=True)
    with pytest.raises(PermissionDenied, match="Product Owner tidak boleh memberikan hak staf atau superuser"):
        custom_admin.save_model(req_po, new_staff_attempt, None, change=False)

    # 6. PO mencoba memberikan is_superuser=True -> Ditolak PermissionDenied
    new_su_attempt = User(username="newbie_su", role=User.RolePengguna.TIM_DEVELOPER, is_superuser=True)
    with pytest.raises(PermissionDenied, match="Product Owner tidak boleh memberikan hak staf atau superuser"):
        custom_admin.save_model(req_po, new_su_attempt, None, change=False)

    # 7. PO mencoba memberikan groups/user_permissions via save_related -> Ditolak PermissionDenied
    form_groups = MagicMock(cleaned_data={"groups": [1]})
    with pytest.raises(PermissionDenied, match="Product Owner tidak boleh memberikan grup atau permissions"):
        custom_admin.save_related(req_po, form_groups, None, change=False)

    form_perms = MagicMock(cleaned_data={"user_permissions": [1]})
    with pytest.raises(PermissionDenied, match="Product Owner tidak boleh memberikan grup atau permissions"):
        custom_admin.save_related(req_po, form_perms, None, change=False)

    # 8. PO mencoba memodifikasi superuser -> Ditolak PermissionDenied
    with pytest.raises(PermissionDenied, match="Product Owner tidak dapat memodifikasi akun superuser"):
        custom_admin.save_model(req_po, admin_user, None, change=True)

    # 9. PO mencoba mengubah role akun sendiri -> Ditolak PermissionDenied
    po_staff_copy = User.objects.get(pk=po_staff.pk)
    po_staff_copy.role = User.RolePengguna.REQUIREMENTS_ENGINEER
    with pytest.raises(PermissionDenied, match="Product Owner tidak dapat mengubah peran akun sendiri"):
        custom_admin.save_model(req_po, po_staff_copy, None, change=True)

    # 10. PO mencoba menonaktifkan akun sendiri -> Ditolak PermissionDenied
    po_staff_active_copy = User.objects.get(pk=po_staff.pk)
    po_staff_active_copy.is_active = False
    with pytest.raises(PermissionDenied, match="tidak dapat menonaktifkan akun"):
        custom_admin.save_model(req_po, po_staff_active_copy, None, change=True)


def test_django_admin_bulk_actions_anti_lockout(rbac_users):
    """
    Memverifikasi delete_queryset mempertahankan invariant minimal satu superuser aktif:
    - Penghapusan bulk yang mencakup semua superuser aktif wajib ditolak (PermissionDenied);
    - Penghapusan yang mencakup akun sendiri wajib ditolak (PermissionDenied);
    - Penghapusan superuser oleh non-superuser wajib ditolak (PermissionDenied).
    """
    admin_site = AdminSite()
    custom_admin = CustomUserAdmin(User, admin_site)
    rf = RequestFactory()

    admin_user = rbac_users["admin"]
    admin2_user = rbac_users["admin2"]
    po_user = rbac_users["po"]

    admin_user.is_active = True
    admin_user.save()
    admin2_user.is_active = True
    admin2_user.save()

    req_admin = rf.get("/admin/accounts/user/")
    req_admin.user = admin_user

    req_po = rf.get("/admin/accounts/user/")
    req_po.user = po_user

    # 1. Non-superuser dilarang menghapus superuser lewat bulk action
    with pytest.raises(PermissionDenied, match="Hanya superuser yang dapat menghapus akun superuser"):
        custom_admin.delete_queryset(req_po, User.objects.filter(pk=admin2_user.pk))

    # 2. Superuser dilarang menghapus akun sendiri lewat bulk action
    with pytest.raises(PermissionDenied, match="tidak dapat menghapus akun sendiri"):
        custom_admin.delete_queryset(req_admin, User.objects.filter(pk=admin_user.pk))

    # 3. Superuser dilarang menghapus SEMUA superuser aktif sekaligus (anti-lockout)
    with pytest.raises(PermissionDenied, match="menghapus semua superuser aktif"):
        custom_admin.delete_queryset(req_admin, User.objects.filter(is_superuser=True))


@pytest.mark.django_db(transaction=True)
def test_concurrent_superuser_status_toggle_anti_lockout(rbac_users):
    """
    Pengujian konkurensi PostgreSQL / Multi-threading:
    Dua transaksi superuser mencoba menonaktifkan satu sama lain secara bersamaan.
    Mekanisme select_for_update().order_by('id') dengan evaluasi list() nyata
    menjamin locking konsisten tanpa deadlock, dan invariant minimal satu superuser aktif
    selalu terjaga (anti-lockout).
    """
    admin1 = rbac_users["admin"]
    admin2 = rbac_users["admin2"]

    admin1.is_active = True
    admin1.save()
    admin2.is_active = True
    admin2.save()

    assert User.objects.filter(is_superuser=True, is_active=True).count() == 2

    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(actor_pk, target_pk, index):
        connections.close_all()
        try:
            barrier.wait(timeout=5)
            actor = User.objects.get(pk=actor_pk)
            c = Client()
            c.force_login(actor)
            resp = c.post(reverse("accounts:toggle_active", kwargs={"pk": target_pk}))
            results[index] = resp.status_code
        except Exception as exc:
            results[index] = exc
        finally:
            connections.close_all()

    t1 = threading.Thread(target=worker, args=(admin1.pk, admin2.pk, 0))
    t2 = threading.Thread(target=worker, args=(admin2.pk, admin1.pk, 1))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Invariant mutlak: minimal 1 superuser aktif harus selalu tersisa di database
    active_superusers = User.objects.filter(is_superuser=True, is_active=True)
    assert active_superusers.count() >= 1, (
        f"KRITIS: Lockout terjadi! Superuser aktif = {active_superusers.count()}"
    )

    # Setidaknya satu thread berhasil atau aman terserialisasi
    valid_statuses = [r for r in results if isinstance(r, int)]
    assert len(valid_statuses) >= 1
