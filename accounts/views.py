"""Views autentikasi dan pengelolaan role KataWarga."""

from django import forms
from django.conf import settings
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.decorators import _get_acting_role
from accounts.models import User
from accounts.roles import role_home_url, role_label

User = get_user_model()


# FORM SIGN UP
class SignUpForm(UserCreationForm):
    """
    Pendaftaran mandiri tanpa pemilihan peran.

    Peran dan status aktif akun ditetapkan oleh Product Owner atau
    administrator melalui halaman Kelola Akses Role. Ini mencegah pengguna
    memberi dirinya sendiri peran istimewa (termasuk ``is_staff``).
    """

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Email sudah terdaftar. Silakan login."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        # Peran awal yang aman; akun tetap nonaktif sampai disetujui RE/admin.
        peran_awal = getattr(
            settings,
            "SIGNUP_DEFAULT_ROLE",
            User.RolePengguna.TIM_DEVELOPER,
        )
        valid_roles = [choice[0] for choice in User.RolePengguna.choices]
        user.role = peran_awal if peran_awal in valid_roles else User.RolePengguna.TIM_DEVELOPER
        user.is_active = False
        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()

        return user


def _safe_next_url(request, next_url):
    if not next_url:
        return None
    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


# LOGIN
def login_view(request):
    if request.user.is_authenticated:
        return redirect(role_home_url(_get_acting_role(request)))

    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request.session.pop("acting_role", None)

            messages.success(request, "Login berhasil!")
            target = _safe_next_url(request, next_url) or role_home_url(user.role)
            return redirect(target)
    else:
        form = AuthenticationForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": next_url},
    )


# SIGN UP
def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Akun berhasil dibuat. Akun menunggu aktivasi dan penetapan "
                "peran oleh Product Owner atau administrator.",
            )
            return redirect("accounts:login")
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form},
    )


# LOGOUT
@login_required
def logout_view(request):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Logout harus menggunakan metode POST."
        )

    request.session.pop("acting_role", None)
    logout(request)

    return redirect("accounts:login")


def _can_manage_roles(request):
    """
    Kebijakan administratif RBAC KataWarga:
    Hanya Superuser (is_superuser=True) atau Product Owner (role == PRODUCT_OWNER).
    Peran lain (Requirements Engineer, Analyst, Tim Developer) dilarang (HTTP 403).
    Kewenangan administratif harus berdasarkan role asli di database, bukan role simulasi.
    """
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.role == User.RolePengguna.PRODUCT_OWNER
        )
    )


# KELOLA ROLE
@login_required
def kelola_role_view(request):
    acting_role = _get_acting_role(request)

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Product Owner atau Superuser yang dapat mengelola peran."
        )

    users = User.objects.all().order_by("username")
    roles = User.RolePengguna.choices

    active_superusers_count = User.objects.filter(
        is_superuser=True, is_active=True
    ).count()

    return render(
        request,
        "accounts/kelola_role.html",
        {
            "users": users,
            "roles": roles,
            "acting_role": acting_role,
            "acting_role_label": role_label(acting_role),
            "is_superuser": request.user.is_superuser,
            "active_superusers_count": active_superusers_count,
        },
    )


# UBAH ROLE
@login_required
def ubah_role_view(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Metode tidak diizinkan. Gunakan metode POST."
        )

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Product Owner atau Superuser yang dapat mengubah peran."
        )

    with transaction.atomic():
        target_user = get_object_or_404(
            User.objects.select_for_update(), pk=pk
        )

        # 1. Pengguna dilarang mengubah perannya sendiri
        if target_user.pk == request.user.pk:
            return HttpResponseForbidden(
                "Anda tidak dapat mengubah peran akun sendiri."
            )

        # 2. Product Owner (dan non-superuser) dilarang mengubah akun superuser
        if target_user.is_superuser and not request.user.is_superuser:
            return HttpResponseForbidden(
                "Product Owner tidak memiliki izin untuk mengubah peran superuser."
            )

        new_role = request.POST.get("role", "").strip()
        valid_roles = [choice[0] for choice in User.RolePengguna.choices]

        if new_role not in valid_roles:
            messages.error(
                request,
                "Pilihan peran tidak valid."
            )
            return redirect("accounts:kelola_role")

        target_user.role = new_role
        target_user.save(update_fields=["role"])

    messages.success(
        request,
        f"Peran untuk pengguna '{target_user.username}' "
        f"berhasil diubah menjadi {target_user.get_role_display()}."
    )

    return redirect("accounts:kelola_role")


# AKTIVASI / NONAKTIFKAN AKUN
@login_required
def toggle_active_view(request, pk):
    """Aktifkan atau nonaktifkan akun."""
    if request.method != "POST":
        return HttpResponseForbidden(
            "Metode tidak diizinkan. Gunakan metode POST."
        )

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Product Owner atau Superuser yang dapat mengubah status akun."
        )

    with transaction.atomic():
        target_user = get_object_or_404(User, pk=pk)

        # 1. Product Owner (dan non-superuser) dilarang mengaktifkan/menonaktifkan superuser
        if target_user.is_superuser and not request.user.is_superuser:
            return HttpResponseForbidden(
                "Product Owner tidak memiliki izin untuk mengaktifkan atau menonaktifkan superuser."
            )

        # 2. Proteksi superuser aktif terakhir (mencegah lockout administratif & race condition)
        # Mengunci seluruh row superuser aktif dalam urutan id konsisten (order_by('id'))
        # dengan list evaluation nyata (bukan .count()) untuk benar-benar mengunci row di PostgreSQL.
        if target_user.is_superuser and target_user.is_active:
            active_superusers = list(
                User.objects.select_for_update()
                .filter(is_superuser=True, is_active=True)
                .order_by("id")
            )
            if len(active_superusers) <= 1:
                return HttpResponseForbidden(
                    "Tidak dapat menonaktifkan superuser aktif terakhir untuk mencegah lockout administratif."
                )
            for su in active_superusers:
                if su.pk == target_user.pk:
                    target_user = su
                    break
        else:
            target_user = get_object_or_404(
                User.objects.select_for_update(), pk=pk
            )

        # 3. Tidak boleh menonaktifkan akun sendiri
        if target_user.pk == request.user.pk:
            return HttpResponseForbidden(
                "Anda tidak dapat menonaktifkan akun sendiri."
            )

        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=["is_active"])

    status = "diaktifkan" if target_user.is_active else "dinonaktifkan"
    messages.success(
        request,
        f"Akun '{target_user.username}' berhasil {status}."
    )
    return redirect("accounts:kelola_role")



# SWITCH ROLE (KHUSUS DEVELOPMENT)
@login_required
def switch_acting_role_view(request):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Metode tidak diizinkan."
        )

    if not (settings.DEBUG and request.user.is_staff):
        return HttpResponseForbidden(
            "Simulasi role hanya tersedia untuk staf "
            "pada lingkungan development."
        )

    new_role = request.POST.get("acting_role", "").strip()
    valid_roles = [choice[0] for choice in User.RolePengguna.choices]

    if new_role in valid_roles:
        if new_role == request.user.role:
            request.session.pop("acting_role", None)
        else:
            request.session["acting_role"] = new_role

        effective_role = new_role
        messages.info(
            request,
            f"Peran efektif diubah menjadi: {role_label(new_role)}."
        )
    else:
        request.session.pop("acting_role", None)
        effective_role = request.user.role

        messages.info(
            request,
            "Simulasi peran dihentikan. Kembali ke peran asli: "
            f"{role_label(effective_role)}."
        )

    # Arahkan ke halaman utama peran baru agar halaman tujuan selalu sesuai
    # dengan sidebar dan izin backend yang berlaku.
    return redirect(role_home_url(effective_role))
