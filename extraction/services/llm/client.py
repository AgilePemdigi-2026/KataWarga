"""
Klien Gemini dengan timeout, retry (backoff), dan pembatas laju permintaan.

Prinsip:
- Kunci API hanya dari settings.LLM['api_key'] (environment variable GEMINI_API_KEY).
- Seluruh error SDK diterjemahkan ke hierarki `LLMError`, sehingga pemanggil
  (ekstraktor, clustering) tidak bergantung pada detail SDK dan dapat melakukan
  degradasi anggun (graceful degradation).
- `generate_json` meminta keluaran JSON terstruktur (response_mime_type + schema).
  Sintaks JSON dijamin oleh API, kebenaran ISI tidak: validasi tetap tugas pemanggil.
"""
import json
import logging
import random
import re
import threading
import time

from django.conf import settings

logger = logging.getLogger('extraction.llm')


class LLMError(Exception):
    """Dasar semua error integrasi LLM."""


class LLMConfigError(LLMError):
    """Konfigurasi belum lengkap (mis. GEMINI_API_KEY kosong) atau SDK tidak terpasang."""


class LLMTimeoutError(LLMError):
    """Permintaan melewati batas waktu setelah seluruh percobaan ulang."""


class LLMRateLimitError(LLMError):
    """Kuota/rate limit (HTTP 429) tetap terlampaui setelah seluruh percobaan ulang."""


class LLMResponseError(LLMError):
    """Respons kosong, diblokir, atau bukan JSON yang valid."""


class _PembatasLaju:
    """Menjaga jarak minimal antar-permintaan agar tidak melewati kuota RPM."""

    def __init__(self, rpm, jam=time.monotonic, tidur=time.sleep):
        self.jeda = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._jam, self._tidur = jam, tidur
        self._terakhir = None
        self._kunci = threading.Lock()

    def tunggu(self):
        with self._kunci:
            if self._terakhir is not None and self.jeda:
                sisa = self.jeda - (self._jam() - self._terakhir)
                if sisa > 0:
                    self._tidur(sisa)
            self._terakhir = self._jam()


class GeminiClient:
    def __init__(self, *, api_key, model, timeout_detik=60.0, max_retry=4, backoff_dasar_detik=2.0,
                 rpm=10, temperature=0.0, sdk_client=None, tidur=time.sleep, jam=time.monotonic):
        if not api_key and sdk_client is None:
            raise LLMConfigError(
                'GEMINI_API_KEY belum diisi. Buat kunci di https://aistudio.google.com/apikey '
                'lalu isi di file .env (jangan commit).')
        self.model = model
        self.timeout_detik = timeout_detik
        self.max_retry = max_retry
        self.backoff_dasar = backoff_dasar_detik
        self.temperature = temperature
        self._api_key = api_key
        self._sdk = sdk_client
        self._tidur = tidur
        self._pembatas = _PembatasLaju(rpm, jam=jam, tidur=tidur)

    # -- SDK -----------------------------------------------------------------
    def _sdk_client(self):
        if self._sdk is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError as exc:
                raise LLMConfigError("Paket 'google-genai' belum terpasang (pip install -r requirements/base.txt).") from exc
            # http_options.timeout dalam milidetik
            self._sdk = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout_detik * 1000)),
            )
        return self._sdk

    def _panggil_sdk(self, prompt, schema, system_instruction):
        from google.genai import types
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            system_instruction=system_instruction,
            response_mime_type='application/json',
            response_json_schema=schema,
        )
        return self._sdk_client().models.generate_content(
            model=self.model, contents=prompt, config=config)

    # -- Klasifikasi error ---------------------------------------------------
    @staticmethod
    def _kode_http(exc):
        kode = getattr(exc, 'code', None)
        return kode if isinstance(kode, int) else None

    @staticmethod
    def _timeout(exc):
        nama = type(exc).__name__.lower()
        return 'timeout' in nama or isinstance(exc, TimeoutError)

    def _terjemahkan(self, exc):
        """Kembalikan (bisa_diulang, error_akhir)."""
        kode = self._kode_http(exc)
        if self._timeout(exc):
            return True, LLMTimeoutError(f'Permintaan ke LLM melewati {self.timeout_detik:g} detik.')
        if kode == 429:
            return True, LLMRateLimitError('Kuota/rate limit Gemini terlampaui (429). Cek kuota di AI Studio.')
        if kode is not None and kode >= 500:
            return True, LLMError(f'Layanan Gemini bermasalah (HTTP {kode}).')
        if kode in (401, 403):
            return False, LLMConfigError(f'Kunci API ditolak (HTTP {kode}). Periksa GEMINI_API_KEY.')
        if kode is not None and 400 <= kode < 500:
            return False, LLMError(f'Permintaan ditolak Gemini (HTTP {kode}): {exc}')
        return False, LLMError(f'{type(exc).__name__}: {exc}')

    def _backoff(self, percobaan):
        return self.backoff_dasar * (2 ** percobaan) + random.uniform(0, 0.5)

    # -- API publik ----------------------------------------------------------
    def _dengan_retry(self, panggil):
        """Jalankan `panggil()` dengan pembatas laju, retry+backoff, dan terjemahan error ke LLMError."""
        terakhir = None
        for percobaan in range(self.max_retry + 1):
            self._pembatas.tunggu()
            try:
                return panggil()
            except LLMConfigError:
                raise
            except Exception as exc:  # error SDK/jaringan -> hierarki LLMError
                bisa_diulang, terakhir = self._terjemahkan(exc)
                if not bisa_diulang:
                    raise terakhir from exc
                if percobaan < self.max_retry:
                    jeda = self._backoff(percobaan)
                    logger.warning('LLM gagal (%s); ulang %d/%d dalam %.1f detik',
                                   type(terakhir).__name__, percobaan + 1, self.max_retry, jeda)
                    self._tidur(jeda)
        raise terakhir

    def generate_json(self, prompt, schema, *, system_instruction=None):
        """Kirim prompt, kembalikan hasil JSON yang sudah di-parse (dict/list)."""
        respons = self._dengan_retry(lambda: self._panggil_sdk(prompt, schema, system_instruction))
        return self._parse(respons)

    def embed(self, teks_list, *, model=None, dimensi=None, task_type='CLUSTERING'):
        """
        Kembalikan list vektor (list[float]) sejajar dengan `teks_list`.
        Vektor dengan dimensi < dimensi penuh model harus dinormalisasi oleh pemanggil.
        """
        if not teks_list:
            return []
        respons = self._dengan_retry(lambda: self._panggil_embed(list(teks_list), model, dimensi, task_type))
        vektor = [list(e.values) for e in getattr(respons, 'embeddings', None) or []]
        if len(vektor) != len(teks_list):
            raise LLMResponseError(
                f'Jumlah embedding ({len(vektor)}) tidak sama dengan jumlah teks ({len(teks_list)}).')
        return vektor

    def _panggil_embed(self, teks_list, model, dimensi, task_type):
        from google.genai import types
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=dimensi)
        return self._sdk_client().models.embed_content(
            model=model or settings.LLM.get('embedding_model'), contents=teks_list, config=config)

    @staticmethod
    def _parse(respons):
        teks = getattr(respons, 'text', None)
        if not teks or not teks.strip():
            raise LLMResponseError('Respons Gemini kosong (mungkin diblokir filter keamanan).')
        try:
            return json.loads(teks)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f'Respons bukan JSON valid: {exc}') from exc

    def daftar_model(self):
        """Nama model yang dapat dipakai kunci ini (untuk perintah gemini_check)."""
        return sorted(m.name for m in self._sdk_client().models.list())


class _HTTPGagal(Exception):
    """Respons HTTP non-2xx dari server LLM; `code` dipakai klasifikasi retry."""

    def __init__(self, code, pesan=''):
        super().__init__(f'HTTP {code}: {pesan}'[:500])
        self.code = code


_RE_THINK = re.compile(r'<think>.*?</think>', re.DOTALL)
_RE_PAGAR = re.compile(r'^\s*```(?:json)?\s*|\s*```\s*$')


def bersihkan_json_teks(teks):
    """Buang blok <think>…</think> (qwen3, dll.) dan pagar ```json yang kadang membungkus keluaran model lokal."""
    teks = _RE_THINK.sub('', teks or '').strip()
    return _RE_PAGAR.sub('', teks).strip()


class OpenAICompatClient(GeminiClient):
    """
    Klien untuk server LLM kompatibel OpenAI (mis. Ollama di server kampus, docs/server-aorus.md).
    Antarmuka sama dengan GeminiClient (generate_json, embed), sehingga ekstraktor tidak peduli penyedianya.

    - Konfigurasi dari env: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (nama baku dari dokumen server).
    - Tidak ada pembatas laju lokal (server memakai antrean GPU bersama); timeout panjang.
    - Keluaran JSON: coba `json_schema`; bila server menolak (400), turun ke `json_object` dengan skema
      disisipkan ke prompt. Isi tetap divalidasi verifikasi.py.
    """

    def __init__(self, *, base_url, api_key='ollama', model, timeout_detik=180.0, max_retry=3,
                 backoff_dasar_detik=5.0, temperature=0.0, embedding_model='', http=None,
                 tidur=time.sleep, jam=time.monotonic):
        if not base_url or not model:
            raise LLMConfigError('LLM_BASE_URL dan LLM_MODEL wajib diisi untuk penyedia LLM kampus.')
        super().__init__(api_key=api_key or 'ollama', model=model, timeout_detik=timeout_detik,
                         max_retry=max_retry, backoff_dasar_detik=backoff_dasar_detik, rpm=0,
                         temperature=temperature, sdk_client=object(), tidur=tidur, jam=jam)
        self.base_url = base_url.rstrip('/')
        self.embedding_model = embedding_model
        self._http = http
        self._mode_json = 'json_schema'

    def _post(self, jalur, payload):
        http = self._http
        if http is None:
            import requests
            http = requests
        r = http.post(f'{self.base_url}{jalur}', json=payload, timeout=self.timeout_detik,
                      headers={'Authorization': f'Bearer {self._api_key}'})
        if r.status_code >= 400:
            raise _HTTPGagal(r.status_code, (getattr(r, 'text', '') or '')[:300])
        return r.json()

    def _panggil_sdk(self, prompt, schema, system_instruction):
        pesan = []
        if system_instruction:
            pesan.append({'role': 'system', 'content': system_instruction})
        payload = {'model': self.model, 'temperature': self.temperature, 'stream': False}
        if self._mode_json == 'json_schema':
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'hasil', 'schema': schema, 'strict': True}}
            pesan.append({'role': 'user', 'content': prompt})
        else:
            payload['response_format'] = {'type': 'json_object'}
            pesan.append({'role': 'user', 'content': (
                f'{prompt}\n\nJawab HANYA dengan JSON yang sesuai skema ini:\n{json.dumps(schema)}')})
        payload['messages'] = pesan
        try:
            return self._post('/chat/completions', payload)
        except _HTTPGagal as exc:
            if exc.code == 400 and self._mode_json == 'json_schema':
                # Turun ke json_object hanya untuk percobaan ini. Mode baru DIPERTAHANKAN (agar request berikutnya
                # tidak selalu gagal dulu) hanya bila percobaan itu berhasil; bila 400 ternyata disebabkan hal
                # lain (mis. prompt terlalu panjang), mode semula dikembalikan.
                logger.warning('server menolak json_schema; mencoba json_object')
                self._mode_json = 'json_object'
                try:
                    return self._panggil_sdk(prompt, schema, system_instruction)
                except Exception:
                    self._mode_json = 'json_schema'
                    raise
            raise

    @staticmethod
    def _parse(respons):
        try:
            teks = respons['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError('Respons server LLM tidak berbentuk chat completion.') from exc
        teks = bersihkan_json_teks(teks)
        if not teks:
            raise LLMResponseError('Respons server LLM kosong.')
        try:
            return json.loads(teks)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f'Respons bukan JSON valid: {exc}') from exc

    def generate_json(self, prompt, schema, *, system_instruction=None):
        respons = self._dengan_retry(lambda: self._panggil_sdk(prompt, schema, system_instruction))
        return self._parse(respons)

    def _terjemahkan(self, exc):
        if isinstance(exc, _HTTPGagal) and exc.code in (401, 403):
            return False, LLMConfigError(f'Server LLM menolak kunci (HTTP {exc.code}). Periksa LLM_API_KEY.')
        if isinstance(exc, _HTTPGagal) and exc.code == 404:
            return False, LLMConfigError(f'Model/endpoint tidak ditemukan di server (404): {exc}. Periksa LLM_MODEL.')
        nama = type(exc).__name__
        if nama in ('ConnectionError', 'ConnectTimeout') or 'ConnectionError' in nama:
            return True, LLMError('Server LLM tidak terjangkau. Endpoint kampus hanya bisa diakses dari aplikasi '
                                  'yang di-deploy di server (bukan dari laptop).')
        return super()._terjemahkan(exc)

    def embed(self, teks_list, *, model=None, dimensi=None, task_type='CLUSTERING'):
        if not teks_list:
            return []
        nama = model if (model and not str(model).startswith('gemini')) else self.embedding_model
        if not nama:
            raise LLMConfigError('Server LLM kampus belum punya model embedding (LLM_EMBED_MODEL kosong). '
                                 'Minta dosen memasang model embedding, atau pakai embedding Gemini.')
        respons = self._dengan_retry(lambda: self._post('/embeddings', {'model': nama, 'input': list(teks_list)}))
        vektor = [d['embedding'] for d in sorted(respons.get('data', []), key=lambda d: d.get('index', 0))]
        if len(vektor) != len(teks_list):
            raise LLMResponseError(
                f'Jumlah embedding ({len(vektor)}) tidak sama dengan jumlah teks ({len(teks_list)}).')
        return vektor

    def daftar_model(self):
        import requests
        r = requests.get(f'{self.base_url}/models', timeout=self.timeout_detik,
                         headers={'Authorization': f'Bearer {self._api_key}'})
        r.raise_for_status()
        return sorted(m['id'] for m in r.json().get('data', []))


def get_llm_client(provider=None, **override):
    provider = provider or settings.LLM.get('provider', 'gemini')
    if provider == 'kampus':
        cfg = {**settings.LLM_KAMPUS, **override}
        return OpenAICompatClient(
            base_url=cfg['base_url'], api_key=cfg['api_key'], model=cfg['model'],
            timeout_detik=cfg['timeout_detik'], max_retry=cfg['max_retry'],
            backoff_dasar_detik=cfg['backoff_dasar_detik'], temperature=cfg['temperature'],
            embedding_model=cfg.get('embedding_model', ''), http=cfg.get('http'))
    cfg = {**settings.LLM, **override}
    return GeminiClient(
        api_key=cfg['api_key'], model=cfg['model'], timeout_detik=cfg['timeout_detik'],
        max_retry=cfg['max_retry'], backoff_dasar_detik=cfg['backoff_dasar_detik'],
        rpm=cfg['rpm'], temperature=cfg['temperature'], sdk_client=cfg.get('sdk_client'))
