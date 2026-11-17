"""Views unggah CSV ulasan untuk Requirements Engineer."""
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from accounts.decorators import role_required
from accounts.models import User
from reviews.services.importer import (
    CsvImportError,
    csv_template_content,
    import_reviews_csv,
)


SESSION_KEY = "csv_import_result"


@role_required(User.RolePengguna.REQUIREMENTS_ENGINEER)
def import_csv_view(request):
    """
    GET  /reviews/import/ — panduan + form unggah.
    POST /reviews/import/ — validasi dan impor atomik.

    Hasil disimpan singkat di sesi lalu diambil sekali agar refresh tidak
    mengirim ulang file (pola POST-Redirect-GET).
    """
    result = request.session.pop(SESSION_KEY, None)
    form_error = ""

    if request.method == "POST":
        berkas = request.FILES.get("file")
        if berkas is None:
            form_error = "Pilih file CSV terlebih dahulu."
        else:
            try:
                result = import_reviews_csv(berkas, user=request.user)
            except CsvImportError as exc:
                result = {
                    "ok": False,
                    "committed": False,
                    "filename": getattr(berkas, "name", "unggahan.csv"),
                    "total_baris": 0,
                    "diimpor": 0,
                    "lolos": 0,
                    "dibuang": 0,
                    "duplikat": 0,
                    "aplikasi_baru": 0,
                    "errors": [str(exc)],
                    "error_count": 1,
                }

            request.session[SESSION_KEY] = result

            if result["ok"]:
                messages.success(
                    request,
                    f"{result['diimpor']} ulasan berhasil diimpor dari "
                    f"{result['filename']}.",
                )
            else:
                messages.error(
                    request,
                    "Impor dibatalkan. Tidak ada baris yang disimpan; "
                    f"periksa {result['error_count']} baris bermasalah.",
                )
            return redirect("reviews:import_csv")

    return render(
        request,
        "reviews/import.html",
        {
            "result": result,
            "form_error": form_error,
        },
    )


@role_required(User.RolePengguna.REQUIREMENTS_ENGINEER)
def csv_template_view(request):
    """Unduh template CSV kanonik (real file, bukan tombol dekoratif)."""
    response = HttpResponse(
        csv_template_content(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        'attachment; filename="template-impor-ulasan-katawarga.csv"'
    )
    return response
