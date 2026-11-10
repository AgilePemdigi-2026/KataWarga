"""
Views untuk Extraction Pipeline, Clustering, dan Validasi Hasil Ekstraksi.

RBAC:
- Requirements Engineer: melihat/menjalankan pipeline dan memantau cluster.
- Analyst: melihat pipeline (read-only) dan memvalidasi cluster.
- Product Owner/Tim Developer: tidak memiliki akses ke area ini.
"""
from django.contrib import messages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import _get_acting_role, role_required
from accounts.models import User
from extraction.models import Cluster, HasilEkstraksi
from extraction.services import validation
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


ROLE_MONITOR = (
    User.RolePengguna.REQUIREMENTS_ENGINEER,
    User.RolePengguna.ANALYST,
)


def _pipeline_stats():
    return {
        'total_ulasan': Ulasan.objects.count(),
        'ulasan_lolos': Ulasan.objects.filter(
            status_filter=Ulasan.StatusFilter.LOLOS
        ).count(),
        'ulasan_dibuang': Ulasan.objects.filter(
            status_filter=Ulasan.StatusFilter.DIBUANG
        ).count(),
        'total_ekstraksi': HasilEkstraksi.objects.count(),
        'cluster_menunggu': Cluster.objects.filter(
            status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI
        ).count(),
        'cluster_tervalidasi': Cluster.objects.filter(
            status_cluster=Cluster.StatusCluster.TERVALIDASI
        ).count(),
    }


@role_required(*ROLE_MONITOR)
def pipeline_view(request):
    """
    Halaman /ekstraksi/ (FR-EKS-02, FR-EKS-13).

    Menampilkan review asli, status filter, hasil WHO/WHAT/WHY, dan cluster.
    Requirements Engineer dapat menjalankan ekstraksi + clustering; Analyst
    hanya memantau (read-only).
    """
    acting_role = _get_acting_role(request)

    ulasan_qs = (
        Ulasan.objects
        .select_related('aplikasi')
        .prefetch_related('hasil_ekstraksi_set__cluster_set__cluster')
        .order_by('-tanggal_ulasan', '-id')
    )

    selected_app = request.GET.get('aplikasi', '').strip()
    selected_status = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    if selected_app:
        ulasan_qs = ulasan_qs.filter(aplikasi__package_name=selected_app)
    if selected_status in dict(Ulasan.StatusFilter.choices):
        ulasan_qs = ulasan_qs.filter(status_filter=selected_status)
    if query:
        ulasan_qs = ulasan_qs.filter(isi_ulasan__icontains=query)

    paginator = Paginator(ulasan_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    clusters = (
        Cluster.objects
        .prefetch_related('anggota_set__hasil_ekstraksi__ulasan__aplikasi')
        .order_by('-tanggal_dibuat')[:8]
    )

    return render(request, 'extraction/pipeline.html', {
        'page_obj': page_obj,
        'clusters': clusters,
        'apps': Aplikasi.objects.filter(aktif=True).order_by('nama_aplikasi'),
        'stats': _pipeline_stats(),
        'selected_app': selected_app,
        'selected_status': selected_status,
        'query': query,
        'status_choices': Ulasan.StatusFilter.choices,
        'can_run': acting_role == User.RolePengguna.REQUIREMENTS_ENGINEER,
    })


@role_required(User.RolePengguna.REQUIREMENTS_ENGINEER)
def run_pipeline_view(request):
    """
    POST /ekstraksi/jalankan/ — jalankan ekstraksi + clustering yang tersedia.

    Scraping tetap dijalankan melalui management command/jadwal karena
    membutuhkan akses jaringan. Aksi ini memproses ulasan yang sudah tersimpan.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    try:
        call_command('extract_reviews')
        call_command('cluster_reviews')
    except CommandError as exc:
        messages.error(request, f'Proses ekstraksi gagal: {exc}')
    except Exception as exc:  # jangan bocorkan traceback ke pengguna
        messages.error(
            request,
            f'Proses ekstraksi gagal dijalankan: {type(exc).__name__}.',
        )
    else:
        messages.success(request, 'Proses ekstraksi selesai')

    return redirect('extraction:pipeline')


@role_required(*ROLE_MONITOR)
def cluster_list_view(request):
    """Daftar cluster untuk pemantauan RE/Analyst."""
    status = request.GET.get('status', '').strip()
    clusters_qs = (
        Cluster.objects
        .prefetch_related('anggota_set__hasil_ekstraksi__ulasan__aplikasi')
        .order_by('-tanggal_dibuat')
    )
    if status in dict(Cluster.StatusCluster.choices):
        clusters_qs = clusters_qs.filter(status_cluster=status)

    paginator = Paginator(clusters_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'extraction/cluster_list.html', {
        'page_obj': page_obj,
        'status_choices': Cluster.StatusCluster.choices,
        'selected_status': status,
    })


@role_required(*ROLE_MONITOR)
def cluster_detail_view(request, pk):
    """
    Detail cluster beserta seluruh komentar asli dan elemen WHO/WHAT/WHY.

    RE melihat read-only. Analyst dapat menyetujui/menolak cluster yang masih
    menunggu validasi.
    """
    cluster = get_object_or_404(
        Cluster.objects.prefetch_related(
            'anggota_set__hasil_ekstraksi__ulasan__aplikasi'
        ),
        pk=pk,
    )
    acting_role = _get_acting_role(request)

    anggota = list(
        cluster.anggota_set
        .select_related('hasil_ekstraksi__ulasan__aplikasi')
        .order_by('id')
    )
    story = UserStory.objects.filter(cluster=cluster).first()

    return render(request, 'extraction/cluster_detail.html', {
        'cluster': cluster,
        'anggota': anggota,
        'story': story,
        'can_validate': (
            acting_role == User.RolePengguna.ANALYST
            and cluster.status_cluster == Cluster.StatusCluster.MENUNGGU_VALIDASI
        ),
        'can_compose': (
            acting_role == User.RolePengguna.REQUIREMENTS_ENGINEER
            and cluster.status_cluster == Cluster.StatusCluster.TERVALIDASI
            and story is None
        ),
    })


@role_required(User.RolePengguna.ANALYST)
def validasi_list_view(request):
    """
    Halaman /validasi-ekstraksi/ (FR-VAL-01).

    Daftar cluster yang berstatus MENUNGGU_VALIDASI untuk divalidasi Analyst.
    Requirements Engineer dapat melihat komentar/cluster lewat halaman
    clustering, tetapi tidak lewat antarmuka validasi ini.
    """
    clusters = (
        Cluster.objects
        .filter(status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI)
        .prefetch_related('anggota_set__hasil_ekstraksi__ulasan__aplikasi')
        .order_by('-tanggal_dibuat')
    )

    return render(request, 'extraction/validasi.html', {
        'clusters': clusters,
    })


@role_required(User.RolePengguna.ANALYST)
def setujui_cluster_view(request, pk):
    """POST /validasi-ekstraksi/<pk>/setujui/ (FR-VAL-03)."""
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    cluster = get_object_or_404(Cluster, pk=pk)
    user = request.user if getattr(request.user, 'is_authenticated', False) else None

    try:
        validation.setujui_cluster(cluster, validator_user=user)
        messages.success(
            request,
            f"Cluster '{cluster.nama_topik}' berhasil tervalidasi.",
        )
    except validation.ValidationError as exc:
        messages.error(request, str(exc))

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/validasi-ekstraksi/'
        return response

    return redirect('extraction:validasi_list')


@role_required(User.RolePengguna.ANALYST)
def tolak_cluster_view(request, pk):
    """POST /validasi-ekstraksi/<pk>/tolak/ (FR-VAL-04)."""
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    cluster = get_object_or_404(Cluster, pk=pk)
    user = request.user if getattr(request.user, 'is_authenticated', False) else None

    validation.tolak_cluster(cluster, validator_user=user)
    messages.info(
        request,
        f"Cluster '{cluster.nama_topik}' ditolak dan ditandai dihapus.",
    )

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/validasi-ekstraksi/'
        return response

    return redirect('extraction:validasi_list')
