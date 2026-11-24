"""Impor ulasan dari CSV untuk Requirements Engineer.

Baris mengikuti aturan filter yang sama dengan pipeline scraping
(``reviews.services.filtering.periksa_ulasan``) supaya status LOLOS/DIBUANG
konsisten dengan data Play Store.
"""
import csv
import io
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from reviews.models import Aplikasi, Ulasan
from reviews.services import dedup
from reviews.services.filtering import ALASAN_DUPLIKAT, evaluasi_ulasan, kunci_duplikat


MAKS_UKURAN_BYTES = 5 * 1024 * 1024
MAKS_BARIS = 2000
MAKS_ERROR_DITAMPILKAN = 20
FORMAT_TANGGAL = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
KOLOM_WAJIB = ("package_name", "nama_aplikasi", "isi_ulasan", "tanggal_ulasan", "skor_bintang")
KOLOM_OPSIONAL = ("username_reviewer", "review_id", "kategori")


class CsvImportError(Exception):
    """Kesalahan file yang dapat ditampilkan langsung ke pengguna."""


def csv_template_content():
    """Template CSV kanonik dengan UTF-8 BOM agar aman dibuka di Excel."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "package_name", "nama_aplikasi", "kategori", "username_reviewer",
        "review_id", "tanggal_ulasan", "skor_bintang", "isi_ulasan",
    ])
    writer.writerow([
        "com.example.aplikasi", "Contoh Aplikasi", "Utilitas", "pengguna_contoh",
        "review-001", "2026-11-17", "4",
        "Aplikasi berjalan lancar tetapi notifikasi sering terlambat masuk.",
    ])
    return "\ufeff" + buffer.getvalue()


def _baca_baris(file_obj):
    if file_obj.size and file_obj.size > MAKS_UKURAN_BYTES:
        raise CsvImportError("Ukuran file melebihi 5 MB.")

    raw = file_obj.read(MAKS_UKURAN_BYTES + 1)
    if len(raw) > MAKS_UKURAN_BYTES:
        raise CsvImportError("Ukuran file melebihi 5 MB.")

    try:
        teks = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            teks = raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise CsvImportError(
                "Encoding file tidak dikenali. Simpan CSV sebagai UTF-8."
            ) from exc

    if not teks.strip():
        raise CsvImportError("File CSV kosong.")

    try:
        dialect = csv.Sniffer().sniff(teks[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(teks), dialect=dialect)
    if not reader.fieldnames:
        raise CsvImportError("Baris header CSV tidak ditemukan.")

    header = [str(name or "").strip().lower() for name in reader.fieldnames]
    reader.fieldnames = header
    hilang = [kolom for kolom in KOLOM_WAJIB if kolom not in header]
    if hilang:
        raise CsvImportError(
            "Kolom wajib tidak ditemukan: " + ", ".join(hilang) + "."
        )

    baris = []
    for nomor, row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        row["_nomor_baris"] = nomor
        baris.append(row)
        if len(baris) > MAKS_BARIS:
            raise CsvImportError(
                f"Jumlah baris melebihi batas {MAKS_BARIS} baris per unggahan."
            )

    if not baris:
        raise CsvImportError("File CSV tidak memiliki baris data.")
    return baris


def _parse_tanggal(value):
    value = str(value or "").strip()
    for format_tanggal in FORMAT_TANGGAL:
        try:
            return datetime.strptime(value, format_tanggal).date()
        except ValueError:
            continue
    return None


def _validasi_baris(row):
    errors = []
    data = {
        "package_name": str(row.get("package_name") or "").strip(),
        "nama_aplikasi": str(row.get("nama_aplikasi") or "").strip(),
        "kategori": str(row.get("kategori") or "").strip()[:100],
        "username_reviewer": str(row.get("username_reviewer") or "").strip()[:150],
        "review_id": str(row.get("review_id") or "").strip()[:100] or None,
        "isi_ulasan": str(row.get("isi_ulasan") or "").strip(),
    }

    if not data["package_name"]:
        errors.append("package_name wajib diisi.")
    elif len(data["package_name"]) > 150:
        errors.append("package_name maksimal 150 karakter.")
    if not data["nama_aplikasi"]:
        errors.append("nama_aplikasi wajib diisi.")
    elif len(data["nama_aplikasi"]) > 100:
        errors.append("nama_aplikasi maksimal 100 karakter.")
    if not data["isi_ulasan"]:
        errors.append("isi_ulasan wajib diisi.")

    tanggal = _parse_tanggal(row.get("tanggal_ulasan"))
    if tanggal is None:
        errors.append("tanggal_ulasan harus valid (YYYY-MM-DD atau DD/MM/YYYY).")
    elif tanggal > timezone.localdate():
        errors.append("tanggal_ulasan tidak boleh di masa depan.")
    data["tanggal_ulasan"] = tanggal

    try:
        skor = int(str(row.get("skor_bintang") or "").strip())
    except (TypeError, ValueError):
        skor = 0
    if skor not in (1, 2, 3, 4, 5):
        errors.append("skor_bintang harus angka 1–5.")
    data["skor_bintang"] = skor

    return data, errors


def import_reviews_csv(file_obj, user=None):
    """Impor CSV secara atomik. Tidak ada baris yang masuk bila ada error validasi."""
    baris = _baca_baris(file_obj)

    konfigurasi = getattr(settings, "SCRAPING", {})

    valid = []
    errors = []
    total_error = 0
    for row in baris:
        data, row_errors = _validasi_baris(row)
        if row_errors:
            total_error += 1
            if len(errors) < MAKS_ERROR_DITAMPILKAN:
                errors.append(f"Baris {row['_nomor_baris']}: " + " ".join(row_errors))
            continue
        data["_nomor_baris"] = row["_nomor_baris"]
        valid.append(data)

    if errors:
        return {
            "ok": False,
            "committed": False,
            "filename": getattr(file_obj, "name", "unggahan.csv"),
            "total_baris": len(baris),
            "diimpor": 0,
            "lolos": 0,
            "dibuang": 0,
            "duplikat": 0,
            "aplikasi_baru": 0,
            "errors": errors,
            "error_count": total_error,
        }

    daftar_package = sorted({item["package_name"] for item in valid})
    aplikasi_map = {
        app.package_name: app
        for app in Aplikasi.objects.filter(package_name__in=daftar_package)
    }

    review_ids = [item["review_id"] for item in valid if item["review_id"]]
    duplikat_db = set()
    if review_ids:
        duplikat_db = set(
            Ulasan.objects
            .filter(review_id__in=review_ids)
            .values_list("aplikasi__package_name", "review_id")
        )

    review_dalam_file = set()
    teks_lolos = {}
    rincian_alasan = {}
    siap_simpan = []
    dilewati = 0
    dibuang = 0
    lolos = 0
    aplikasi_baru = 0

    for item in valid:
        review_id = item["review_id"]
        if review_id:
            kunci = (item["package_name"], review_id)
            if kunci in duplikat_db or kunci in review_dalam_file:
                dilewati += 1
                continue
            review_dalam_file.add(kunci)

        aplikasi = aplikasi_map.get(item["package_name"])
        if aplikasi is None:
            aplikasi = Aplikasi(
                nama_aplikasi=item["nama_aplikasi"],
                package_name=item["package_name"],
                kategori=item["kategori"],
            )
            aplikasi_map[item["package_name"]] = aplikasi
            aplikasi_baru += 1

        keputusan = evaluasi_ulasan(
            item["isi_ulasan"], item["skor_bintang"], konfigurasi
        )
        sudah_lolos, alasan = keputusan.lolos, keputusan.alasan
        if sudah_lolos:
            kunci_set = teks_lolos.setdefault(
                item["package_name"], dedup.kunci_teks_lolos(aplikasi)
            )
            kunci = kunci_duplikat(item["isi_ulasan"])
            if kunci in kunci_set:
                sudah_lolos, alasan = False, ALASAN_DUPLIKAT
            else:
                kunci_set.add(kunci)
        if sudah_lolos:
            lolos += 1
        else:
            dibuang += 1
            rincian_alasan[alasan] = rincian_alasan.get(alasan, 0) + 1

        siap_simpan.append((aplikasi, item, sudah_lolos, alasan))

    with transaction.atomic():
        for aplikasi in aplikasi_map.values():
            if aplikasi.pk is None:
                aplikasi.save()

        Ulasan.objects.bulk_create([
            Ulasan(
                aplikasi=aplikasi,
                review_id=item["review_id"],
                username_reviewer=item["username_reviewer"],
                isi_ulasan=item["isi_ulasan"],
                tanggal_ulasan=item["tanggal_ulasan"],
                skor_bintang=item["skor_bintang"],
                status_filter=(
                    Ulasan.StatusFilter.LOLOS
                    if sudah_lolos
                    else Ulasan.StatusFilter.DIBUANG
                ),
                alasan_filter=alasan,
            )
            for aplikasi, item, sudah_lolos, alasan in siap_simpan
        ])

    return {
        "ok": True,
        "committed": True,
        "filename": getattr(file_obj, "name", "unggahan.csv"),
        "total_baris": len(baris),
        "diimpor": len(siap_simpan),
        "lolos": lolos,
        "dibuang": dibuang,
        "rincian_alasan": rincian_alasan,
        "duplikat": dilewati,
        "aplikasi_baru": aplikasi_baru,
        "errors": [],
        "error_count": 0,
        "pengguna": getattr(user, "username", ""),
    }
