from django.contrib import admin
from .models import UserStory

@admin.register(UserStory)
class UserStoryAdmin(admin.ModelAdmin):
    list_display = ('peran', 'kebutuhan', 'kategori_prioritas', 'status_persetujuan', 'skor_prioritas')
    list_filter = ('status_persetujuan', 'kategori_prioritas')
