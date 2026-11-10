"""Perhitungan metrik ringkas untuk Dashboard Overview."""
from django.db.models import Avg, Count, Max

from backlog.models import BacklogItem
from extraction.models import Cluster, HasilEkstraksi
from reviews.models import Aplikasi, Ulasan
from stories.models import UserStory


def _persen(nilai, total):
    if not total:
        return 0.0
    return round((nilai / total) * 100, 1)


def ringkasan_dashboard():
    total_ulasan = Ulasan.objects.count()
    ulasan_dibuang = Ulasan.objects.filter(
        status_filter=Ulasan.StatusFilter.DIBUANG
    ).count()
    total_ekstraksi = HasilEkstraksi.objects.count()

    rata_confidence = (
        HasilEkstraksi.objects.aggregate(rata=Avg('skor_confidence'))['rata']
        or 0
    )

    status_cluster = {
        row['status_cluster']: row['jumlah']
        for row in Cluster.objects.values('status_cluster').annotate(
            jumlah=Count('id')
        )
    }
    status_story = {
        row['status_persetujuan']: row['jumlah']
        for row in UserStory.objects.values('status_persetujuan').annotate(
            jumlah=Count('id')
        )
    }
    status_backlog = {
        row['status_eksekusi']: row['jumlah']
        for row in BacklogItem.objects.values('status_eksekusi').annotate(
            jumlah=Count('id')
        )
    }

    top_clusters = list(
        Cluster.objects.order_by('-jumlah_anggota', '-tanggal_dibuat')[:5]
    )

    aplikasi = list(
        Aplikasi.objects.annotate(
            rata_rating=Avg('ulasan_set__skor_bintang'),
            jumlah_ulasan=Count('ulasan_set'),
        ).order_by('nama_aplikasi')
    )

    ulasan_terakhir = Ulasan.objects.aggregate(
        terakhir=Max('tanggal_scraping')
    )['terakhir']
    ekstraksi_terakhir = HasilEkstraksi.objects.aggregate(
        terakhir=Max('tanggal_ekstraksi')
    )['terakhir']

    return {
        'total_ulasan': total_ulasan,
        'ulasan_lolos': Ulasan.objects.filter(
            status_filter=Ulasan.StatusFilter.LOLOS
        ).count(),
        'ulasan_dibuang': ulasan_dibuang,
        'filtered_noise_rate': _persen(ulasan_dibuang, total_ulasan),
        'total_ekstraksi': total_ekstraksi,
        'total_cluster': Cluster.objects.count(),
        'cluster_menunggu_validasi': status_cluster.get(
            Cluster.StatusCluster.MENUNGGU_VALIDASI, 0
        ),
        'cluster_tervalidasi': status_cluster.get(
            Cluster.StatusCluster.TERVALIDASI, 0
        ),
        'total_user_story': UserStory.objects.count(),
        'story_menunggu': status_story.get(
            UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN, 0
        ),
        'story_disetujui': status_story.get(
            UserStory.StatusPersetujuan.DISETUJUI, 0
        ),
        'story_diabaikan': status_story.get(
            UserStory.StatusPersetujuan.DIABAIKAN, 0
        ),
        'model_confidence_score': round(float(rata_confidence) * 100, 1),
        'backlog_total': BacklogItem.objects.count(),
        'backlog_siap': status_backlog.get(
            BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI, 0
        ),
        'backlog_dikerjakan': status_backlog.get(
            BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN, 0
        ),
        'backlog_selesai': status_backlog.get(
            BacklogItem.StatusEksekusi.SELESAI, 0
        ),
        'top_clusters': top_clusters,
        'aplikasi': aplikasi,
        'ulasan_terakhir': ulasan_terakhir,
        'ekstraksi_terakhir': ekstraksi_terakhir,
    }
