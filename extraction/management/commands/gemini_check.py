"""Uji koneksi Gemini: `python manage.py gemini_check [--list-models]`."""
from django.core.management.base import BaseCommand, CommandError

from extraction.services.llm import LLMError, get_llm_client

SKEMA_UJI = {
    'type': 'object',
    'properties': {'balasan': {'type': 'string'}},
    'required': ['balasan'],
}


class Command(BaseCommand):
    help = 'Uji kunci API dan model Gemini dengan satu permintaan kecil.'

    def add_arguments(self, parser):
        parser.add_argument('--list-models', action='store_true', help='Tampilkan model yang tersedia untuk kunci ini.')

    def handle(self, *args, **opts):
        try:
            klien = get_llm_client()
            if opts['list_models']:
                for nama in klien.daftar_model():
                    self.stdout.write(nama)
                return
            hasil = klien.generate_json('Balas dengan JSON: {"balasan": "halo"}', SKEMA_UJI)
        except LLMError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'OK: model {klien.model} merespons: {hasil}'))
