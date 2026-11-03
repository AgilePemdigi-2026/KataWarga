"""
KataWarga — Base settings.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Baca file .env di root proyek (lihat .env.example). Variabel yang sudah
# diset di environment/shell tetap menang (override=False).
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-only-katawarga')

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # === KataWarga Apps ===
    'accounts',
    'reviews',
    'extraction',
    'stories',
    'backlog',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'katawarga'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5433'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Stub peran dev (§4): dipakai selama Sprint 1-2 sebelum auth jadi
DEV_ACTING_ROLE = os.environ.get('DEV_ACTING_ROLE', 'REQUIREMENTS_ENGINEER')

# Parameter skor prioritas user story (§7, TBD-02)  # TBD-02 / USULAN
STORY_SCORING = {
    'min_ulasan': 5,
    'n_ref': 100,
    'bobot_f': 0.7,
    'bobot_s': 0.3,
    'batas_tinggi': 70,
    'batas_sedang': 35,
}

# ---------------------------------------------------------------------------
# Scraping Play Store (§8, FR-EKS-03/04/05/10/11). Semua nilai berlabel
# TBD/USULAN sengaja dijadikan konfigurasi, bukan hardcode.
# ---------------------------------------------------------------------------
SCRAPING = {
    'lang': 'id',
    'country': 'id',
    'jumlah_default': 200,        # ulasan per aplikasi per penarikan  # TBD-12 / USULAN
    'batch_size': 200,            # ulasan per permintaan ke Play Store
    'jeda_detik': 2.0,            # jeda antar-permintaan (§3.2.3)
    'max_retry': 4,               # percobaan ulang per permintaan
    'backoff_dasar_detik': 2.0,   # backoff bertahap: 2, 4, 8, 16 detik
    'min_kata': 3,                # ulasan < min_kata dibuang  # TBD-01 / USULAN
    'pola_generik': [             # ulasan yang isinya hanya ini dibuang  # TBD-01 / USULAN
        'bagus', 'mantap', 'keren', 'ok', 'oke', 'good', 'nice', 'baik',
        'jelek', 'sip', 'top', 'wow', 'terbaik', 'bagus banget',
        'mantap jiwa', 'bagus sekali', 'sangat bagus', 'lumayan',
    ],
    'samarkan_username': True,    # TBD-10 / USULAN: username di-hash, bukan disimpan asli
}

# Aplikasi target (§1). package_name TIDAK ada di SRS (Project_Context §8):
# kosongkan bila belum diverifikasi; command akan melewatinya dan memberi peringatan.
SCRAPER_TARGET_APPS = [
    # Verifikasi package_name di URL Play Store: play.google.com/store/apps/details?id=<package_name>
    {'nama_aplikasi': 'SATU SEHAT', 'package_name': 'com.telkom.tracencare', 'kategori': 'Kesehatan'},  # VERIFIKASI
    {'nama_aplikasi': 'IKD', 'package_name': 'gov.dukcapil.mobile_id', 'kategori': 'Kependudukan'},     # VERIFIKASI
    {'nama_aplikasi': 'M-Pajak', 'package_name': '', 'kategori': 'Perpajakan'},                         # ISI DULU
]

# ---------------------------------------------------------------------------
# Ekstraksi who-what-why (FR-EKS-06, §8). Ekstraktor dapat diganti tanpa
# mengubah pipeline: isi 'ekstraktor' dengan nama terdaftar atau dotted path
# ke kelas turunan extraction.services.base.Ekstraktor (mis. IndoBERT nanti).
# ---------------------------------------------------------------------------
EXTRACTION = {
    'ekstraktor': 'aturan',     # ekstraktor awal berbasis aturan (baseline)  # USULAN
    'max_hasil_per_ulasan': 3,  # satu ulasan boleh menghasilkan >1 hasil (FR-EKS-06)
    'batch_size': 100,          # ulasan per transaksi
}
