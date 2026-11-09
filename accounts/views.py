
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
User = get_user_model()


# FORM SIGN UP
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    role = forms.ChoiceField(
        choices=[("", "Choose your role")] + list(User.RolePengguna.choices),
        required=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "role",
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
        user.role = self.cleaned_data["role"]

        if commit:
            user.save()

        return user

# LOGIN
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            login(request, form.get_user())
            request.session.pop("acting_role", None)

            messages.success(request, "Login berhasil!")
            return redirect("/user-story/")
    else:
        form = AuthenticationForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form},
    )

# SIGN UP
def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            request.session.pop("acting_role", None)

            messages.success(
                request,
                "Akun berhasil dibuat. Selamat datang di KataWarga!"
            )

            return redirect("/user-story/")
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

    return redirect("/login/")

# KELOLA ROLE
@login_required
def kelola_role_view(request):
    acting_role = _get_acting_role(request)

    if (
        acting_role != User.RolePengguna.REQUIREMENTS_ENGINEER
        and not request.user.is_staff
    ):
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
        },
    )

# UBAH ROLE
@login_required
def ubah_role_view(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Metode tidak diizinkan."
        )

    acting_role = _get_acting_role(request)

    if (
        acting_role != User.RolePengguna.REQUIREMENTS_ENGINEER
        and not request.user.is_staff
    ):
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
        request.session["acting_role"] = new_role

        messages.info(
            request,
            f"Simulasi peran aktif diubah menjadi: {new_role}"
        )
    else:
        request.session.pop("acting_role", None)

        messages.info(
            request,
            "Simulasi peran aktif dikembalikan ke default."
        )

    next_url = request.POST.get("next", "/user-story/")

    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/user-story/"

    return redirect(next_url)
