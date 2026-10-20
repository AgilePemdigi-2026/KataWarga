# KataWarga: Folder Structure Reference

> Referensi struktur folder proyek Django **KataWarga**.
> Stack: Django, HTMX, Tailwind CSS, Chart.js, PostgreSQL.
> Berdasarkan §15 Project_Context.md dengan detail lengkap.

---

## Penjelasan Konvensi

| Konvensi | Keterangan |
|---|---|
| `config/` | Project-level Django config (settings, root URLs, wsgi/asgi) — **bukan** nama default `katawarga/` agar jelas ini konfigurasi, bukan app |
| Tiap app punya `urls.py` sendiri | Di-include dari `config/urls.py` |
| `templates/` di root | Global templates (base layout, komponen bersama, partials HTMX) |
| `templates/<app_name>/` | Template per app, sesuai konvensi Django namespace |
| `static/` di root | Global static files (Tailwind build output, Chart.js, HTMX) |
| `fixtures/` | Data dummy Sprint 1 (JSON fixtures untuk `loaddata`) |
| `requirements/` | Dependency files terpisah per environment (`base.txt`, `dev.txt`, `prod.txt`) |
| `logs/` | Log kegagalan scraping & NLP (§3.2, §6.1, FR-EKS-10) — di-gitkeep |
| `ml_models/` | Tempat bobot model IndoBERT fine-tuned (§3.2, §8) — di-gitkeep |
| `media/` | Django `MEDIA_ROOT` untuk file dinamis/export — di-gitkeep |
| `docker-compose.yml` | Container PostgreSQL 16 untuk environment lokal tim yang seragam |

---

## Struktur Lengkap

```
KataWarga/                              # Root repository
│
├── README.md                           # Deskripsi proyek
├── Reference/                          # Dokumen referensi (non-code)
│   ├── Project_Context.md
│   └── Folder_Structure.md             # File ini
│
├── .gitignore
├── .env.example                        # Template environment variables
├── docker-compose.yml                  # PostgreSQL 16 local database container
├── manage.py                           # Django management entry point
│
├── requirements/                       # Dependencies
│   ├── base.txt                        # Shared dependencies (Django, PostgreSQL, NLP IndoBERT, Scraper)
│   ├── dev.txt                         # Development (debug toolbar, pytest, flake8, black)
│   └── prod.txt                        # Production (gunicorn, whitenoise)
│
├── logs/                               # Log file server & pipeline (FR-EKS-10, §3.2)
│   └── .gitkeep
│
├── ml_models/                          # Bobot model IndoBERT fine-tuned (§3.2, §8)
│   └── .gitkeep
│
├── media/                              # Django MEDIA_ROOT untuk file dinamis/export
│   └── .gitkeep
│
├── config/                             # Django project configuration
│   ├── __init__.py
│   ├── settings/                       # Split settings
│   │   ├── __init__.py
│   │   ├── base.py                     # Settings umum (INSTALLED_APPS, MIDDLEWARE, AUTH_USER_MODEL, dll)
│   │   ├── dev.py                      # DEBUG=True, console email, django-debug-toolbar
│   │   └── prod.py                     # DEBUG=False, ALLOWED_HOSTS, security settings
│   ├── urls.py                         # Root URL configuration (include semua app)
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                           # App: Pengguna, Auth, RBAC
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Custom User model (AbstractUser + role field)
│   ├── admin.py                        # Register ke Django Admin
│   ├── forms.py                        # Login, Register forms
│   ├── views.py                        # Login, Logout, Register views
│   ├── urls.py                         # /login/, /logout/, /register/
│   ├── decorators.py                   # @role_required decorator untuk RBAC
│   ├── mixins.py                       # RoleRequiredMixin untuk CBV
│   ├── managers.py                     # Custom UserManager (opsional)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_views.py
│   │   └── test_rbac.py
│   └── migrations/
│       └── __init__.py
│
├── reviews/                            # App: Aplikasi target, Ulasan, Scraping & Filter
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Aplikasi, Ulasan
│   ├── admin.py
│   ├── views.py
│   ├── urls.py
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── scraper.py                  # google-play-scraper wrapper, backoff, dedup
│   │   └── filter.py                   # Filter ulasan pendek/generik
│   ├── management/
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── scrape_reviews.py       # Management command: python manage.py scrape_reviews
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_scraper.py
│   │   └── test_filter.py
│   └── migrations/
│       └── __init__.py
│
├── extraction/                         # App: Hasil Ekstraksi, Cluster, Pipeline NLP, Validasi Analyst
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # HasilEkstraksi, Cluster, ClusterAnggota
│   ├── admin.py
│   ├── views.py                        # Halaman /ekstraksi, /validasi-ekstraksi/{id}
│   ├── urls.py
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── extractor.py               # IndoBERT token classification (BIO)
│   │   ├── clustering.py              # Semantic similarity clustering & dedup
│   │   ├── pipeline.py                # Orchestrator: scrape → filter → extract → cluster
│   │   └── validation.py              # Logika validasi Analyst (Setujui/Tolak)
│   ├── management/
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── run_extraction.py      # Management command: python manage.py run_extraction
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_extractor.py
│   │   ├── test_clustering.py
│   │   ├── test_pipeline.py
│   │   └── test_validation.py
│   └── migrations/
│       └── __init__.py
│
├── stories/                            # App: User Story, Penyusunan & Skor, Persetujuan PO
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # UserStory
│   ├── admin.py
│   ├── views.py                        # Halaman /susun-user-story, /user-story/{id}
│   ├── urls.py
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── composer.py                # Perumusan "Sebagai [who]..." dari cluster
│   │   ├── scoring.py                 # Skor prioritas (frekuensi + sentimen) & kategori
│   │   └── approval.py               # Logika persetujuan PO (Setujui/Abaikan)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_composer.py
│   │   ├── test_scoring.py
│   │   └── test_approval.py
│   └── migrations/
│       └── __init__.py
│
├── backlog/                            # App: Backlog Item, Eksekusi Developer
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # BacklogItem
│   ├── admin.py
│   ├── views.py                        # Halaman /backlog, /backlog/{id}
│   ├── urls.py
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   └── execution.py              # Transisi status: Siap → Dikerjakan → Selesai
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   └── test_execution.py
│   └── migrations/
│       └── __init__.py
│
├── dashboard/                          # App: Dashboard Overview (metrik & grafik)
│   ├── __init__.py
│   ├── apps.py
│   ├── views.py                        # Halaman Dashboard (Chart.js data)
│   ├── urls.py
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   └── metrics.py                 # Hitung metrik: total reviews, noise rate, dll
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_metrics.py
│   └── migrations/
│       └── __init__.py
│
├── templates/                          # Global templates
│   ├── base.html                       # Base layout: sidebar, header, dark mode, Tailwind
│   ├── components/                     # Komponen reusable
│   │   ├── sidebar.html               # Sidebar navigasi (Dashboard, Extraction, Backlog, dll)
│   │   ├── header.html                # Header dengan search bar
│   │   ├── messages.html              # Django messages / flash notifications
│   │   └── pagination.html            # Pagination component
│   ├── partials/                       # HTMX partial responses
│   │   └── _empty.html                # Placeholder
│   │
│   ├── accounts/                       # Templates app accounts
│   │   ├── login.html
│   │   ├── register.html
│   │   └── profile.html
│   │
│   ├── reviews/                        # Templates app reviews
│   │   └── review_list.html
│   │
│   ├── extraction/                     # Templates app extraction
│   │   ├── pipeline.html              # /ekstraksi — tombol "Jalankan Ekstraksi", section hasil-cluster
│   │   ├── partials/                  # HTMX partials untuk extraction
│   │   │   ├── _cluster_list.html     # Section hasil-cluster (HTMX swap target)
│   │   │   ├── _cluster_card.html     # Kartu cluster individual
│   │   │   └── _extraction_status.html # Status proses ekstraksi
│   │   └── validation_detail.html     # /validasi-ekstraksi/{id} — Setujui/Tolak
│   │
│   ├── stories/                        # Templates app stories
│   │   ├── compose.html               # /susun-user-story — tombol "Susun User Story", daftar-user-story
│   │   ├── partials/
│   │   │   ├── _story_list.html       # Section daftar-user-story (HTMX swap target)
│   │   │   └── _story_card.html       # Kartu user story individual
│   │   └── detail.html                # /user-story/{id} — Setujui/Abaikan (PO)
│   │
│   ├── backlog/                        # Templates app backlog
│   │   ├── list.html                  # /backlog — papan Kanban (To Review, Sprint Backlog, dll)
│   │   ├── partials/
│   │   │   ├── _backlog_board.html    # Papan kolom status (HTMX swap target)
│   │   │   └── _backlog_card.html     # Kartu backlog item
│   │   └── detail.html               # /backlog/{id} — Mulai Kerjakan / Tandai Selesai
│   │
│   └── dashboard/                      # Templates app dashboard
│       ├── overview.html              # Dashboard utama (Chart.js graphs)
│       └── partials/
│           ├── _metrics_cards.html    # Empat kartu metrik
│           ├── _sentiment_chart.html  # Grafik garis sentimen
│           └── _cluster_chart.html    # Grafik batang Biggest Topic Cluster
│
├── static/                             # Global static files
│   ├── css/
│   │   ├── input.css                  # Tailwind CSS input (source)
│   │   └── output.css                 # Tailwind CSS compiled output (generated)
│   ├── js/
│   │   ├── htmx.min.js               # HTMX library
│   │   ├── chart.min.js              # Chart.js library
│   │   └── app.js                    # Custom JS (Chart.js init, HTMX config, dll)
│   └── images/
│       ├── logo.svg                   # Logo KataWarga
│       └── favicon.ico
│
├── fixtures/                           # Data dummy untuk Sprint 1
│   ├── 01_users.json                  # Pengguna per role
│   ├── 02_apps.json                   # 3 aplikasi target (SATU SEHAT, IKD, M-Pajak)
│   ├── 03_reviews.json                # Ulasan dummy (lolos & dibuang)
│   ├── 04_extractions.json            # Hasil ekstraksi dummy
│   ├── 05_clusters.json               # Cluster dummy (tervalidasi, berbagai ukuran)
│   ├── 06_stories.json                # User story per kategori prioritas
│   └── 07_backlog.json                # Item backlog berbagai status
│
├── tailwind.config.js                  # Konfigurasi Tailwind CSS
├── package.json                        # Node dependencies (Tailwind CLI)
└── Makefile                            # Shortcuts: make run, make migrate, make test, dll (opsional)
```

---

## Penjelasan per Layer

### 1. `config/` — Project Configuration

Menggunakan **split settings** (`base.py`, `dev.py`, `prod.py`) agar konfigurasi development dan production terpisah jelas.

```python
# manage.py default
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
```

Penting di `base.py`:
- `AUTH_USER_MODEL = 'accounts.User'` — **wajib sebelum migrasi pertama**
- `INSTALLED_APPS` — daftarkan semua 6 app
- `TEMPLATES` — arahkan ke `templates/` di root
- `STATICFILES_DIRS` — arahkan ke `static/` di root

### 2. App Django — Pembagian Berdasarkan Domain

| App | Model | Halaman/URL | Sprint |
|---|---|---|---|
| `accounts` | User (custom) | `/login/`, `/logout/`, `/register/` | 2–3 |
| `reviews` | Aplikasi, Ulasan | (admin/management command) | 2 |
| `extraction` | HasilEkstraksi, Cluster, ClusterAnggota | `/ekstraksi`, `/validasi-ekstraksi/{id}` | 2 |
| `stories` | UserStory | `/susun-user-story`, `/user-story/{id}` | 1 |
| `backlog` | BacklogItem | `/backlog`, `/backlog/{id}` | 1 |
| `dashboard` | (no models) | `/` atau `/dashboard` | 2 |

### 3. `services/` — Business Logic Layer (per app)

Sesuai §15 Project Context: _"Logika bisnis (skor, signifikansi, transisi status) di service/domain layer, bukan di view/template."_

Setiap app memiliki folder `services/` untuk memisahkan logika bisnis dari views. Ini memudahkan testing dan maintenance.

### 4. `templates/` — Template Organization

- **`base.html`**: Layout utama (dark mode, sidebar, header) — semua halaman extend ini
- **`components/`**: Komponen HTML reusable (sidebar, header, pagination)
- **`partials/`**: Fragment HTML untuk HTMX partial swap (prefix `_`)
- **`<app_name>/`**: Template spesifik per app, sesuai konvensi Django

Konvensi penamaan partial HTMX: **prefix underscore** (`_cluster_list.html`) menandakan ini bukan halaman utuh, melainkan fragment untuk HTMX swap.

### 5. `static/` — Frontend Assets

- **Tailwind CSS**: `input.css` → compile → `output.css` via Tailwind CLI
- **HTMX & Chart.js**: Di-serve sebagai static files
- **`app.js`**: Inisialisasi Chart.js graphs dan konfigurasi HTMX

### 6. `fixtures/` — Data Dummy Sprint 1

Numbered prefix (`01_`, `02_`, ...) untuk urutan `loaddata` yang benar (karena FK dependencies). Load semua:

```bash
python manage.py loaddata fixtures/01_users.json fixtures/02_apps.json ...
```

---

## URL Patterns (dari Gherkin §9)

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('', include('accounts.urls')),
    path('ekstraksi/', include('extraction.urls')),           # /ekstraksi
    path('susun-user-story/', include('stories.urls')),       # /susun-user-story
    path('validasi-ekstraksi/', include('extraction.urls')),  # /validasi-ekstraksi/{id}
    path('user-story/', include('stories.urls')),             # /user-story/{id}
    path('backlog/', include('backlog.urls')),                # /backlog, /backlog/{id}
]
```

> **Catatan:** URL path di atas mengikuti jalur Gherkin persis seperti §9 Project Context.

---

## Catatan Penting

1. **Custom User Model** (`accounts.User`) HARUS dibuat **sebelum** `python manage.py migrate` pertama kali
2. **`id`/`data-testid`** di template harus cocok dengan nama section Gherkin: `hasil-cluster`, `daftar-user-story`, `menunggu-penyusunan` (§9)
3. **Split settings** memerlukan environment variable `DJANGO_SETTINGS_MODULE` — set di `.env`
4. **Tailwind CSS** memerlukan Node.js untuk compile — install via `package.json`
5. **DBMS**: PostgreSQL (sesuai rekomendasi OPEN-01, belum final — `[USULAN]`)
