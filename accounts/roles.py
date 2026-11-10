"""Pemetaan halaman utama dan label peran KataWarga."""
from django.urls import NoReverseMatch, reverse

from accounts.models import User


ROLE_LABELS = dict(User.RolePengguna.choices)

ROLE_HOME_URL_NAMES = {
    User.RolePengguna.REQUIREMENTS_ENGINEER: 'extraction:pipeline',
    User.RolePengguna.ANALYST: 'extraction:validasi_list',
    User.RolePengguna.PRODUCT_OWNER: 'stories:board',
    User.RolePengguna.TIM_DEVELOPER: 'backlog:list',
}


def role_label(role):
    """Label UI untuk kode peran; string kosong bila peran tidak dikenal."""
    return ROLE_LABELS.get(role, '')


def role_home_url(role):
    """URL halaman utama yang sesuai dengan peran efektif pengguna."""
    url_name = ROLE_HOME_URL_NAMES.get(role)
    if url_name:
        try:
            return reverse(url_name)
        except NoReverseMatch:
            pass
    return reverse('dashboard:overview')
