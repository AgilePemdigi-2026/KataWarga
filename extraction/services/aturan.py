"""
Ekstraktor awal berbasis aturan untuk ulasan berbahasa Indonesia.

Ini BASELINE sementara agar pipeline ujung ke ujung dapat berjalan sebelum model
IndoBERT hasil fine-tuning tersedia. Kualitasnya terbatas dan tidak boleh dipakai
sebagai klaim performa model (O-2). Cara kerja:
  - ulasan dipecah menjadi klausa; klausa yang memuat kata masalah/kebutuhan jadi kandidat WHAT;
  - kata penghubung sebab/tujuan (supaya, agar, karena, ...) memisahkan WHAT dan WHY;
  - WHO diambil dari pola "sebagai <peran>" atau kata kunci pemangku kepentingan.
"""
import re
from dataclasses import replace

from extraction.services.base import Ekstraktor, HasilEkstrak

# Penanda masalah atau kebutuhan. # USULAN: sesuaikan dengan data nyata
KATA_MASALAH = (
    'tidak bisa', 'gak bisa', 'ga bisa', 'nggak bisa', 'tdk bisa', 'tidak dapat',
    'tidak muncul', 'gak muncul', 'tidak masuk', 'tidak berfungsi', 'tidak jalan',
    'tidak terbuka', 'gagal', 'error', 'eror', 'bug', 'crash', 'force close',
    'keluar sendiri', 'hang', 'lemot', 'lambat', 'susah', 'sulit', 'ribet',
    'macet', 'loading terus', 'stuck', 'hilang', 'salah', 'terblokir', 'otp',
)
KATA_KEBUTUHAN = (
    'ingin', 'mau', 'butuh', 'perlu', 'tolong', 'mohon', 'harap', 'semoga',
    'tambahkan', 'tambah fitur', 'perbaiki', 'diperbaiki', 'buatkan', 'sediakan',
)
PENANDA_WHY = r'(?:supaya|agar|biar|sehingga|karena|soalnya|sebab|gara-gara|akibatnya)'

_PEMBUKA = re.compile(
    r'^(?:(?:dan|tapi|tetapi|namun|cuma|hanya|jadi|makanya|akhirnya|saya|aku|kami|tolong|mohon|harap|semoga)\s+)+',
    re.IGNORECASE)
_PEMBUKA_KEBUTUHAN = re.compile(
    r'^(?:(?:saya|aku|kami)\s+)?(?:ingin|mau|butuh|perlu|berharap)\s+(?:sekali\s+)?', re.IGNORECASE)
# WHO hanya diambil dari pola eksplisit, mis. "sebagai wajib pajak" atau "saya seorang pasien".
# Pencarian kata kunci bebas sengaja tidak dipakai: "ke dokter" bukan pemangku kepentingan.
_SEBAGAI = re.compile(r'\b(?:sebagai|selaku|saya seorang|saya adalah)\s+((?:[a-z]+\s?){1,3})', re.IGNORECASE)
_AWAL_SEBAGAI = re.compile(r'^(?:sebagai|selaku)\s+[^,]+,\s*', re.IGNORECASE)
_BERHENTI_WHO = {'saya', 'aku', 'kami', 'ingin', 'mau', 'tidak', 'gak', 'ga', 'sulit', 'susah', 'merasa',
                 'butuh', 'perlu', 'bisa', 'dan', 'yang'}
_MARKER = re.compile(rf'\b{PENANDA_WHY}\b', re.IGNORECASE)


def _bersihkan(teks):
    return re.sub(r'\s+', ' ', teks).strip(' ,.!?;:-–—"\'')


def _pecah_klausa(teks):
    bagian = re.split(r'(?<=[.!?])\s+|[\n;]+', teks or '')
    return [b.strip() for b in bagian if b and b.strip()]


def _ada_kata(teks, daftar):
    t = f' {teks.lower()} '
    return any(re.search(rf'\b{re.escape(k)}\b', t) for k in daftar)


def _cari_who(teks):
    m = _SEBAGAI.search(teks)
    if not m:
        return ''
    kata = []
    for k in m.group(1).split():
        if k.lower() in _BERHENTI_WHO:
            break
        kata.append(k)
    return ' '.join(kata).lower()


_KATA_KOSONG = {'segera', 'diperbaiki', 'perbaiki', 'tolong', 'mohon', 'ya', 'dong', 'nya',
                'sekali', 'banget', 'cepat', 'dibenahi', 'diperbaharui', 'diperbarui', 'ditingkatkan'}


def _kosong(what):
    """True bila isinya hanya permintaan umum ("segera diperbaiki") tanpa objek yang jelas."""
    return not [k for k in re.findall(r'\w+', what.lower()) if k not in _KATA_KOSONG]


def _bersihkan_what(what):
    what = _bersihkan(what)
    what = _AWAL_SEBAGAI.sub('', what)
    what = _PEMBUKA_KEBUTUHAN.sub('', what)
    what = _PEMBUKA.sub('', what)
    return _bersihkan(what)


def _pisah_what_why(klausa):
    """Kembalikan (what, why) dari satu klausa."""
    m = _MARKER.search(klausa)
    if not m:
        return klausa, ''
    sebelum, sesudah = klausa[:m.start()], klausa[m.end():]
    if _bersihkan(sebelum):                       # "<what> karena/agar <why>"
        return sebelum, sesudah
    if ',' in sesudah:                            # "Karena <why>, <what>"
        why, what = sesudah.split(',', 1)
        if _ada_kata(what, KATA_MASALAH + KATA_KEBUTUHAN):
            return what, why
    return sesudah, ''                            # "Karena <what>"


class EkstraktorAturan(Ekstraktor):
    nama = 'aturan'
    CONFIDENCE_MAKS = 0.8  # heuristik tidak boleh tampak seyakin model terlatih

    def __init__(self, max_hasil=3):
        self.max_hasil = max_hasil

    def ekstrak(self, teks):
        who = _cari_who(teks or '')
        hasil, terlihat = [], set()
        for klausa in _pecah_klausa(teks):
            if not _ada_kata(klausa, KATA_MASALAH + KATA_KEBUTUHAN):
                continue
            what_mentah, why_mentah = _pisah_what_why(klausa)
            what, why = _bersihkan_what(what_mentah), _bersihkan(why_mentah)
            if _kosong(what):
                # permintaan umum ("tolong segera diperbaiki karena ..."): simpan alasannya
                # pada hasil sebelumnya bila hasil itu belum punya alasan.
                if why and hasil and not hasil[-1].why:
                    hasil[-1] = replace(hasil[-1], why=why[:1000])
                continue
            if len(what.split()) < 2 or what.lower() in terlihat:
                continue
            terlihat.add(what.lower())
            conf = 0.4 + (0.2 if len(what.split()) >= 3 else 0) + (0.15 if why else 0) + (0.1 if who else 0)
            hasil.append(HasilEkstrak(
                what=what[:1000], who=who[:100], why=why[:1000],
                confidence=round(min(conf, self.CONFIDENCE_MAKS), 4),
            ))
            if len(hasil) >= self.max_hasil:
                break
        return hasil
