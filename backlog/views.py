"""Views Sprint Backlog dan eksekusi item oleh Tim Developer."""
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import _get_acting_role, role_required
from accounts.models import User
from backlog.models import BacklogItem
from backlog.services import execution
from backlog.services.execution import BacklogExecutionError
from reviews.models import Ulasan
from stories.services import scoring


def _get_execution_user(request):
    """Ambil user pengerja: request.user jika login, atau fallback dev user."""
    if request.user and request.user.is_authenticated:
        return request.user
    dev_user = User.objects.filter(role=User.RolePengguna.TIM_DEVELOPER).first()
    if not dev_user:
        dev_user, _ = User.objects.get_or_create(
            username='dev_user',
            defaults={
                'role': User.RolePengguna.TIM_DEVELOPER,
                'email': 'dev@katawarga.local',
            },
        )
    return dev_user


def _ulasan_sumber(story):
    metrik = scoring.hitung_skor_cluster(story.cluster)
    ulasan = metrik.get('ulasan_list', [])
    if not ulasan:
        ulasan = Ulasan.objects.filter(
            hasil_ekstraksi_set__cluster_set__cluster=story.cluster
        ).distinct()
    return metrik, ulasan


@role_required(
    User.RolePengguna.TIM_DEVELOPER,
    User.RolePengguna.PRODUCT_OWNER,
)
def backlog_list_view(request):
    """
    Menampilkan daftar User Story yang sudah masuk backlog.

    Tim Developer dapat mengeksekusi item; Product Owner hanya melihat status.
    """
    backlog_items = (
        BacklogItem.objects
        .select_related("user_story", "pengguna")
        .order_by("-user_story__skor_prioritas")
    )
    acting_role = _get_acting_role(request)

    return render(request, "backlog/list.html", {
        "backlog_items": backlog_items,
        "can_execute": acting_role == User.RolePengguna.TIM_DEVELOPER,
    })


@role_required(
    User.RolePengguna.TIM_DEVELOPER,
    User.RolePengguna.PRODUCT_OWNER,
)
def backlog_detail_view(request, pk):
    """Detail item backlog, User Story, prioritas, dan ulasan sumber."""
    item = get_object_or_404(
        BacklogItem.objects.select_related(
            'user_story', 'user_story__cluster', 'pengguna',
        ),
        pk=pk,
    )
    metrik, ulasan_sumber = _ulasan_sumber(item.user_story)
    acting_role = _get_acting_role(request)

    return render(request, 'backlog/detail.html', {
        'item': item,
        'story': item.user_story,
        'metrik': metrik,
        'ulasan_sumber': ulasan_sumber,
        'can_execute': acting_role == User.RolePengguna.TIM_DEVELOPER,
    })


@role_required(User.RolePengguna.TIM_DEVELOPER)
def backlog_detail_latest_view(request):
    """Pintasan sidebar Developer ke item backlog aktif yang relevan."""
    item = (
        BacklogItem.objects
        .exclude(status_eksekusi=BacklogItem.StatusEksekusi.SELESAI)
        .select_related('user_story')
        .order_by('-user_story__skor_prioritas', 'tanggal_masuk_backlog')
        .first()
    )
    if item is None:
        item = (
            BacklogItem.objects
            .select_related('user_story')
            .order_by('-tanggal_masuk_backlog')
            .first()
        )

    if item is None:
        messages.info(request, 'Belum ada item backlog yang dapat dikerjakan.')
        return redirect('backlog:list')

    return redirect('backlog:detail', pk=item.pk)


@role_required(User.RolePengguna.TIM_DEVELOPER)
def mulai_kerjakan_view(request, pk):
    """
    POST /backlog/<pk>/mulai (FR-BKL-03).
    Hanya untuk TIM_DEVELOPER. SIAP_DIEKSEKUSI -> SEDANG_DIKERJAKAN.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    item = get_object_or_404(BacklogItem, pk=pk)
    user = _get_execution_user(request)

    try:
        execution.mulai_kerjakan(item, user, role=acting_role)
        messages.success(request, f"Item backlog #{item.pk} mulai dikerjakan.")
    except BacklogExecutionError as exc:
        messages.error(request, str(exc))
        if request.headers.get('HX-Request'):
            return HttpResponse(str(exc), status=400)

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('backlog:list')
        return response

    return redirect('backlog:list')


@role_required(User.RolePengguna.TIM_DEVELOPER)
def tandai_selesai_view(request, pk):
    """
    POST /backlog/<pk>/selesai (FR-BKL-04).
    Hanya untuk TIM_DEVELOPER. SEDANG_DIKERJAKAN -> SELESAI.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    item = get_object_or_404(BacklogItem, pk=pk)
    user = _get_execution_user(request)

    try:
        execution.tandai_selesai(item, user, role=acting_role)
        messages.success(request, "Keluhan pengguna telah ditangani")
    except BacklogExecutionError as exc:
        messages.error(request, str(exc))
        if request.headers.get('HX-Request'):
            return HttpResponse(str(exc), status=400)

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('backlog:list')
        return response

    return redirect('backlog:list')
