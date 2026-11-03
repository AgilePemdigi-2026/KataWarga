
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import _get_acting_role
from accounts.models import User
from backlog.models import BacklogItem
from backlog.services import execution
from backlog.services.execution import BacklogExecutionError


def _get_execution_user(request):
    """Ambil user pengerja: request.user jika login, atau fallback dev user jika DEV_MODE."""
    if request.user and request.user.is_authenticated:
        return request.user
    dev_user = User.objects.filter(role=User.RolePengguna.TIM_DEVELOPER).first()
    if not dev_user:
        dev_user, _ = User.objects.get_or_create(
            username='dev_user',
            defaults={'role': User.RolePengguna.TIM_DEVELOPER, 'email': 'dev@katawarga.local'}
        )
    return dev_user


def backlog_list_view(request):
    """Menampilkan daftar User Story yang sudah masuk backlog."""
    backlog_items = (
        BacklogItem.objects
        .select_related("user_story", "pengguna")
        .order_by("-user_story__skor_prioritas")
    )

    return render(request, "backlog/list.html", {
        "backlog_items": backlog_items,
    })


def mulai_kerjakan_view(request, pk):
    """
    POST /backlog/<pk>/mulai (FR-BKL-03).
    Hanya untuk TIM_DEVELOPER.
    Transisi: SIAP_DIEKSEKUSI -> SEDANG_DIKERJAKAN.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    if acting_role != User.RolePengguna.TIM_DEVELOPER:
        return HttpResponseForbidden('Hanya Tim Developer yang boleh mengeksekusi backlog.')

    item = get_object_or_404(BacklogItem, pk=pk)
    user = _get_execution_user(request)

    try:
        execution.mulai_kerjakan(item, user)
        messages.success(request, f"Item backlog #{item.pk} mulai dikerjakan.")
    except BacklogExecutionError as exc:
        messages.error(request, str(exc))
        if request.headers.get('HX-Request'):
            return HttpResponse(str(exc), status=400)

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/backlog'
        return response

    return redirect('/backlog')


def tandai_selesai_view(request, pk):
    """
    POST /backlog/<pk>/selesai (FR-BKL-04).
    Hanya untuk TIM_DEVELOPER.
    Transisi: SEDANG_DIKERJAKAN -> SELESAI.
    Pesan sukses persis: 'Keluhan pengguna telah ditangani' (Gherkin 5.2.6).
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    if acting_role != User.RolePengguna.TIM_DEVELOPER:
        return HttpResponseForbidden('Hanya Tim Developer yang boleh mengeksekusi backlog.')

    item = get_object_or_404(BacklogItem, pk=pk)
    user = _get_execution_user(request)

    try:
        execution.tandai_selesai(item, user)
        messages.success(request, "Keluhan pengguna telah ditangani")
    except BacklogExecutionError as exc:
        messages.error(request, str(exc))
        if request.headers.get('HX-Request'):
            return HttpResponse(str(exc), status=400)

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/backlog'
        return response

    return redirect('/backlog')
