"""Menyatukan dua cabang migrasi: label topik manual (main) dan kolom LLM/embedding (Sprint 3 Ega)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('extraction', '0002_cluster_nama_topik_manual'),
        ('extraction', '0004_embedding_dan_representatif'),
    ]

    operations = []
