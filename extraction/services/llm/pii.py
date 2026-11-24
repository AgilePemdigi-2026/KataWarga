"""Penyamaran data pribadi sebelum teks ulasan dikirim ke API eksternal."""
import re

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_NIK = re.compile(r'(?<!\d)(?:\d[ .-]?){15}\d(?!\d)')  # 16 digit, boleh dipisah spasi/titik/strip
_TELEPON = re.compile(r'(?<!\d)(?:\+?62|0)[ .-]?8\d(?:[ .-]?\d){7,11}(?!\d)')


def samarkan_pii(teks):
    """Ganti email, NIK (16 digit), dan nomor telepon dengan penanda [EMAIL]/[NIK]/[TELEPON]."""
    teks = _EMAIL.sub('[EMAIL]', teks)
    teks = _NIK.sub('[NIK]', teks)
    teks = _TELEPON.sub('[TELEPON]', teks)
    return teks
