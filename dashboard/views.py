"""Views Dashboard Overview dan pencarian global KataWarga."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import _get_acting_role
from dashboard.services.metrics import ringkasan_dashboard
from dashboard.services.search import cari_global


@login_required
def overview_view(request):
    """Dashboard Overview untuk semua pengguna yang sudah login."""
    return render(
        request,
        'dashboard/overview.html',
        {'metrics': ringkasan_dashboard()},
    )


@login_required
def search_view(request):
    """Pencarian global dengan cakupan hasil sesuai peran efektif."""
    query = request.GET.get('q', '').strip()
    role = _get_acting_role(request)
    groups, total = cari_global(query, role)

    return render(
        request,
        'dashboard/search.html',
        {
            'query': query,
            'groups': groups,
            'total': total,
            'searched': len(query) >= 2,
        },
    )
