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
        'group': 'workspace',
        'group_label': 'Workspace',
    },
    'pipeline': {
        'label': 'Extraction Pipeline',
        'url_name': 'extraction:pipeline',
        'group': 'pipeline',
        'group_label': 'Pipeline & Validasi',
    },
    'clustering': {
        'label': 'Clustering',
        'url_name': 'extraction:cluster_list',
        'group': 'pipeline',
        'group_label': 'Pipeline & Validasi',
    },
    'validasi': {
        'label': 'Validasi Ekstraksi',
        'url_name': 'extraction:validasi_list',
        'group': 'pipeline',
        'group_label': 'Pipeline & Validasi',
    },
    'compose': {
        'label': 'Susun User Story',
        'url_name': 'stories:susun',
        'group': 'delivery',
        'group_label': 'User Story',
    },
    'stories': {
        'label': 'User Story Backlog',
        'url_name': 'stories:board',
        'group': 'delivery',
        'group_label': 'User Story',
    },
    'story_detail': {
        'label': 'Detail User Story',
        'url_name': 'stories:detail_latest',
        'group': 'delivery',
        'group_label': 'User Story',
    },
    'backlog': {
        'label': 'Sprint Backlog',
        'url_name': 'backlog:list',
        'group': 'delivery',
        'group_label': 'Delivery',
    },
    'backlog_detail': {
        'label': 'Detail Backlog',
        'url_name': 'backlog:detail_latest',
        'group': 'delivery',
        'group_label': 'Delivery',
    },
    'roles': {
        'label': 'Kelola Akses Role',
        'url_name': 'accounts:kelola_role',
        'group': 'admin',
        'group_label': 'Administrasi',
    },
}

# Kontrak menu sidebar per peran efektif; akses Kelola Role ditambahkan
# secara terpisah hanya berdasar PERAN ASLI atau status superuser.
SIDEBAR_BY_ROLE = {
    User.RolePengguna.REQUIREMENTS_ENGINEER: (
        'dashboard', 'pipeline', 'clustering', 'compose',
    ),
    User.RolePengguna.ANALYST: (
        'dashboard', 'pipeline', 'validasi', 'clustering',
    ),
    User.RolePengguna.PRODUCT_OWNER: (
        'dashboard', 'stories', 'story_detail',
    ),
    User.RolePengguna.TIM_DEVELOPER: (
        'dashboard', 'backlog', 'backlog_detail',
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
    ('reviews', 'import_csv'): 'pipeline',
    ('reviews', 'csv_template'): 'pipeline',
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
    """Bangun sidebar sesuai peran efektif dan izin kelola role yang sah.

    ``is_superuser`` tetap ada pada signature untuk kompatibilitas pemanggil.
    Hak pengelolaan role harus berasal dari ``can_manage_roles`` yang dihitung
    terhadap user asli, bukan dari role hasil simulasi.
    """
    items = []
    keys = list(SIDEBAR_BY_ROLE.get(effective_role, ()))

    if can_manage_roles:
        if 'roles' not in keys:
            keys.append('roles')
    elif 'roles' in keys:
        keys.remove('roles')

    for key in keys:
        config = SIDEBAR_ITEMS[key]
        try:
            href = reverse(config['url_name'])
        except NoReverseMatch:
            # Jangan tampilkan tautan ke route yang tidak tersedia.
            continue
        items.append({
            'key': key,
            'label': config['label'],
            'href': href,
            'group': config.get('group', 'workspace'),
            'group_label': config.get('group_label', 'Workspace'),
        })

    return items


def navigation(request):
    """Sediakan data sidebar dan penanda menu aktif ke semua template."""
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

    active_config = SIDEBAR_ITEMS.get(active_section, {})

    # Jangan menggunakan effective_role di sini: simulasi Developer/Analyst/PO
    # tidak boleh memberikan atau mengambil hak kelola akun yang sebenarnya.
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
        'active_label': active_config.get('label', 'Workspace'),
        'active_group_label': active_config.get('group_label', 'Workspace'),
        'sidebar_items': _sidebar_items(
            effective_role,
            is_superuser=bool(is_authenticated and user.is_superuser),
            can_manage_roles=can_manage_roles,
        ),
    }
