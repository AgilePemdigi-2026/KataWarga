"""Context processor untuk sidebar dan informasi peran efektif."""
from django.conf import settings
from django.urls import NoReverseMatch, reverse

from accounts.decorators import _get_acting_role
from accounts.models import User
from accounts.roles import role_label


SIDEBAR_ITEMS = {
    'dashboard': {
        'label': 'Dashboard',
        'url_name': 'dashboard:overview',
    },
    'pipeline': {
        'label': 'Extraction Pipeline',
        'url_name': 'extraction:pipeline',
    },
    'clustering': {
        'label': 'Clustering',
        'url_name': 'extraction:cluster_list',
    },
    'validasi': {
        'label': 'Validasi Ekstraksi',
        'url_name': 'extraction:validasi_list',
    },
    'compose': {
        'label': 'Susun User Story',
        'url_name': 'stories:susun',
    },
    'stories': {
        'label': 'User Story Backlog',
        'url_name': 'stories:board',
    },
    'story_detail': {
        'label': 'Detail User Story',
        'url_name': 'stories:detail_latest',
    },
    'backlog': {
        'label': 'Sprint Backlog',
        'url_name': 'backlog:list',
    },
    'backlog_detail': {
        'label': 'Detail Backlog',
        'url_name': 'backlog:detail_latest',
    },
    'roles': {
        'label': 'Kelola Akses Role',
        'url_name': 'accounts:kelola_role',
    },
}

# Kontrak menu sidebar per peran efektif. Hanya route yang memang boleh
# diakses peran tersebut yang ditampilkan.
SIDEBAR_BY_ROLE = {
    User.RolePengguna.REQUIREMENTS_ENGINEER: (
        'dashboard',
        'pipeline',
        'clustering',
        'compose',
    ),
    User.RolePengguna.ANALYST: (
        'dashboard',
        'pipeline',
        'validasi',
        'clustering',
    ),
    User.RolePengguna.PRODUCT_OWNER: (
        'dashboard',
        'stories',
        'story_detail',
        'roles',
    ),
    User.RolePengguna.TIM_DEVELOPER: (
        'dashboard',
        'backlog',
        'backlog_detail',
    ),
}


_ACTIVE_SECTIONS = {
    ('dashboard', 'overview'): 'dashboard',
    ('dashboard', 'dashboard'): 'dashboard',
    ('extraction', 'pipeline'): 'pipeline',
    ('extraction', 'run_pipeline'): 'pipeline',
    ('extraction', 'cluster_list'): 'clustering',
    ('extraction', 'cluster_detail'): 'clustering',
    ('extraction', 'validasi_list'): 'validasi',
    ('stories', 'susun'): 'compose',
    ('stories', 'board'): 'stories',
    ('stories', 'detail'): 'stories',
    ('stories', 'detail_latest'): 'stories',
    ('backlog', 'list'): 'backlog',
    ('backlog', 'detail'): 'backlog',
    ('backlog', 'detail_latest'): 'backlog',
    ('accounts', 'kelola_role'): 'roles',
    ('accounts', 'ubah_role'): 'roles',
    ('accounts', 'toggle_active'): 'roles',
}


def _sidebar_items(effective_role, is_superuser=False, can_manage_roles=False):
    """Bangun daftar menu sidebar yang aman untuk peran efektif."""
    items = []
    keys = list(SIDEBAR_BY_ROLE.get(effective_role, ()))
    if 'roles' in keys and not can_manage_roles:
        keys.remove('roles')
    elif can_manage_roles and 'roles' not in keys:
        keys.append('roles')

    for key in keys:
        config = SIDEBAR_ITEMS[key]

        try:
            href = reverse(config['url_name'])
        except NoReverseMatch:
            # Jangan tampilkan tautan yang route-nya tidak tersedia.
            continue

        items.append({
            'key': key,
            'label': config['label'],
            'href': href,
        })

    return items


def navigation(request):
    """Sediakan peran efektif dan penanda menu aktif ke semua template."""
    user = getattr(request, 'user', None)
    is_authenticated = bool(user and user.is_authenticated)
    effective_role = _get_acting_role(request) if is_authenticated else None
    original_role = user.role if is_authenticated else None

    match = getattr(request, 'resolver_match', None)
    active_section = ''
    active_url_name = ''
    if match is not None:
        active_url_name = match.url_name or ''
        active_section = _ACTIVE_SECTIONS.get(
            (match.namespace or '', active_url_name), ''
        )

    can_manage_roles = bool(
        is_authenticated
        and (
            user.is_superuser
            or original_role == User.RolePengguna.PRODUCT_OWNER
        )
    )

    return {
        'effective_role': effective_role,
        'effective_role_label': role_label(effective_role),
        'original_role': original_role,
        'original_role_label': role_label(original_role),
        'is_simulating_role': bool(
            is_authenticated
            and effective_role
            and original_role
            and effective_role != original_role
        ),
        'can_simulate_role': bool(
            is_authenticated and settings.DEBUG and user.is_staff
        ),
        'can_manage_roles': can_manage_roles,
        'role_choices': User.RolePengguna.choices,
        'is_re': effective_role == User.RolePengguna.REQUIREMENTS_ENGINEER,
        'is_analyst': effective_role == User.RolePengguna.ANALYST,
        'is_po': effective_role == User.RolePengguna.PRODUCT_OWNER,
        'is_developer': effective_role == User.RolePengguna.TIM_DEVELOPER,
        'active_section': active_section,
        'active_url_name': active_url_name,
        'sidebar_items': _sidebar_items(effective_role, is_superuser=bool(user and user.is_superuser), can_manage_roles=can_manage_roles),
    }
