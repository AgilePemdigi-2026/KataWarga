"""
API JSON konsisten untuk frontend (Sprint 3, bagian E). Dipakai Sakha lewat fetch/HTMX.

Format respons SEMUA endpoint:
    sukses : {"status": "success", "data": <objek|daftar>, "error": null, "meta": {...}}
    gagal  : {"status": "error",   "data": null, "error": {"code": "...", "message": "..."}, "meta": {}}

Kode error: tidak_login (401), akses_ditolak (403), tidak_ditemukan (404), metode_tidak_diizinkan (405),
permintaan_tidak_valid (400), status_tidak_valid (409).
Autentikasi memakai sesi Django; permintaan POST wajib membawa header `X-CSRFToken` dan body JSON.
Tampilan (cluster/ekstraksi) boleh dibaca RE dan Analyst; aksi validasi hanya Analyst.
"""
import functools
import json

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404  # noqa: F401  (dipakai tidak langsung lewat _ambil)

from accounts.decorators import _get_acting_role
from accounts.models import User
from extraction.models import Cluster, GalatEkstraksi, HasilEkstraksi, LogValidasi
from extraction.services import validation
from reviews.models import Ulasan

ROLE_BACA = (User.RolePengguna.REQUIREMENTS_ENGINEER, User.RolePengguna.ANALYST)
ROLE_VALIDASI = (User.RolePengguna.ANALYST,)


# --------------------------------------------------------------------------- amplop respons
def sukses(data, meta=None, status=200):
    return JsonResponse({'status': 'success', 'data': data, 'error': None, 'meta': meta or {}}, status=status)


def galat(kode, pesan, status):
    return JsonResponse({'status': 'error', 'data': None, 'error': {'code': kode, 'message': pesan}, 'meta': {}},
                        status=status)


def api_view(*, roles, methods=('GET',)):
    """Dekorator: cek metode, login, peran; semua penolakan berupa JSON (bukan redirect/HTML)."""
    def dekorator(fn):
        @functools.wraps(fn)
        def _wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return galat('metode_tidak_diizinkan', f"Metode {request.method} tidak diizinkan.", 405)
            user = getattr(request, 'user', None)
            if user is None or not user.is_authenticated:
                return galat('tidak_login', 'Silakan login terlebih dahulu.', 401)
            if _get_acting_role(request) not in roles:
                return galat('akses_ditolak', 'Peran Anda tidak memiliki akses ke sumber daya ini.', 403)
            try:
                return fn(request, *args, **kwargs)
            except validation.ValidationError as exc:
                return galat('status_tidak_valid', str(exc), 409)
            except _Permintaan as exc:
                return galat(exc.kode, str(exc), exc.http)
        return _wrapped
    return dekorator


class _Permintaan(Exception):
    def __init__(self, pesan, kode='permintaan_tidak_valid', http=400):
        super().__init__(pesan)
        self.kode, self.http = kode, http


def _ambil(model, pk, queryset=None):
    try:
        return (queryset if queryset is not None else model.objects).get(pk=pk)
    except model.DoesNotExist:
        raise _Permintaan(f'{model._meta.verbose_name} #{pk} tidak ditemukan.', 'tidak_ditemukan', 404)


def _body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise _Permintaan('Body harus berupa JSON yang valid.')
    if not isinstance(data, dict):
        raise _Permintaan('Body JSON harus berupa objek.')
    return data


def _halaman(request, qs, serial):
    try:
        ukuran = min(max(int(request.GET.get('ukuran', 20)), 1), 100)
    except ValueError:
        raise _Permintaan("Parameter 'ukuran' harus berupa angka.")
    page = Paginator(qs, ukuran).get_page(request.GET.get('halaman'))
    meta = {'halaman': page.number, 'ukuran': ukuran, 'total_halaman': page.paginator.num_pages,
            'total': page.paginator.count}
    return sukses([serial(o) for o in page.object_list], meta)


def _tgl(dt):
    return dt.isoformat() if dt else None


# --------------------------------------------------------------------------- serializer
def status_tahap(ulasan):
    """
    Status tiap tahap pipeline untuk satu ulasan, DIHITUNG dari data tersimpan (selalu konsisten):
    filter -> ekstraksi -> clustering -> validasi.
    """
    hasil = list(ulasan.hasil_ekstraksi_set.all())
    if ulasan.status_filter == Ulasan.StatusFilter.DIBUANG:
        ekstraksi = 'TIDAK_DIPROSES'
    elif hasil:
        ekstraksi = 'BERHASIL'
    elif ulasan.galat_ekstraksi_set.all():
        ekstraksi = 'GAGAL'
    else:
        ekstraksi = 'BELUM_DIPROSES'
    ids_cluster = sorted({ca.cluster_id for h in hasil for ca in h.cluster_set.all()})
    status_val = sorted({h.status_validasi for h in hasil})
    return {
        'filter': {'status': ulasan.status_filter, 'alasan': ulasan.alasan_filter or None},
        'ekstraksi': {'status': ekstraksi, 'jumlah_hasil': len(hasil)},
        'clustering': {'status': 'DALAM_CLUSTER' if ids_cluster else 'BELUM', 'cluster_id': ids_cluster},
        'validasi': {'status': status_val},
    }


def ser_ulasan(u):
    return {'id': u.pk, 'aplikasi': u.aplikasi.nama_aplikasi, 'package_name': u.aplikasi.package_name,
            'isi_ulasan': u.isi_ulasan, 'skor_bintang': u.skor_bintang, 'tanggal_ulasan': u.tanggal_ulasan.isoformat(),
            'tahap': status_tahap(u)}


def ser_ekstraksi(h, detail=False):
    d = {
        'id': h.pk, 'ulasan_id': h.ulasan_id, 'aplikasi': h.ulasan.aplikasi.nama_aplikasi,
        'who': h.teks_who, 'what': h.teks_what, 'why': h.teks_why,
        'user_story': h.kalimat_user_story or None,
        'confidence': float(h.skor_confidence), 'sentimen': h.sentimen or None,
        'status_validasi': h.status_validasi, 'cluster_id': [ca.cluster_id for ca in h.cluster_set.all()],
        'ekstraktor': h.nama_ekstraktor or None, 'model': h.model_llm or None, 'versi_prompt': h.versi_prompt or None,
    }
    if detail:
        d.update({
            'evidence': h.evidence or None, 'evidence_why': h.evidence_why or None,
            'isi_ulasan': h.ulasan.isi_ulasan, 'skor_bintang': h.ulasan.skor_bintang,
            'pengguna_validasi': h.pengguna.get_username() if h.pengguna_id else None,
            'tanggal_ekstraksi': _tgl(h.tanggal_ekstraksi), 'tanggal_validasi': _tgl(h.tanggal_validasi),
        })
    return d


def ser_cluster(c, detail=False):
    rep = c.representatif
    d = {
        'id': c.pk, 'nama_topik': c.nama_topik, 'status': c.status_cluster, 'jumlah_anggota': c.jumlah_anggota,
        'metode': c.metode or None, 'ambang_jarak': c.ambang_jarak, 'rata_jarak': c.rata_jarak,
        'representatif': ser_ekstraksi(rep) if rep else None,
        'tanggal_dibuat': _tgl(c.tanggal_dibuat),
    }
    if detail:
        d['anggota'] = [ser_ekstraksi(ca.hasil_ekstraksi, detail=True) for ca in c.anggota_set.all()]
    return d


def ser_log(l):
    return {'id': l.pk, 'aksi': l.aksi, 'objek': l.objek_jenis, 'objek_id': l.objek_id,
            'pengguna': l.pengguna.get_username() if l.pengguna_id else None,
            'nilai_lama': l.nilai_lama, 'nilai_baru': l.nilai_baru, 'catatan': l.catatan or None,
            'tanggal': _tgl(l.tanggal)}


_QS_EKS = HasilEkstraksi.objects.select_related('ulasan__aplikasi', 'pengguna').prefetch_related('cluster_set')
_QS_CLU = Cluster.objects.select_related('representatif__ulasan__aplikasi').prefetch_related('representatif__cluster_set')


# --------------------------------------------------------------------------- endpoint baca
@api_view(roles=ROLE_BACA)
def ringkasan(request):
    """GET /api/v1/ringkasan/ — hitungan per tahap pipeline."""
    hitung = lambda qs, f: {k: qs.filter(**{f: k}).count() for k in sorted(set(qs.values_list(f, flat=True)))}  # noqa: E731
    return sukses({
        'ulasan': {'total': Ulasan.objects.count(), **hitung(Ulasan.objects.all(), 'status_filter')},
        'ulasan_dibuang_per_alasan': hitung(Ulasan.objects.filter(status_filter='DIBUANG'), 'alasan_filter'),
        'ekstraksi': {'total': HasilEkstraksi.objects.count(),
                      **hitung(HasilEkstraksi.objects.all(), 'status_validasi')},
        'galat_ekstraksi': GalatEkstraksi.objects.count(),
        'cluster': {'total': Cluster.objects.count(), **hitung(Cluster.objects.all(), 'status_cluster')},
    })


@api_view(roles=ROLE_BACA)
def ulasan_list(request):
    """GET /api/v1/ulasan/?aplikasi=<package>&filter=LOLOS|DIBUANG&halaman=&ukuran="""
    qs = (Ulasan.objects.select_related('aplikasi')
          .prefetch_related('hasil_ekstraksi_set__cluster_set', 'galat_ekstraksi_set').order_by('-id'))
    if request.GET.get('aplikasi'):
        qs = qs.filter(aplikasi__package_name=request.GET['aplikasi'])
    if request.GET.get('filter') in dict(Ulasan.StatusFilter.choices):
        qs = qs.filter(status_filter=request.GET['filter'])
    return _halaman(request, qs, ser_ulasan)


@api_view(roles=ROLE_BACA)
def ekstraksi_list(request):
    """GET /api/v1/ekstraksi/?status=MENUNGGU_VALIDASI&aplikasi=<package>&cluster=<id>"""
    qs = _QS_EKS.order_by('-id')
    st = request.GET.get('status')
    if st:
        if st not in dict(HasilEkstraksi.StatusValidasi.choices):
            raise _Permintaan(f"Nilai 'status' tidak dikenal: {st}.")
        qs = qs.filter(status_validasi=st)
    if request.GET.get('aplikasi'):
        qs = qs.filter(ulasan__aplikasi__package_name=request.GET['aplikasi'])
    if request.GET.get('cluster', '').isdigit():
        qs = qs.filter(cluster_set__cluster_id=int(request.GET['cluster']))
    return _halaman(request, qs, ser_ekstraksi)


@api_view(roles=ROLE_BACA)
def ekstraksi_detail(request, pk):
    """GET /api/v1/ekstraksi/<id>/ — termasuk evidence dan teks ulasan asli."""
    return sukses(ser_ekstraksi(_ambil(HasilEkstraksi, pk, _QS_EKS), detail=True))


@api_view(roles=ROLE_BACA)
def ekstraksi_riwayat(request, pk):
    """GET /api/v1/ekstraksi/<id>/riwayat/ — jejak tindakan validasi."""
    _ambil(HasilEkstraksi, pk)
    logs = LogValidasi.objects.filter(objek_jenis='EKSTRAKSI', objek_id=pk).select_related('pengguna')
    return sukses([ser_log(l) for l in logs], {'total': logs.count()})


@api_view(roles=ROLE_BACA)
def cluster_list(request):
    """GET /api/v1/cluster/?status=MENUNGGU_VALIDASI"""
    qs = _QS_CLU.order_by('-jumlah_anggota', '-id')
    st = request.GET.get('status')
    if st:
        if st not in dict(Cluster.StatusCluster.choices):
            raise _Permintaan(f"Nilai 'status' tidak dikenal: {st}.")
        qs = qs.filter(status_cluster=st)
    return _halaman(request, qs, ser_cluster)


@api_view(roles=ROLE_BACA)
def cluster_detail(request, pk):
    """GET /api/v1/cluster/<id>/ — dengan seluruh anggota (WHO/WHAT/WHY + ulasan sumber)."""
    qs = _QS_CLU.prefetch_related('anggota_set__hasil_ekstraksi__ulasan__aplikasi',
                                  'anggota_set__hasil_ekstraksi__cluster_set')
    return sukses(ser_cluster(_ambil(Cluster, pk, qs), detail=True))


# --------------------------------------------------------------------------- endpoint tulis (Analyst)
@api_view(roles=ROLE_VALIDASI, methods=('POST',))
def ekstraksi_setujui(request, pk):
    """POST /api/v1/ekstraksi/<id>/setujui/  body: {"catatan": "..."} (opsional)"""
    # Service mengembalikan baris yang dikunci (select_for_update) tanpa select_related/prefetch; serializer detail
    # menyentuh ulasan, aplikasi, pengguna, dan cluster_set, jadi dimuat ulang lewat _QS_EKS (1 query) agar
    # tidak terjadi lazy query berulang. Hal yang sama berlaku untuk tolak/perbaiki/cluster di bawah.
    he = validation.setujui_ekstraksi(_ambil(HasilEkstraksi, pk), request.user, _body(request).get('catatan', ''))
    return sukses(ser_ekstraksi(_ambil(HasilEkstraksi, he.pk, _QS_EKS), detail=True))


@api_view(roles=ROLE_VALIDASI, methods=('POST',))
def ekstraksi_tolak(request, pk):
    """POST /api/v1/ekstraksi/<id>/tolak/  body: {"alasan": "..."} (opsional)"""
    he = validation.tolak_ekstraksi(_ambil(HasilEkstraksi, pk), request.user, _body(request).get('alasan', ''))
    return sukses(ser_ekstraksi(_ambil(HasilEkstraksi, he.pk, _QS_EKS), detail=True))


@api_view(roles=ROLE_VALIDASI, methods=('POST',))
def ekstraksi_perbaiki(request, pk):
    """POST /api/v1/ekstraksi/<id>/perbaiki/  body: {"who":..., "what":..., "why":..., "catatan":...} (sebagian boleh)"""
    b = _body(request)
    for k in ('who', 'what', 'why'):
        if k in b and not isinstance(b[k], str):
            raise _Permintaan(f"Field '{k}' harus berupa teks.")
    he = validation.perbaiki_ekstraksi(_ambil(HasilEkstraksi, pk), request.user, who=b.get('who'),
                                       what=b.get('what'), why=b.get('why'), catatan=b.get('catatan', ''))
    return sukses(ser_ekstraksi(_ambil(HasilEkstraksi, he.pk, _QS_EKS), detail=True))


@api_view(roles=ROLE_VALIDASI, methods=('POST',))
def cluster_setujui(request, pk):
    """POST /api/v1/cluster/<id>/setujui/"""
    c = validation.setujui_cluster(_ambil(Cluster, pk), request.user)
    return sukses(ser_cluster(_ambil(Cluster, c.pk, _QS_CLU)))


@api_view(roles=ROLE_VALIDASI, methods=('POST',))
def cluster_tolak(request, pk):
    """POST /api/v1/cluster/<id>/tolak/  body: {"alasan": "..."} (opsional)"""
    c = validation.tolak_cluster(_ambil(Cluster, pk), request.user, _body(request).get('alasan', ''))
    return sukses(ser_cluster(_ambil(Cluster, c.pk, _QS_CLU)))
