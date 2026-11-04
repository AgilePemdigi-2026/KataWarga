"""
Views untuk Validasi Hasil Ekstraksi & Cluster (UC-2, FR-VAL-01 s/d FR-VAL-05).
"""
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import _get_acting_role
from accounts.models import User
from extraction.models import Cluster, HasilEkstraksi
from extraction.services import validation


def validasi_list_view(request):
    """
    Halaman /validasi-ekstraksi (FR-VAL-01):
    Daftar cluster yang berstatus MENUNGGU_VALIDASI untuk divalidasi oleh Analyst.
    """
    acting_role = _get_acting_role(request)
    # Peran Analyst atau admin
    if acting_role not in [User.RolePengguna.ANALYST] and not (request.user and request.user.is_staff):
        return HttpResponseForbidden('Hanya Analyst yang dapat mengakses antarmuka validasi ekstraksi.')

    clusters = (
        Cluster.objects.filter(status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI)
        .prefetch_related('anggota_set__hasil_ekstraksi__ulasan__aplikasi')
        .order_by('-tanggal_dibuat')
    )

    return render(request, 'extraction/validasi.html', {
        'clusters': clusters,
    })


def setujui_cluster_view(request, pk):
    """
    POST /validasi-ekstraksi/<pk>/setujui (FR-VAL-03).
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    if acting_role not in [User.RolePengguna.ANALYST] and not (request.user and request.user.is_staff):
        return HttpResponseForbidden('Hanya Analyst yang berhak menyetujui hasil ekstraksi.')

    cluster = get_object_or_404(Cluster, pk=pk)
    user = request.user if getattr(request.user, 'is_authenticated', False) else None

    try:
        validation.setujui_cluster(cluster, validator_user=user)
        messages.success(request, f"Cluster '{cluster.nama_topik}' berhasil tervalidasi.")
    except validation.ValidationError as exc:
        messages.error(request, str(exc))

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/validasi-ekstraksi'
        return response

    return redirect('extraction:validasi_list')


def tolak_cluster_view(request, pk):
    """
    POST /validasi-ekstraksi/<pk>/tolak (FR-VAL-04).
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    if acting_role not in [User.RolePengguna.ANALYST] and not (request.user and request.user.is_staff):
        return HttpResponseForbidden('Hanya Analyst yang berhak menolak hasil ekstraksi.')

    cluster = get_object_or_404(Cluster, pk=pk)
    user = request.user if getattr(request.user, 'is_authenticated', False) else None

    validation.tolak_cluster(cluster, validator_user=user)
    messages.info(request, f"Cluster '{cluster.nama_topik}' ditolak dan ditandai dihapus.")

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/validasi-ekstraksi'
        return response

    return redirect('extraction:validasi_list')

