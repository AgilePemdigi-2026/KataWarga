# KataWarga
Sistem otomatisasi elisitasi ulasan aplikasi pemerintah

## Menjalankan test
Gunakan **Python 3.12** (Django 4.2 belum kompatibel dengan Python 3.14).

```bash
pip install -r requirements/dev.txt
docker compose up -d      # PostgreSQL (port 5433)
pytest                    # semua test
pytest reviews -x         # satu app, berhenti di kegagalan pertama
```

Test juga berjalan otomatis di GitHub Actions pada setiap Pull Request dan push ke `main`
(`.github/workflows/tests.yml`).
