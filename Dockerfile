# ==============================================================================
# KataWarga — Production Dockerfile untuk Coolify (https://katawarga.caiis.ai.id)
# ==============================================================================
FROM python:3.12-slim

# Mencegah pembuatan file .pyc dan memastikan output log langsung ke console
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PORT=8000

WORKDIR /app

# Install system dependencies (build-essential, libpq-dev untuk psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install dependencies
COPY requirements/base.txt requirements/prod.txt requirements/

# Install CPU-only PyTorch terlebih dahulu untuk menghemat ~2.3GB download size di server Coolify,
# kemudian install sisa dependensi produksi
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch>=2.0.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements/prod.txt

# Copy source code proyek
COPY . .

# Expose port internal aplikasi
EXPOSE 8000

# Entrypoint: Migrasi DB, collectstatic, inisialisasi akun demo/admin, lalu jalankan Gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py init_roles_admin && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -"]
