# Sprint 3 — AI, NLP & Backend: catatan teknis

## 1. Alur pipeline dan status tiap tahap
scrape → **filter** (aturan; alasan dibuang disimpan di `Ulasan.alasan_filter`) → **ekstraksi** (LLM; galat di `GalatEkstraksi`)
→ **clustering** (embedding WHAT) → **validasi analis** (`HasilEkstraksi.status_validasi`, `Cluster.status_cluster`, jejak di `LogValidasi`)
→ susun user story → persetujuan PO.
`GET /api/v1/ulasan/` mengembalikan status keempat tahap itu per ulasan (dihitung dari data tersimpan, selalu konsisten).

## 2. Penyedia LLM
| Penyedia | Ekstraktor | Env | Catatan |
|---|---|---|---|
| Gemini (utama) | `--extractor gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.1-flash-lite`, `GEMINI_RPM=12` | batch 50 ulasan/permintaan |
| LLM kampus (opsional) | `--extractor kampus` | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL=gemma4:12b`, `LLM_TIMEOUT=180`, `LLM_BATCH=15` | hanya terjangkau dari aplikasi yang di-deploy di server kampus |
Embedding: `EMBED_PROVIDER=gemini` (default, `gemini-embedding-001`, 768 dim). Server kampus belum punya model embedding.

## 3. Kalibrasi ambang clustering (gemini-embedding-001, 101 hasil ekstraksi)
| ambang | cluster | singleton | terbesar | silhouette |
|---|---|---|---|---|
| 0.05 | 81 | 67 | 6 | 0.155 |
| 0.08 | 54 | 34 | 15 | 0.180 |
| **0.10** | 35 | 16 | 19 | **0.201** |
| 0.12 | 23 | 10 | 21 | 0.164 |
| 0.14 | 12 | 6 | 32 | 0.169 |
| 0.16 | 5 | 2 | 86 | 0.109 |
| 0.18 | 2 | 1 | 100 | 0.230 (degenerasi) |
| 0.20 | 1 | 0 | 101 | – |

Dipilih **0.10**. Pada 0.12 cluster terbesar menjadi kumpulan umum (pendaftaran akun, melihat identitas, tanpa bukti fisik) dan
"verifikasi data" bercampur dengan "unduh data". Kelemahan 0.10: 16 singleton yang seharusnya bergabung dan wakil cluster
kecil yang terlalu spesifik; analis dapat menggabung/menolak. Ambang pada artikel acuan (0.5) tidak dapat dipakai karena
bergantung pada model embedding. Opsi `--pusatkan` (kurangi vektor rata-rata) tersedia; kalibrasi ulang bila dipakai.

## 4. API JSON (`/api/v1/`)
Semua respons: `{"status": "success"|"error", "data": ..., "error": null|{"code","message"}, "meta": {...}}`.
Autentikasi sesi Django; POST wajib `X-CSRFToken` dan body JSON. Peran: RE dan Analyst membaca, hanya Analyst memvalidasi.

| Metode | Path | Fungsi |
|---|---|---|
| GET | `/ringkasan/` | hitungan per tahap |
| GET | `/ulasan/?aplikasi=&filter=` | ulasan + status 4 tahap |
| GET | `/ekstraksi/?status=&aplikasi=&cluster=` | daftar user story (WHO/WHAT/WHY) |
| GET | `/ekstraksi/<id>/` | detail + evidence + ulasan asli |
| GET | `/ekstraksi/<id>/riwayat/` | jejak validasi (siapa, kapan, lama → baru) |
| POST | `/ekstraksi/<id>/setujui/` | `{"catatan"?}` |
| POST | `/ekstraksi/<id>/tolak/` | `{"alasan"?}` |
| POST | `/ekstraksi/<id>/perbaiki/` | `{"who"?, "what"?, "why"?, "catatan"?}` |
| GET | `/cluster/?status=` , `/cluster/<id>/` | daftar / detail + anggota |
| POST | `/cluster/<id>/setujui/` , `/tolak/` | validasi cluster |

Paginasi: `?halaman=&ukuran=` (maks. 100); metadata di `meta`. Kode galat: `tidak_login` 401, `akses_ditolak` 403,
`tidak_ditemukan` 404, `metode_tidak_diizinkan` 405, `permintaan_tidak_valid` 400, `status_tidak_valid` 409.
