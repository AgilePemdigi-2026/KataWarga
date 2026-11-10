"""Views Dashboard Overview KataWarga."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from dashboard.services.metrics import ringkasan_dashboard


@login_required
def overview_view(request):
    """Dashboard Overview untuk semua pengguna yang sudah login."""
    return render(
        request,
        'dashboard/overview.html',
        {'metrics': ringkasan_dashboard()},
    )
