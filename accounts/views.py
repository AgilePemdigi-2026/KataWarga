"""Views autentikasi dan pengelolaan role KataWarga."""

from django import forms
from django.conf import settings
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

    Peran dan status aktif akun ditetapkan oleh Requirements Engineer atau
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
                "peran oleh Requirements Engineer atau administrator.",
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
    """Kebijakan administratif: Requirements Engineer atau staf/admin."""
    acting_role = _get_acting_role(request)
    return bool(
        acting_role == User.RolePengguna.REQUIREMENTS_ENGINEER
        or request.user.is_staff
    )


# KELOLA ROLE
@login_required
def kelola_role_view(request):
    acting_role = _get_acting_role(request)

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Requirements Engineer atau Administrator "
            "yang dapat mengelola peran."
        )

    users = User.objects.all().order_by("username")
    roles = User.RolePengguna.choices

    return render(
        request,
        "accounts/kelola_role.html",
        {
            "users": users,
            "roles": roles,
            "acting_role": acting_role,
            "acting_role_label": role_label(acting_role),
        },
    )


# UBAH ROLE
@login_required
def ubah_role_view(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Metode tidak diizinkan."
        )

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Requirements Engineer atau Administrator "
            "yang dapat mengubah peran."
        )

    target_user = get_object_or_404(User, pk=pk)

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
    """Aktifkan atau nonaktifkan akun hasil pendaftaran mandiri."""
    if request.method != "POST":
        return HttpResponseForbidden("Metode tidak diizinkan.")

    if not _can_manage_roles(request):
        return HttpResponseForbidden(
            "Hanya Requirements Engineer atau Administrator "
            "yang dapat mengubah status akun."
        )

    target_user = get_object_or_404(User, pk=pk)

    if target_user.pk == request.user.pk:
        messages.error(request, "Anda tidak dapat menonaktifkan akun sendiri.")
        return redirect("accounts:kelola_role")

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=["is_active"])

    status = "diaktifkan" if target_user.is_active else "dinonaktifkan"
    messages.success(
        request,
        f"Akun '{target_user.username}' berhasil {status}.",
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
