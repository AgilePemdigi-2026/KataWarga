from django.contrib import admin
from .models import Cluster, ClusterAnggota, GalatEkstraksi, HasilEkstraksi


@admin.register(HasilEkstraksi)
class HasilEkstraksiAdmin(admin.ModelAdmin):
    list_display = ('id', 'ulasan', 'teks_who', 'teks_what', 'teks_why', 'skor_confidence',
                    'nama_ekstraktor', 'versi_prompt', 'status_validasi')
    list_filter = ('nama_ekstraktor', 'versi_prompt', 'status_validasi', 'sentimen')
    search_fields = ('teks_what', 'teks_why', 'evidence', 'kalimat_user_story', 'ulasan__isi_ulasan')
    readonly_fields = ('kalimat_user_story', 'evidence', 'evidence_why', 'sentimen', 'nama_ekstraktor', 'model_llm', 'versi_prompt')


@admin.register(GalatEkstraksi)
class GalatEkstraksiAdmin(admin.ModelAdmin):
    list_display = ('id', 'tanggal', 'jenis', 'nama_ekstraktor', 'versi_prompt', 'ulasan', 'pesan')
    list_filter = ('jenis', 'nama_ekstraktor', 'versi_prompt')
    search_fields = ('pesan', 'ulasan__isi_ulasan')


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('nama_topik', 'nama_topik_manual', 'jumlah_anggota', 'rata_jarak', 'metode', 'ambang_jarak',
                    'status_cluster')
    list_filter = ('status_cluster', 'metode', 'nama_topik_manual')
    search_fields = ('nama_topik',)
    fields = ('nama_topik', 'nama_topik_manual', 'jumlah_anggota', 'skor_signifikansi', 'status_cluster',
              'representatif', 'metode', 'ambang_jarak', 'rata_jarak')
    readonly_fields = ('representatif', 'metode', 'ambang_jarak', 'rata_jarak')

    def save_model(self, request, obj, form, change):
        if change and 'nama_topik' in form.changed_data:
            obj.nama_topik_manual = True
        super().save_model(request, obj, form, change)


@admin.register(ClusterAnggota)
class ClusterAnggotaAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'hasil_ekstraksi')
