"""
Preprocessing dan filter ulasan (FR-EKS-05, Project_Context §8, TBD-01, Sprint 3 bagian B).

Dua tingkat:
- ``periksa_ulasan``  : filter dasar (terlalu pendek / generik persis). Dipertahankan agar kompatibel.
- ``evaluasi_ulasan`` : filter lengkap berbasis aturan. Memberi keputusan DAN alasan yang jelas:

    terlalu pendek  - kata < min_kata (kecuali keluhan teknis singkat, mis. "login gagal")
    spam            - tautan/nomor telepon/promosi judi, atau kata berulang-ulang tanpa isi
    generik         - pujian murni ("bagus banget aplikasinya", "terima kasih")
    tidak relevan   - pendek, tanpa sinyal kebutuhan/keluhan, dan bintang netral/positif
    duplikat        - teks sama dengan ulasan lolos lain pada aplikasi yang sama (ditangani di ingest)
    tanpa kebutuhan - lolos filter tetapi ekstraktor tidak menemukan kebutuhan (ditangani di runner)

Prinsip: ulasan yang mengandung sinyal keluhan teknis atau permintaan fitur (bug, "tidak bisa login",
"tolong tambahkan ...") TIDAK PERNAH dibuang oleh aturan pujian/tidak relevan (bagian B4). Bila ragu,
ulasan dibiarkan LOLOS; keputusan akhir ada pada tahap ekstraksi dan validasi Analyst.
Semua ambang dapat diatur lewat settings.SCRAPING.
"""
import re
import unicodedata
from dataclasses import dataclass

ALASAN_PENDEK = 'terlalu pendek'
ALASAN_GENERIK = 'generik'
ALASAN_SPAM = 'spam'
ALASAN_TIDAK_RELEVAN = 'tidak relevan'
ALASAN_DUPLIKAT = 'duplikat'
ALASAN_TANPA_KEBUTUHAN = 'tanpa kebutuhan'


def normalisasi(teks):
    """Huruf kecil, buang tanda baca/emoji, rapikan spasi, dan ringkas huruf berulang."""
    if not teks:
        return ''
    teks = unicodedata.normalize('NFKC', str(teks)).lower()
    teks = re.sub(r'[^\w\s]|_', ' ', teks)
    teks = re.sub(r'(\w)\1+', r'\1', teks)  # "bagusss" -> "bagus", "mantapp" -> "mantap"
    return re.sub(r'\s+', ' ', teks).strip()


def hitung_kata(teks):
    return len(re.findall(r'\w+', teks or ''))


def kunci_duplikat(teks):
    """Kunci pembanding duplikasi: teks yang sama setelah normalisasi dianggap duplikat."""
    return normalisasi(teks)


# --- Kamus (dinormalisasi dengan fungsi yang sama agar cocok dengan teks ternormalisasi) ---------

_SLANG = {
    'gak': 'tidak', 'ga': 'tidak', 'nggak': 'tidak', 'ngga': 'tidak', 'enggak': 'tidak', 'gk': 'tidak',
    'tdk': 'tidak', 'g': 'tidak', 'tak': 'tidak', 'bgt': 'banget', 'yg': 'yang', 'udh': 'sudah',
    'udah': 'sudah', 'sdh': 'sudah', 'blm': 'belum', 'sy': 'saya', 'dgn': 'dengan', 'utk': 'untuk',
    'krn': 'karena', 'jg': 'juga', 'bs': 'bisa', 'trs': 'terus', 'terus2': 'terus', 'eror': 'error',
    'ngelag': 'lag', 'lemot': 'lambat', 'nyangkut': 'stuck', 'tmbh': 'tambah', 'tmbahin': 'tambahin',
}

_TEKNIS = [
    'error', 'bug', 'crash', 'force close', 'fc', 'keluar sendiri', 'tertutup sendiri', 'nutup sendiri',
    'lambat', 'lag', 'loading', 'hang', 'macet', 'gagal', 'tidak bisa', 'tidak dapat', 'tidak muncul',
    'tidak masuk', 'tidak terkirim', 'tidak merespon', 'tidak respon', 'blank', 'layar putih', 'stuck',
    'mentok', 'freeze', 'login', 'log in', 'masuk akun', 'daftar', 'registrasi', 'otp', 'kode verifikasi',
    'verifikasi', 'sinkron', 'sync', 'server', 'koneksi', 'hilang', 'update', 'pembaruan', 'offline',
    'tidak jalan', 'tidak berfungsi', 'boros', 'panas', 'notifikasi', 'salah', 'keliru', 'gangguan',
    'maintenance', 'ditolak', 'invalid', 'timeout', 'tidak sesuai', 'tidak valid', 'tidak ditemukan',
    'ribet', 'susah', 'sulit', 'rumit', 'bingung', 'tidak', 'failed', 'lama',
]

_KEBUTUHAN = [
    'tolong', 'mohon', 'tambah', 'tambahkan', 'ditambah', 'ditambahkan', 'tambahin', 'fitur', 'semoga',
    'harap', 'berharap', 'harusnya', 'seharusnya', 'sebaiknya', 'perbaiki', 'diperbaiki', 'perbaikan',
    'tingkatkan', 'ditingkatkan', 'ingin', 'pengen', 'mau', 'butuh', 'perlu', 'minta', 'request', 'saran',
    'usul', 'usulan', 'dibuat', 'kurang', 'sayang', 'sayangnya', 'padahal', 'tapi', 'namun', 'tetapi',
    'cuma', 'harus', 'kenapa', 'mengapa', 'kok', 'masa',
]

_PUJIAN = [
    'bagus', 'mantap', 'keren', 'ok', 'oke', 'good', 'nice', 'baik', 'sip', 'top', 'wow', 'terbaik',
    'lumayan', 'membantu', 'bermanfaat', 'berguna', 'memudahkan', 'mudah', 'simpel', 'praktis', 'cepat',
    'lancar', 'puas', 'suka', 'recommended', 'rekomended', 'terima kasih', 'makasih', 'thanks', 'thx',
    'sempurna', 'luar biasa', 'hebat', 'josss', 'jos',
]
_PENGISI = [
    'aplikasi', 'app', 'banget', 'sekali', 'sangat', 'sih', 'deh', 'ya', 'yang', 'ini', 'itu', 'dan',
    'amat', 'pokoknya', 'semua', 'nya', 'sangat', 'untuk', 'sudah', 'saya', 'sekarang', 'pemerintah',
    # kata penunjuk subjek/objek umum dan nama aplikasi target: tidak membawa kebutuhan
    'bagi', 'buat', 'kita', 'kami', 'masyarakat', 'warga', 'rakyat', 'orang', 'indonesia', 'negara',
    'pengguna', 'm', 'ikd', 'satusehat', 'sehat', 'satu', 'mpajak', 'pajak', 'dukcapil', 'identitas',
    'kependudukan', 'digital', 'dalam', 'sangat', 'lebih', 'jadi', 'dengan', 'oleh', 'dari', 'pada',
]

_KATA_SPAM = [
    'slot', 'gacor', 'judi', 'togel', 'maxwin', 'deposit', 'pinjol', 'pinjaman cepat', 'wa me',
    'whatsapp', 'telegram', 'hubungi kami', 'klik link', 'klik tautan', 'daftar sekarang bonus',
]

_RE_URL = re.compile(r'(https?://|www\.|\b[a-z0-9-]+\.(?:com|net|xyz|top|site|online|link|club|vip)\b)', re.I)
_RE_TELEPON = re.compile(r'(?<!\d)(?:\+?62|0)\s*8[\s-]?\d(?:[\s-]?\d){7,11}(?!\d)')


def _norm_daftar(daftar):
    return [normalisasi(x) for x in daftar]


_SET_TEKNIS = _norm_daftar(_TEKNIS)
_SET_KEBUTUHAN = _norm_daftar(_KEBUTUHAN)
_SET_PUJIAN = _norm_daftar(_PUJIAN)
_SET_PENGISI = set(_norm_daftar(_PENGISI))
_SET_SPAM = _norm_daftar(_KATA_SPAM)
_SLANG_N = {normalisasi(k): normalisasi(v) for k, v in _SLANG.items()}


def _token_baku(teks):
    """Token ternormalisasi dengan slang diubah ke bentuk baku (khusus untuk pencocokan sinyal)."""
    token = [_SLANG_N.get(t, t) for t in normalisasi(teks).split()]
    # akhiran -nya ("loadingnya", "aplikasinya") dibuang agar cocok dengan kamus
    return [t[:-3] if t.endswith('nya') and len(t) > 5 else t for t in token]


def _mengandung(padded, daftar):
    return any(f' {f} ' in padded for f in daftar)


def sinyal_teknis(teks):
    return _mengandung(f" {' '.join(_token_baku(teks))} ", _SET_TEKNIS)


def sinyal_kebutuhan(teks):
    return _mengandung(f" {' '.join(_token_baku(teks))} ", _SET_KEBUTUHAN)


def _pujian_murni(token):
    if not token:
        return False
    padded = f" {' '.join(token)} "
    sisa = padded
    # buang frasa pujian dulu (mis. "terima kasih"), lalu cek apakah semua token sisa adalah pujian/pengisi
    ada_pujian = False
    for f in sorted(_SET_PUJIAN, key=len, reverse=True):
        if f' {f} ' in sisa:
            ada_pujian = True
            sisa = sisa.replace(f' {f} ', ' ')
    sisa_token = sisa.split()
    return ada_pujian and all(t in _SET_PENGISI for t in sisa_token)


@dataclass(frozen=True)
class Keputusan:
    lolos: bool
    alasan: str = ''


def _spam(teks, token, ada_sinyal, cfg):
    padded = f" {' '.join(token)} "
    if _mengandung(padded, _SET_SPAM):
        return True  # promosi judi/pinjol dibuang walau mengandung kata "daftar"/"login"
    if ada_sinyal:
        return False  # ulasan yang memuat keluhan/kebutuhan tidak dibuang karena tautan/angka
    if _RE_URL.search(teks) or _RE_TELEPON.search(teks):
        return True
    if len(token) >= 4 and len(set(token)) / len(token) <= cfg.get('maks_rasio_unik_spam', 0.3):
        return True
    return False


def periksa_ulasan(teks, min_kata, pola_generik):
    """
    Filter dasar: kembalikan (lolos: bool, alasan: str); `alasan` kosong bila lolos.
    Untuk filter lengkap (spam, pujian, tidak relevan) gunakan ``evaluasi_ulasan``.
    """
    if hitung_kata(teks) < min_kata:
        return False, ALASAN_PENDEK
    pola = {normalisasi(p) for p in pola_generik}
    if normalisasi(teks) in pola:
        return False, ALASAN_GENERIK
    return True, ''


def evaluasi_ulasan(teks, skor=None, cfg=None):
    """
    Filter lengkap. Urutan aturan menentukan alasan yang dicatat:
    pendek -> spam -> generik -> (sinyal teknis/kebutuhan: LOLOS) -> tidak relevan -> LOLOS.
    """
    cfg = cfg or {}
    min_kata = cfg.get('min_kata', 3)
    min_kata_keluhan = cfg.get('min_kata_keluhan', 2)
    maks_tanpa_sinyal = cfg.get('maks_kata_tanpa_sinyal', 5)
    pola_generik = cfg.get('pola_generik', [])

    token = _token_baku(teks)
    padded = f" {' '.join(token)} "
    teknis = _mengandung(padded, _SET_TEKNIS)
    kebutuhan = _mengandung(padded, _SET_KEBUTUHAN)
    ada_sinyal = teknis or kebutuhan
    jumlah_kata = hitung_kata(teks)

    if jumlah_kata < min_kata:
        # B4: keluhan teknis singkat ("login gagal", "force close") tetap dianggap sumber kebutuhan
        if not (teknis and jumlah_kata >= min_kata_keluhan):
            if _spam(teks, token, False, cfg) and jumlah_kata:
                return Keputusan(False, ALASAN_SPAM)
            return Keputusan(False, ALASAN_PENDEK)

    if _spam(teks, token, ada_sinyal, cfg):
        return Keputusan(False, ALASAN_SPAM)

    if normalisasi(teks) in {normalisasi(p) for p in pola_generik}:
        return Keputusan(False, ALASAN_GENERIK)
    if not ada_sinyal and _pujian_murni(token):
        return Keputusan(False, ALASAN_GENERIK)

    if ada_sinyal:
        return Keputusan(True)

    if jumlah_kata <= maks_tanpa_sinyal and (skor is None or skor >= 3):
        return Keputusan(False, ALASAN_TIDAK_RELEVAN)
    return Keputusan(True)
