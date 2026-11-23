from django.contrib import admin
from .models import HasilEkstraksi, Cluster, ClusterAnggota

@admin.register(HasilEkstraksi)
class HasilEkstraksiAdmin(admin.ModelAdmin):
    list_display = ('ulasan', 'teks_what', 'status_validasi')

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('nama_topik', 'nama_topik_manual', 'jumlah_anggota', 'status_cluster')
    list_filter = ('status_cluster', 'nama_topik_manual')
    fields = ('nama_topik', 'nama_topik_manual', 'jumlah_anggota', 'skor_signifikansi', 'status_cluster')

    def save_model(self, request, obj, form, change):
        if change and 'nama_topik' in form.changed_data:
            obj.nama_topik_manual = True
        super().save_model(request, obj, form, change)

@admin.register(ClusterAnggota)
class ClusterAnggotaAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'hasil_ekstraksi')
