"""
Ekstraktor user story berbasis Gemini (Sprint 3, bagian C).

Alur per kelompok ulasan (default 50 per permintaan, mengikuti Prasetya et al. 2026):
samarkan PII -> prompt berversi -> Gemini (JSON terstruktur) -> verifikasi tiap objek.
Objek yang gagal verifikasi tidak disimpan; penyebabnya dicatat lewat `ambil_galat()`.
"""
import logging

from django.conf import settings

from extraction.services.base import Ekstraktor
from extraction.services.llm import get_llm_client
from extraction.services.llm.pii import samarkan_pii
from extraction.services.llm.prompt import SKEMA_JSON, SYSTEM_INSTRUCTION, VERSI_PROMPT, susun_prompt
from extraction.services.llm.verifikasi import Ditolak, verifikasi_objek

logger = logging.getLogger('extraction.pipeline')


class VerifikasiGagal(Exception):
    """Model menjawab untuk ulasan ini, tetapi semua objeknya ditolak verifikasi."""


class EkstraktorGemini(Ekstraktor):
    nama = 'gemini'
    versi_prompt = VERSI_PROMPT

    provider = 'gemini'

    def __init__(self, client=None, batch_llm=None):
        self.client = client or get_llm_client(provider=self.provider)
        self.batch_llm = batch_llm or self._batch_default()
        self.model = getattr(self.client, 'model', '') or settings.LLM.get('model', '')
        self._galat = []

    def _batch_default(self):
        return settings.EXTRACTION['batch_llm']

    def ambil_galat(self):
        galat, self._galat = self._galat, []
        return galat

    def ekstrak(self, teks):
        hasil = self.ekstrak_batch([teks])[0]
        if isinstance(hasil, Exception):
            raise hasil
        return hasil

    def ekstrak_batch(self, daftar_teks):
        hasil = []
        for awal in range(0, len(daftar_teks), self.batch_llm):
            hasil.extend(self._satu_permintaan(daftar_teks[awal:awal + self.batch_llm], awal))
        return hasil

    def _satu_permintaan(self, teks_kelompok, offset):
        disamarkan = [samarkan_pii(t) for t in teks_kelompok]
        daftar = [(str(i), t) for i, t in enumerate(disamarkan)]
        try:
            data = self.client.generate_json(
                susun_prompt(daftar), SKEMA_JSON, system_instruction=SYSTEM_INSTRUCTION)
        except Exception as exc:  # error API: seluruh kelompok gagal, bisa dicoba ulang nanti
            logger.error('permintaan LLM gagal (%s ulasan): %s: %s', len(teks_kelompok), type(exc).__name__, exc)
            return [exc] * len(teks_kelompok)

        objek = data.get('userStories') if isinstance(data, dict) else None
        if not isinstance(objek, list):
            exc = ValueError("respons tidak memuat daftar 'userStories'")
            return [exc] * len(teks_kelompok)

        per_ulasan = {str(i): [] for i in range(len(teks_kelompok))}
        ditolak = {str(i): 0 for i in range(len(teks_kelompok))}
        for o in objek:
            rid = str(o.get('review_id')) if isinstance(o, dict) else None
            if rid not in per_ulasan:
                self._galat.append((None, 'review_id_tidak_dikenal', repr(o)[:300]))
                continue
            idx = int(rid)
            try:
                h, catatan = verifikasi_objek(o, disamarkan[idx])
            except Ditolak as d:
                ditolak[rid] += 1
                self._galat.append((offset + idx, d.jenis, d.pesan))
                continue
            if catatan:
                self._galat.append((offset + idx, catatan, f'what: {h.what} | why dibuang: {o.get("why", "")}'))
            if all(h.what.lower() != x.what.lower() for x in per_ulasan[rid]):
                per_ulasan[rid].append(h)

        hasil = []
        for i in range(len(teks_kelompok)):
            rid = str(i)
            if not per_ulasan[rid] and ditolak[rid]:
                hasil.append(VerifikasiGagal(f'{ditolak[rid]} objek ditolak verifikasi'))
            else:
                hasil.append(per_ulasan[rid])
        return hasil


class EkstraktorKampus(EkstraktorGemini):
    """Ekstraktor yang sama (prompt, verifikasi) dengan LLM kampus (OpenAI-compatible). Opsional, berdampingan dengan Gemini."""
    nama = 'kampus'
    provider = 'kampus'

    def _batch_default(self):
        return settings.LLM_KAMPUS['batch_llm']
