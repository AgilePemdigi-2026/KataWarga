"""
Verifikasi keluaran LLM sebelum disimpan. LLM dijamin menghasilkan JSON yang sintaksnya valid,
tetapi ISI-nya tidak: di sini dicek bentuk, evidence nyata, format template, dan WHY yang berdasar.
"""
import re
from dataclasses import dataclass

from extraction.services.base import HasilEkstrak

_SENTIMEN = {'positive', 'neutral', 'negative'}
_TEMPLATE = re.compile(r'^\s*As an? (?P<who>.+?), I want to (?P<what>.+?)(?:, so that (?P<why>.+?))?\s*\.?\s*$',
                       re.IGNORECASE | re.DOTALL)
_ROLE_DEFAULT = 'pengguna'
_KATA_ORANG_PERTAMA = {'saya', 'aku', 'gue', 'gw', 'ane', 'sy'}


class Ditolak(Exception):
    """Satu objek user story ditolak; `jenis` dicatat ke GalatEkstraksi."""

    def __init__(self, jenis, pesan=''):
        super().__init__(f'{jenis}: {pesan}')
        self.jenis, self.pesan = jenis, pesan


def normalisasi_teks(teks):
    return ' '.join(re.sub(r'[^\w\s\[\]]', ' ', (teks or '').lower()).split())


_PEMISAH_POTONGAN = re.compile(r'\s*(?:\.{3,}|\u2026)\s*')


def evidence_ada(evidence, teks_ulasan):
    """
    Evidence boleh berupa beberapa potongan kutipan yang dipisah "..." (ulasan panjang sering
    menyebut satu kebutuhan di dua tempat). Setiap potongan harus ada PERSIS di ulasan.
    """
    potongan = [normalisasi_teks(p) for p in _PEMISAH_POTONGAN.split(evidence)]
    potongan = [p for p in potongan if len(p) >= 3]
    teks = normalisasi_teks(teks_ulasan)
    return bool(potongan) and all(p in teks for p in potongan)


def susun_user_story(who, what, why=''):
    kalimat = f'As a {who}, I want to {what}'
    return f'{kalimat}, so that {why}' if why else kalimat


def _token_isi(teks):
    return {t for t in normalisasi_teks(teks).split() if len(t) > 2}


def alasan_why_ditolak(why, evidence_why, teks_ulasan, what=''):
    """
    None bila WHY layak; selain itu alasan pengosongan. WHY harus (a) punya kutipan dasar yang nyata,
    (b) berupa frasa netral, bukan kalimat orang pertama, (c) bukan salinan ulasan.
    """
    if not evidence_why or not evidence_ada(evidence_why, teks_ulasan):
        return 'why_tanpa_dasar'
    norm_why = normalisasi_teks(why)
    if _KATA_ORANG_PERTAMA & set(norm_why.split()):
        return 'why_orang_pertama'
    if len(norm_why.split()) > 6 and norm_why in normalisasi_teks(teks_ulasan):
        return 'why_salinan_ulasan'
    tw, tt = _token_isi(why), _token_isi(what)
    if len(tw) >= 3 and len(tw & tt) / len(tw) >= 0.5:
        return 'why_ulang_what'  # WHY hanya mengulang WHAT dengan kata lain (melingkar)
    return None


def verifikasi_objek(obj, teks_ulasan):
    """Kembalikan (HasilEkstrak, catatan) atau lempar `Ditolak`. `catatan`: None atau alasan WHY dikosongkan."""
    if not isinstance(obj, dict):
        raise Ditolak('bukan_objek', repr(obj)[:200])
    ambil = lambda k: obj.get(k) if isinstance(obj.get(k), str) else ''
    who, what, why = ambil('who').strip(), ambil('what').strip(), ambil('why').strip()
    evidence_why = ambil('why_evidence').strip()
    evidence, cerita = ambil('evidence').strip(), ambil('as_a_i_want_so_that').strip()

    if not what:
        raise Ditolak('what_kosong')
    if not evidence:
        raise Ditolak('evidence_kosong', what)
    if not evidence_ada(evidence, teks_ulasan):
        raise Ditolak('evidence_tidak_ditemukan', evidence[:200])
    m = _TEMPLATE.match(cerita)
    if not m:
        raise Ditolak('format_template', cerita[:200])
    if normalisasi_teks(what) not in normalisasi_teks(cerita):
        raise Ditolak('what_tidak_sesuai_story', f'{what} | {cerita}'[:300])

    who = who or _ROLE_DEFAULT
    catatan = None
    if why:
        sebab = alasan_why_ditolak(why, evidence_why, teks_ulasan, what)
        if sebab:
            why, evidence_why, catatan = '', '', sebab  # cegah WHY karangan/salinan (syarat tugas C)
    else:
        evidence_why = ''
    story = susun_user_story(who, what, why)  # selalu disusun dari field agar konsisten dengan who/what/why

    try:
        conf = float(obj.get('confidence', 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    sentimen = obj.get('sentiment') if obj.get('sentiment') in _SENTIMEN else ''
    return HasilEkstrak(what=what, who=who[:100], why=why, confidence=max(0.0, min(1.0, conf)),
                        user_story=story, evidence=evidence, evidence_why=evidence_why, sentimen=sentimen), catatan
