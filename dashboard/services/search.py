"""Pencarian global yang dibatasi peran efektif (RBAC)."""
import re

from django.db.models import Q
from django.urls import reverse

from accounts.models import User
from backlog.models import BacklogItem
from extraction.models import Cluster
from reviews.models import Ulasan
from stories.models import UserStory


MAKS_ITEM = 6


def _rapikan(teks, maks=180):
    teks = re.sub(r"\s+", " ", str(teks or "")).strip()
    if len(teks) <= maks:
        return teks
    return teks[: maks - 1].rstrip() + "…"


def _grup(key, label, icon, queryset, pembuat_item):
    total = queryset.count()
    items = [pembuat_item(obj) for obj in queryset[:MAKS_ITEM]]
    return {
        "key": key,
        "label": label,
        "icon": icon,
        "total": total,
        "items": items,
    }


def cari_global(query, role):
    """Kembalikan (groups, total). Tidak ada hasil dummy."""
    query = (query or "").strip()
    if len(query) < 2:
        return [], 0

    groups = []

    if role in (
        User.RolePengguna.REQUIREMENTS_ENGINEER,
        User.RolePengguna.ANALYST,
    ):
        ulasan = (
            Ulasan.objects
            .select_related("aplikasi")
            .filter(
                Q(isi_ulasan__icontains=query)
                | Q(username_reviewer__icontains=query)
                | Q(aplikasi__nama_aplikasi__icontains=query)
            )
            .order_by("-tanggal_ulasan", "-id")
        )
        groups.append(_grup(
            "reviews",
            "Ulasan",
            "icon-inbox",
            ulasan,
            lambda obj: {
                "title": f"{obj.aplikasi.nama_aplikasi} · {obj.tanggal_ulasan:%d %b %Y}",
                "snippet": _rapikan(obj.isi_ulasan),
                "meta": (
                    f"{obj.skor_bintang}★ · {obj.get_status_filter_display()}"
                    + (f" · {obj.username_reviewer}" if obj.username_reviewer else "")
                ),
                "url": f"{reverse('extraction:pipeline')}?q={query}",
                "icon": "icon-inbox",
            },
        ))

        cluster = (
            Cluster.objects
            .filter(nama_topik__icontains=query)
            .order_by("-jumlah_anggota", "-tanggal_dibuat")
        )
        groups.append(_grup(
            "clusters",
            "Cluster",
            "icon-clustering",
            cluster,
            lambda obj: {
                "title": obj.nama_topik,
                "snippet": _rapikan(
                    f"{obj.jumlah_anggota} ulasan anggota · skor signifikansi "
                    f"{obj.skor_signifikansi}"
                ),
                "meta": obj.get_status_cluster_display(),
                "url": reverse("extraction:cluster_detail", args=[obj.pk]),
                "icon": "icon-clustering",
            },
        ))

    if role in (
        User.RolePengguna.REQUIREMENTS_ENGINEER,
        User.RolePengguna.PRODUCT_OWNER,
        User.RolePengguna.TIM_DEVELOPER,
    ):
        cerita = (
            UserStory.objects
            .select_related("cluster")
            .filter(
                Q(peran__icontains=query)
                | Q(kebutuhan__icontains=query)
                | Q(alasan__icontains=query)
                | Q(cluster__nama_topik__icontains=query)
            )
            .distinct()
            .order_by("-skor_prioritas", "-tanggal_disusun")
        )
        groups.append(_grup(
            "stories",
            "User Story",
            "icon-stories",
            cerita,
            lambda obj: {
                "title": f"User Story #{obj.pk} · {obj.cluster.nama_topik}",
                "snippet": _rapikan(obj.kalimat),
                "meta": (
                    f"{obj.get_status_persetujuan_display()} · "
                    f"prioritas {obj.get_kategori_prioritas_display()} · "
                    f"skor {obj.skor_prioritas}"
                ),
                "url": reverse("stories:detail", args=[obj.pk]),
                "icon": "icon-stories",
            },
        ))

    if role in (
        User.RolePengguna.PRODUCT_OWNER,
        User.RolePengguna.TIM_DEVELOPER,
    ):
        backlog = (
            BacklogItem.objects
            .select_related("user_story", "user_story__cluster")
            .filter(
                Q(user_story__peran__icontains=query)
                | Q(user_story__kebutuhan__icontains=query)
                | Q(user_story__alasan__icontains=query)
                | Q(user_story__cluster__nama_topik__icontains=query)
            )
            .distinct()
            .order_by("-user_story__skor_prioritas", "-tanggal_masuk_backlog")
        )
        groups.append(_grup(
            "backlog",
            "Sprint Backlog",
            "icon-backlog",
            backlog,
            lambda obj: {
                "title": f"Backlog #{obj.pk} · {obj.user_story.cluster.nama_topik}",
                "snippet": _rapikan(obj.user_story.kalimat),
                "meta": obj.get_status_eksekusi_display(),
                "url": reverse("backlog:detail", args=[obj.pk]),
                "icon": "icon-backlog",
            },
        ))

    groups = [group for group in groups if group["total"]]
    total = sum(group["total"] for group in groups)
    return groups, total
