"""
Views untuk Backlog #7 (Menyusun User Story) dan #8 (Validasi & Persetujuan User Story).
"""
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import role_required
from accounts.models import User
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory
from stories.services import composer, approval, scoring


def susun_user_story_view(request):
    """
    Halaman /susun-user-story (FR-USR-01, FR-USR-08).
    - GET: Tampilkan tombol 'Susun User Story' dan section #daftar-user-story.
    - POST: Jalankan compose_pending() untuk cluster TERVALIDASI.
            Hanya boleh diakses oleh REQUIREMENTS_ENGINEER (§4, §6.3).
    """
    if request.method == 'POST':
        # Cek hak akses untuk aksi POST
        # Sprint 1 dev role stub via accounts.decorators._get_acting_role
        from accounts.decorators import _get_acting_role
        acting_role = _get_acting_role(request)
        if acting_role != User.RolePengguna.REQUIREMENTS_ENGINEER:
            return HttpResponseForbidden('Hanya Requirements Engineer yang dapat menyusun user story.')

        # Jalankan penyusunan
        stories_created = composer.compose_pending()

        # Ambil semua user story terbaru untuk ditampilkan di section
        stories = UserStory.objects.all().select_related('cluster')

        # Jika request berasal dari HTMX, kembalikan partial _story_list.html
        if request.headers.get('HX-Request'):
            return render(request, 'stories/partials/_story_list.html', {
                'stories': stories,
                'baru_dibuat': len(stories_created),
            })

        messages.success(request, f"{len(stories_created)} user story berhasil disusun.")
        return render(request, 'stories/compose.html', {
            'stories': stories,
            'baru_dibuat': len(stories_created),
        })

    # GET request: dapat dilihat oleh semua peran
    stories = UserStory.objects.all().select_related('cluster')
    return render(request, 'stories/compose.html', {'stories': stories})


def user_story_board_view(request):
    """
    Halaman /user-story — Papan Kanban ringan (FR-APP-01, FR-APP-07).
    Kolom:
      - To Review (MENUNGGU_PERSETUJUAN)
      - Sprint Backlog (DISETUJUI)
      - Dismissed (DIABAIKAN)
    Filter GET:
      - aplikasi (id atau package_name)
      - prioritas (TINGGI, SEDANG, RENDAH)
    """
    qs = UserStory.objects.all().select_related('cluster')

    # Filter aplikasi
    app_filter = request.GET.get('aplikasi', '').strip()
    if app_filter:
        if app_filter.isdigit():
            qs = qs.filter(cluster__anggota_set__hasil_ekstraksi__ulasan__aplikasi__id=int(app_filter))
        else:
            qs = qs.filter(cluster__anggota_set__hasil_ekstraksi__ulasan__aplikasi__package_name=app_filter)

    # Filter kategori prioritas
    prio_filter = request.GET.get('prioritas', '').strip()
    if prio_filter:
        qs = qs.filter(kategori_prioritas=prio_filter.upper())

    # Urutkan berdasarkan skor menurun
    qs = qs.order_by('-skor_prioritas').distinct()

    # Kelompokkan per kolom status
    to_review = [s for s in qs if s.status_persetujuan == UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN]
    sprint_backlog = [s for s in qs if s.status_persetujuan == UserStory.StatusPersetujuan.DISETUJUI]
    dismissed = [s for s in qs if s.status_persetujuan == UserStory.StatusPersetujuan.DIABAIKAN]

    aplikasi_list = Aplikasi.objects.filter(aktif=True)

    return render(request, 'stories/board.html', {
        'to_review': to_review,
        'sprint_backlog': sprint_backlog,
        'dismissed': dismissed,
        'aplikasi_list': aplikasi_list,
        'selected_aplikasi': app_filter,
        'selected_prioritas': prio_filter,
    })


def user_story_detail_view(request, pk):
    """
    Halaman /user-story/<pk> — Detail User Story (FR-APP-02, FR-USR-10).
    Menampilkan:
      - Kalimat user story
      - Skor dan Kategori ('Tinggi'/'Sedang'/'Rendah') di data-testid="prioritas"
      - Status ('Menunggu Persetujuan'/'Disetujui'/'Diabaikan') di data-testid="status"
      - Rincian skor (n, F, rata-rata S)
      - Ulasan sumber
      - Tombol 'Setujui' dan 'Abaikan' saat MENUNGGU_PERSETUJUAN
    """
    story = get_object_or_404(UserStory.objects.select_related('cluster'), pk=pk)

    # Hitung rincian skor dari cluster
    metrik = scoring.hitung_skor_cluster(story.cluster)

    # Ambil ulasan sumber
    ulasan_sumber = metrik.get('ulasan_list', [])
    if not ulasan_sumber:
        ulasan_sumber = Ulasan.objects.filter(
            hasil_ekstraksi_set__cluster_set__cluster=story.cluster
        ).distinct()

    return render(request, 'stories/detail.html', {
        'story': story,
        'metrik': metrik,
        'ulasan_sumber': ulasan_sumber,
    })


def setujui_view(request, pk):
    """
    POST /user-story/<pk>/setujui (FR-APP-03, FR-SIM-04).
    Hanya untuk PRODUCT_OWNER (§4, SRS 5.3).
    Atomik: jika hook backlog gagal, rollback dan tampilkan pesan 'Gagal menyimpan ke backlog'.
    Sukses: redirect ke /backlog (HX-Redirect jika request HTMX).
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    from accounts.decorators import _get_acting_role
    acting_role = _get_acting_role(request)
    if acting_role != User.RolePengguna.PRODUCT_OWNER:
        return HttpResponseForbidden('Hanya Product Owner yang berhak menyetujui user story.')

    story = get_object_or_404(UserStory, pk=pk)

    try:
        approval.setujui_user_story(story, validator_user=request.user)
    except approval.ApprovalError as e:
        messages.error(request, 'Gagal menyimpan ke backlog')
        if request.headers.get('HX-Request'):
            response = HttpResponse('Gagal menyimpan ke backlog', status=400)
            return response
        return redirect(f"/user-story/{pk}")

    messages.success(request, 'User story berhasil disimpan ke backlog')

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/backlog'
        return response

    return redirect('/backlog')


def abaikan_view(request, pk):
    """
    POST /user-story/<pk>/abaikan (FR-APP-04).
    Hanya untuk PRODUCT_OWNER.
    Status -> DIABAIKAN, simpan alasan_diabaikan (opsional).
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    from accounts.decorators import _get_acting_role
    acting_role = _get_acting_role(request)
    if acting_role != User.RolePengguna.PRODUCT_OWNER:
        return HttpResponseForbidden('Hanya Product Owner yang berhak mengabaikan user story.')

    story = get_object_or_404(UserStory, pk=pk)
    alasan = request.POST.get('alasan', '')
    approval.abaikan_user_story(story, alasan=alasan)

    messages.info(request, 'User story telah diabaikan.')

    if request.headers.get('HX-Request'):
        return render(request, 'stories/detail.html', {
            'story': story,
            'metrik': scoring.hitung_skor_cluster(story.cluster),
            'ulasan_sumber': [],
        })

    return redirect(f"/user-story/{pk}")
