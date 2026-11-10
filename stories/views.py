"""
Views untuk Backlog #7 (Menyusun User Story) dan #8 (Validasi & Persetujuan User Story).

RBAC:
- Requirements Engineer: menyusun dan melihat hasil User Story.
- Product Owner: melihat board, menyetujui, dan mengabaikan User Story.
- Tim Developer: melihat detail User Story dari Sprint Backlog (read-only).
"""
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import _get_acting_role, role_required
from accounts.models import User
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory
from stories.services import composer, approval, scoring


@role_required(User.RolePengguna.REQUIREMENTS_ENGINEER)
def susun_user_story_view(request):
    """
    Halaman /susun-user-story (FR-USR-01, FR-USR-08).
    - GET: Tampilkan tombol 'Susun User Story' dan section #daftar-user-story.
    - POST: Jalankan compose_pending() untuk cluster TERVALIDASI.
    """
    if request.method == 'POST':
        stories_created = composer.compose_pending()
        stories = UserStory.objects.all().select_related('cluster')

        if request.headers.get('HX-Request'):
            return render(request, 'stories/partials/_story_list.html', {
                'stories': stories,
                'baru_dibuat': len(stories_created),
            })

        messages.success(
            request,
            f"{len(stories_created)} user story berhasil disusun.",
        )
        return render(request, 'stories/compose.html', {
            'stories': stories,
            'baru_dibuat': len(stories_created),
        })

    stories = UserStory.objects.all().select_related('cluster')
    return render(request, 'stories/compose.html', {'stories': stories})


@role_required(User.RolePengguna.PRODUCT_OWNER)
def user_story_board_view(request):
    """
    Halaman /user-story — Papan Kanban ringan (FR-APP-01, FR-APP-07).
    Kolom:
      - To Review (MENUNGGU_PERSETUJUAN)
      - Sprint Backlog (DISETUJUI)
      - Dismissed (DIABAIKAN)
    """
    qs = UserStory.objects.all().select_related('cluster')

    app_filter = request.GET.get('aplikasi', '').strip()
    if app_filter:
        if app_filter.isdigit():
            qs = qs.filter(
                cluster__anggota_set__hasil_ekstraksi__ulasan__aplikasi__id=int(app_filter)
            )
        else:
            qs = qs.filter(
                cluster__anggota_set__hasil_ekstraksi__ulasan__aplikasi__package_name=app_filter
            )

    prio_filter = request.GET.get('prioritas', '').strip()
    if prio_filter:
        qs = qs.filter(kategori_prioritas=prio_filter.upper())

    qs = qs.order_by('-skor_prioritas').distinct()

    to_review = [
        s for s in qs
        if s.status_persetujuan == UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN
    ]
    sprint_backlog = [
        s for s in qs
        if s.status_persetujuan == UserStory.StatusPersetujuan.DISETUJUI
    ]
    dismissed = [
        s for s in qs
        if s.status_persetujuan == UserStory.StatusPersetujuan.DIABAIKAN
    ]

    aplikasi_list = Aplikasi.objects.filter(aktif=True)

    return render(request, 'stories/board.html', {
        'to_review': to_review,
        'sprint_backlog': sprint_backlog,
        'dismissed': dismissed,
        'aplikasi_list': aplikasi_list,
        'selected_aplikasi': app_filter,
        'selected_prioritas': prio_filter,
    })


@role_required(
    User.RolePengguna.REQUIREMENTS_ENGINEER,
    User.RolePengguna.PRODUCT_OWNER,
    User.RolePengguna.TIM_DEVELOPER,
)
def user_story_detail_view(request, pk):
    """
    Halaman /user-story/<pk> — Detail User Story (FR-APP-02, FR-USR-10).

    Tombol Setujui/Abaikan hanya ditampilkan dan diizinkan untuk Product Owner.
    """
    story = get_object_or_404(
        UserStory.objects.select_related('cluster'),
        pk=pk,
    )
    acting_role = _get_acting_role(request)

    metrik = scoring.hitung_skor_cluster(story.cluster)
    ulasan_sumber = metrik.get('ulasan_list', [])
    if not ulasan_sumber:
        ulasan_sumber = Ulasan.objects.filter(
            hasil_ekstraksi_set__cluster_set__cluster=story.cluster
        ).distinct()

    if acting_role == User.RolePengguna.TIM_DEVELOPER:
        back_url = reverse('backlog:list')
        back_label = 'Kembali ke Sprint Backlog'
    elif acting_role == User.RolePengguna.REQUIREMENTS_ENGINEER:
        back_url = reverse('stories:susun')
        back_label = 'Kembali ke Susun User Story'
    else:
        back_url = reverse('stories:board')
        back_label = 'Kembali ke Papan Backlog'

    return render(request, 'stories/detail.html', {
        'story': story,
        'metrik': metrik,
        'ulasan_sumber': ulasan_sumber,
        'can_approve': (
            acting_role == User.RolePengguna.PRODUCT_OWNER
            and story.status_persetujuan
            == UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN
        ),
        'can_view_cluster': (
            acting_role == User.RolePengguna.REQUIREMENTS_ENGINEER
        ),
        'back_url': back_url,
        'back_label': back_label,
    })


@role_required(User.RolePengguna.PRODUCT_OWNER)
def user_story_detail_latest_view(request):
    """Pintasan sidebar PO ke User Story yang paling relevan."""
    story = (
        UserStory.objects
        .filter(status_persetujuan=UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN)
        .order_by('-skor_prioritas', '-tanggal_disusun')
        .first()
    )
    if story is None:
        story = UserStory.objects.order_by('-tanggal_disusun').first()

    if story is None:
        messages.info(
            request,
            'Belum ada User Story. Minta Requirements Engineer menyusunnya '
            'dari cluster yang sudah tervalidasi.',
        )
        return redirect('stories:board')

    return redirect('stories:detail', pk=story.pk)


@role_required(User.RolePengguna.PRODUCT_OWNER)
def setujui_view(request, pk):
    """
    POST /user-story/<pk>/setujui (FR-APP-03, FR-SIM-04).
    Hanya untuk PRODUCT_OWNER.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    story = get_object_or_404(UserStory, pk=pk)

    try:
        approval.setujui_user_story(story, validator_user=request.user)
    except approval.ApprovalError:
        messages.error(request, 'Gagal menyimpan ke backlog')
        if request.headers.get('HX-Request'):
            return HttpResponse('Gagal menyimpan ke backlog', status=400)
        return redirect('stories:detail', pk=pk)

    messages.success(request, 'User story berhasil disimpan ke backlog')

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('backlog:list')
        return response

    return redirect('backlog:list')


@role_required(User.RolePengguna.PRODUCT_OWNER)
def abaikan_view(request, pk):
    """
    POST /user-story/<pk>/abaikan (FR-APP-04).
    Hanya untuk PRODUCT_OWNER. Status -> DIABAIKAN.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    story = get_object_or_404(UserStory, pk=pk)
    alasan = request.POST.get('alasan', '')
    approval.abaikan_user_story(story, alasan=alasan)

    messages.info(request, 'User story telah diabaikan.')

    if request.headers.get('HX-Request'):
        return render(request, 'stories/detail.html', {
            'story': story,
            'metrik': scoring.hitung_skor_cluster(story.cluster),
            'ulasan_sumber': [],
            'can_approve': False,
            'can_view_cluster': False,
            'back_url': reverse('stories:board'),
            'back_label': 'Kembali ke Papan Backlog',
        })

    return redirect('stories:detail', pk=pk)
