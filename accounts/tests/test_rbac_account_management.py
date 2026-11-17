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
import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
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
# 13. Audit Jalur Django Admin (Review #4)
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
    # Set admin2 inaktif agar admin_user menjadi superuser aktif terakhir
    admin2_user.is_active = False
    admin2_user.save(update_fields=["is_active"])
    assert User.objects.filter(is_superuser=True, is_active=True).count() == 1
    assert custom_admin.has_delete_permission(req_admin, obj=admin_user) is False

    # 4. save_model menolak jika non-superuser mencoba menyimpan superuser
    with pytest.raises(PermissionDenied, match="Hanya superuser"):
        custom_admin.save_model(req_staff, admin_user, None, change=True)

    # 5. delete_model menolak jika non-superuser mencoba menghapus superuser
    with pytest.raises(PermissionDenied, match="Hanya superuser"):
        custom_admin.delete_model(req_staff, admin_user)

    # 6. delete_model menolak penghapusan superuser aktif terakhir
    with pytest.raises(PermissionDenied, match="superuse"):
        custom_admin.delete_model(req_admin, admin_user)
