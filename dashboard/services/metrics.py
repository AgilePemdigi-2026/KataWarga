"""Perhitungan metrik ringkas untuk Dashboard Overview."""
from datetime import date

from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from backlog.models import BacklogItem
from extraction.models import Cluster, HasilEkstraksi
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


NAMA_BULAN = (
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
)


def _persen(nilai, total):
    if not total:
        return 0.0
    return round((nilai / total) * 100, 1)


def _bulan_terakhir(jumlah=6):
    """Kembalikan enam bulan terakhir (termasuk bulan berjalan) secara kronologis."""
    hari_ini = timezone.localdate()
    bulan = []
    tahun, nomor_bulan = hari_ini.year, hari_ini.month

    for _ in range(jumlah):
        bulan.append((tahun, nomor_bulan))
        nomor_bulan -= 1
        if nomor_bulan == 0:
            nomor_bulan = 12
            tahun -= 1

    return list(reversed(bulan))


def _rentang_bulan(tahun, bulan):
    mulai = date(tahun, bulan, 1)
    if bulan == 12:
        selesai = date(tahun + 1, 1, 1)
    else:
        selesai = date(tahun, bulan + 1, 1)
    return mulai, selesai


def _data_tren_bulanan():
    """Rata-rata rating ulasan dan jumlah user story per bulan (nyata dari DB)."""
    labels = []
    sentimen = []
    cerita = []

    for tahun, bulan in _bulan_terakhir():
        mulai, selesai = _rentang_bulan(tahun, bulan)
        labels.append(NAMA_BULAN[bulan - 1])

        ulasan_bulan = Ulasan.objects.filter(
            tanggal_ulasan__gte=mulai,
            tanggal_ulasan__lt=selesai,
        )
        agregat = ulasan_bulan.aggregate(
            jumlah=Count("id"),
            rata=Avg("skor_bintang"),
        )
        # Skala sentimen 0–5; bulan tanpa ulasan ditampilkan 0 (bukan data palsu).
        sentimen.append(
            round(float(agregat["rata"]), 2) if agregat["rata"] else 0
        )

        cerita.append(
            UserStory.objects.filter(
                tanggal_disusun__date__gte=mulai,
                tanggal_disusun__date__lt=selesai,
            ).count()
        )

    return {
        "labels": labels,
        "sentiment": sentimen,
        "stories": cerita,
        "has_data": any(sentimen) or any(cerita),
    }


def _distribusi_rating():
    """Distribusi bintang 1–5 per aplikasi dengan satu query agregat."""
    rows = (
        Ulasan.objects
        .filter(skor_bintang__gte=1, skor_bintang__lte=5)
        .values("aplikasi_id", "skor_bintang")
        .annotate(jumlah=Count("id"))
    )
    hasil = {}
    for row in rows:
        app_id = row["aplikasi_id"]
        bintang = int(row["skor_bintang"])
        hasil[(app_id, bintang)] = row["jumlah"]
    return hasil


def ringkasan_dashboard():
    total_ulasan = Ulasan.objects.count()
    ulasan_dibuang = Ulasan.objects.filter(
        status_filter=Ulasan.StatusFilter.DIBUANG
    ).count()
    total_ekstraksi = HasilEkstraksi.objects.count()

    rata_confidence = (
        HasilEkstraksi.objects.aggregate(rata=Avg("skor_confidence"))["rata"]
        or 0
    )

    status_cluster = {
        row["status_cluster"]: row["jumlah"]
        for row in Cluster.objects.values("status_cluster").annotate(
            jumlah=Count("id")
        )
    }
    status_story = {
        row["status_persetujuan"]: row["jumlah"]
        for row in UserStory.objects.values("status_persetujuan").annotate(
            jumlah=Count("id")
        )
    }
    status_backlog = {
        row["status_eksekusi"]: row["jumlah"]
        for row in BacklogItem.objects.values("status_eksekusi").annotate(
            jumlah=Count("id")
        )
    }

    top_clusters = list(
        Cluster.objects.order_by("-jumlah_anggota", "-tanggal_dibuat")[:5]
    )

    aplikasi = list(
        Aplikasi.objects.annotate(
            rata_rating=Avg(
                "ulasan_set__skor_bintang",
                filter=Q(ulasan_set__skor_bintang__gte=1, ulasan_set__skor_bintang__lte=5),
            ),
            jumlah_ulasan=Count("ulasan_set"),
        ).order_by("nama_aplikasi")
    )

    distribusi = _distribusi_rating()
    for app in aplikasi:
        # Rata-rata rating konsisten dengan ulasan valid 1-5 (atau 0.0 jika belum ada rating valid)
        app.rata_rating = round(float(app.rata_rating), 1) if app.rata_rating is not None else 0.0

        # Hitung total ulasan dengan rating valid untuk denominator yang akurat
        bintang_counts = [distribusi.get((app.pk, b), 0) for b in range(1, 6)]
        total_berating = sum(bintang_counts)
        denominator = total_berating if total_berating > 0 else 0

        rincian = []
        for bintang in range(5, 0, -1):
            jumlah = distribusi.get((app.pk, bintang), 0)
            persen = _persen(jumlah, denominator) if denominator > 0 else 0.0
            rincian.append({
                "bintang": bintang,
                "jumlah": jumlah,
                "persen": persen,
                "persen_css": f"{persen:.1f}",
            })
        app.distribusi_bintang = rincian

    ulasan_terakhir = Ulasan.objects.aggregate(
        terakhir=Max("tanggal_scraping")
    )["terakhir"]
    ekstraksi_terakhir = HasilEkstraksi.objects.aggregate(
        terakhir=Max("tanggal_ekstraksi")
    )["terakhir"]

    tren = _data_tren_bulanan()
    max_cerita = max(tren["stories"] or [0])

    return {
        "total_ulasan": total_ulasan,
        "ulasan_lolos": Ulasan.objects.filter(
            status_filter=Ulasan.StatusFilter.LOLOS
        ).count(),
        "ulasan_dibuang": ulasan_dibuang,
        "filtered_noise_rate": _persen(ulasan_dibuang, total_ulasan),
        "total_ekstraksi": total_ekstraksi,
        "total_cluster": Cluster.objects.count(),
        "cluster_menunggu_validasi": status_cluster.get(
            Cluster.StatusCluster.MENUNGGU_VALIDASI, 0
        ),
        "cluster_tervalidasi": status_cluster.get(
            Cluster.StatusCluster.TERVALIDASI, 0
        ),
        "total_user_story": UserStory.objects.count(),
        "story_menunggu": status_story.get(
            UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN, 0
        ),
        "story_disetujui": status_story.get(
            UserStory.StatusPersetujuan.DISETUJUI, 0
        ),
        "story_diabaikan": status_story.get(
            UserStory.StatusPersetujuan.DIABAIKAN, 0
        ),
        "model_confidence_score": round(float(rata_confidence) * 100, 1),
        "backlog_total": BacklogItem.objects.count(),
        "backlog_siap": status_backlog.get(
            BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI, 0
        ),
        "backlog_dikerjakan": status_backlog.get(
            BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN, 0
        ),
        "backlog_selesai": status_backlog.get(
            BacklogItem.StatusEksekusi.SELESAI, 0
        ),
        "top_clusters": top_clusters,
        "aplikasi": aplikasi,
        "ulasan_terakhir": ulasan_terakhir,
        "ekstraksi_terakhir": ekstraksi_terakhir,
        "tren": tren,
        "chart_data": {
            "labels": tren["labels"],
            "series": [
                {
                    "name": "Rata-rata sentimen",
                    "values": tren["sentiment"],
                    "max": 5,
                    "color": "var(--kw-accent)",
                    "unit": "dari 5",
                },
                {
                    "name": "User Story dibuat",
                    "values": tren["stories"],
                    "max": max(max_cerita, 1),
                    "color": "var(--kw-success)",
                    "unit": "story",
                },
            ],
            "aria_label": (
                "Grafik enam bulan terakhir: rata-rata rating ulasan dan "
                "jumlah user story yang dibuat"
            ),
        },
    }
