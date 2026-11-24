"""Uji klien LLM kampus (kompatibel OpenAI) tanpa jaringan: HTTP dipalsukan."""
import pytest

from extraction.services.llm import LLMConfigError, LLMError, LLMResponseError, OpenAICompatClient
from extraction.services.llm.client import bersihkan_json_teks

SKEMA = {'type': 'object', 'properties': {'a': {'type': 'string'}}, 'required': ['a']}


class _R:
    def __init__(self, kode, data=None, text=''):
        self.status_code, self._d, self.text = kode, data, text

    def json(self):
        return self._d


def _chat(isi):
    return _R(200, {'choices': [{'message': {'content': isi}}]})


class _Http:
    def __init__(self, urutan):
        self.urutan, self.panggilan = list(urutan), []

    def post(self, url, json=None, timeout=None, headers=None):
        self.panggilan.append((url, json, timeout))
        item = self.urutan.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _klien(http, **kw):
    return OpenAICompatClient(base_url='http://x/v1/', model='gemma4:12b', http=http,
                              tidur=lambda s: None, **kw)


def test_generate_json_dan_url():
    http = _Http([_chat('{"a": "b"}')])
    assert _klien(http).generate_json('p', SKEMA, system_instruction='s') == {'a': 'b'}
    url, payload, timeout = http.panggilan[0]
    assert url == 'http://x/v1/chat/completions'
    assert payload['messages'][0] == {'role': 'system', 'content': 's'}
    assert payload['response_format']['type'] == 'json_schema' and timeout == 180.0


def test_fallback_json_object_saat_400():
    http = _Http([_R(400, text='unsupported'), _chat('{"a": "b"}')])
    k = _klien(http)
    assert k.generate_json('p', SKEMA) == {'a': 'b'}
    assert http.panggilan[1][1]['response_format'] == {'type': 'json_object'}
    assert 'skema' in http.panggilan[1][1]['messages'][-1]['content']


def test_bersihkan_think_dan_pagar():
    assert bersihkan_json_teks('<think>hmm</think>\n```json\n{"a":"b"}\n```') == '{"a":"b"}'


def test_json_rusak():
    with pytest.raises(LLMResponseError):
        _klien(_Http([_chat('bukan json')])).generate_json('p', SKEMA)


def test_retry_5xx_lalu_berhasil():
    http = _Http([_R(503), _chat('{"a": "b"}')])
    assert _klien(http).generate_json('p', SKEMA) == {'a': 'b'}
    assert len(http.panggilan) == 2


def test_auth_tidak_diulang():
    http = _Http([_R(401)])
    with pytest.raises(LLMConfigError):
        _klien(http).generate_json('p', SKEMA)
    assert len(http.panggilan) == 1


def test_embed_tanpa_model_menolak_jelas():
    with pytest.raises(LLMConfigError):
        _klien(_Http([])).embed(['a'])


def test_embed_urut_index():
    data = {'data': [{'index': 1, 'embedding': [0, 1]}, {'index': 0, 'embedding': [1, 0]}]}
    http = _Http([_R(200, data)])
    assert _klien(http, embedding_model='bge-m3').embed(['a', 'b']) == [[1, 0], [0, 1]]


def test_konfigurasi_wajib():
    with pytest.raises(LLMConfigError):
        OpenAICompatClient(base_url='', model='m')


def test_ekstraktor_kampus_terdaftar(settings):
    settings.LLM_KAMPUS = {**settings.LLM_KAMPUS, 'base_url': 'http://x/v1'}
    from extraction.services.registry import get_ekstraktor
    e = get_ekstraktor('kampus')
    assert e.nama == 'kampus' and e.batch_llm == settings.LLM_KAMPUS['batch_llm'] and e.model


def test_health(client):
    assert client.get('/health').json() == {'status': 'ok'}


def test_mode_turun_dipertahankan_bila_json_object_berhasil():
    http = _Http([_R(400, text='unsupported'), _chat('{"a": "1"}'), _chat('{"a": "2"}')])
    k = _klien(http)
    k.generate_json('p', SKEMA)
    k.generate_json('p', SKEMA)
    assert [c[1]['response_format']['type'] for c in http.panggilan] == ['json_schema', 'json_object', 'json_object']


def test_mode_dikembalikan_bila_400_bukan_karena_json_schema():
    http = _Http([_R(400, text='prompt terlalu panjang'), _R(400, text='prompt terlalu panjang'),
                  _chat('{"a": "ok"}')])
    k = _klien(http)
    with pytest.raises(LLMError):
        k.generate_json('p', SKEMA)
    assert k._mode_json == 'json_schema'
    assert k.generate_json('p', SKEMA) == {'a': 'ok'}
    assert http.panggilan[-1][1]['response_format']['type'] == 'json_schema'
