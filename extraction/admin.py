from django.contrib import admin
from .models import HasilEkstraksi, Cluster, ClusterAnggota

@admin.register(HasilEkstraksi)
class HasilEkstraksiAdmin(admin.ModelAdmin):
    list_display = ('ulasan', 'teks_what', 'status_validasi')

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('nama_topik', 'jumlah_anggota', 'status_cluster')

@admin.register(ClusterAnggota)
class ClusterAnggotaAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'hasil_ekstraksi')
