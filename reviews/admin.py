from django.contrib import admin
from .models import Aplikasi, Ulasan

@admin.register(Aplikasi)
class AplikasiAdmin(admin.ModelAdmin):
    list_display = ('nama_aplikasi', 'package_name', 'aktif')

@admin.register(Ulasan)
class UlasanAdmin(admin.ModelAdmin):
    list_display = ('aplikasi', 'skor_bintang', 'status_filter', 'alasan_filter', 'tanggal_ulasan')
    list_filter = ('status_filter', 'alasan_filter', 'aplikasi')
