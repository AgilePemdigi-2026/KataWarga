"""Uji klien Gemini tanpa jaringan: SDK dipalsukan (mock)."""
import pytest

from extraction.services.llm import (
    GeminiClient, LLMConfigError, LLMError, LLMRateLimitError, LLMResponseError, LLMTimeoutError,
)

SKEMA = {'type': 'object', 'properties': {'a': {'type': 'string'}}, 'required': ['a']}


class _Respons:
    def __init__(self, text):
        self.text = text


class _ErrorHTTP(Exception):
    def __init__(self, code):
        super().__init__(f'HTTP {code}')
        self.code = code


class ReadTimeout(Exception):  # nama mengandung "timeout", seperti httpx.ReadTimeout
    pass


class _SdkPalsu:
    """Memutar daftar hasil: Exception -> dilempar, selain itu dikembalikan sebagai respons."""

    def __init__(self, urutan):
        self.urutan = list(urutan)
        self.panggilan = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.panggilan += 1
        item = self.urutan.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _klien(sdk, **kw):
    tidur = []
    k = GeminiClient(api_key='x', model='m', sdk_client=sdk, rpm=0, backoff_dasar_detik=1.0,
                     tidur=tidur.append, **kw)
    k.tidur_dicatat = tidur
    return k


def test_tanpa_api_key_error_konfigurasi_jelas():
    with pytest.raises(LLMConfigError, match='GEMINI_API_KEY'):
        GeminiClient(api_key='', model='m')


def test_json_valid_diparse():
    k = _klien(_SdkPalsu([_Respons('{"a": "b"}')]))
    assert k.generate_json('p', SKEMA) == {'a': 'b'}


def test_429_diulang_lalu_berhasil_dengan_backoff():
    sdk = _SdkPalsu([_ErrorHTTP(429), _ErrorHTTP(503), _Respons('{"a": "ok"}')])
    k = _klien(sdk)
    assert k.generate_json('p', SKEMA) == {'a': 'ok'}
    assert sdk.panggilan == 3
    assert len(k.tidur_dicatat) == 2 and k.tidur_dicatat[1] > k.tidur_dicatat[0]


def test_429_terus_menerus_menjadi_rate_limit_error():
    sdk = _SdkPalsu([_ErrorHTTP(429)] * 3)
    k = _klien(sdk, max_retry=2)
    with pytest.raises(LLMRateLimitError):
        k.generate_json('p', SKEMA)
    assert sdk.panggilan == 3


def test_timeout_menjadi_timeout_error():
    k = _klien(_SdkPalsu([ReadTimeout()] * 2), max_retry=1)
    with pytest.raises(LLMTimeoutError):
        k.generate_json('p', SKEMA)


def test_401_tidak_diulang_dan_menjadi_error_konfigurasi():
    sdk = _SdkPalsu([_ErrorHTTP(401), _Respons('{}')])
    k = _klien(sdk)
    with pytest.raises(LLMConfigError):
        k.generate_json('p', SKEMA)
    assert sdk.panggilan == 1


def test_400_tidak_diulang():
    sdk = _SdkPalsu([_ErrorHTTP(400), _Respons('{}')])
    with pytest.raises(LLMError):
        _klien(sdk).generate_json('p', SKEMA)
    assert sdk.panggilan == 1


@pytest.mark.parametrize('teks', [None, '', '   ', 'bukan json', '{"a": '])
def test_respons_kosong_atau_rusak(teks):
    with pytest.raises(LLMResponseError):
        _klien(_SdkPalsu([_Respons(teks)])).generate_json('p', SKEMA)


def test_pembatas_laju_menjaga_jarak_antar_permintaan():
    waktu = [0.0]
    tidur = []

    def jam():
        return waktu[0]

    def tidur_palsu(d):
        tidur.append(d)
        waktu[0] += d

    k = GeminiClient(api_key='x', model='m', sdk_client=_SdkPalsu([_Respons('{}'), _Respons('{}')]),
                     rpm=10, jam=jam, tidur=tidur_palsu)
    k.generate_json('p', SKEMA)
    k.generate_json('p', SKEMA)
    assert tidur == [pytest.approx(6.0)]  # 60 detik / 10 RPM
