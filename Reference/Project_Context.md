# KataWarga: PROJECT_CONTEXT

> Konteks tunggal proyek untuk **tim (3 orang) dan AI assistant di IDE**.
> Letakkan di root repo. Semua AI harus membaca file ini sebelum menulis kode, merencanakan, atau menjawab pertanyaan tentang proyek.

- **Proyek:** KataWarga, ekstraksi otomatis user story dari ulasan aplikasi e-government publik menggunakan NLP
- **Mata kuliah:** Pembangunan Perangkat Lunak (PPL), S1 Sistem Informasi, FST Universitas Airlangga. Dosen: Dr. Indra Kharisma Raharjana, S.Kom., M.T.
- **Tim:** Kelompok 3
- **Sumber:** SRS KataWarga (8 Oktober 2026) dan dokumen Progress Pembangunan Perangkat Lunak Sprint 1 (Minggu ke-9)
- **Versi file:** 1.0 (20 Oktober 2026)

## Label sumber (dipakai di seluruh file)

| Label | Arti | Prioritas |
|---|---|---|
| `[KEPUTUSAN]` | Sudah diputuskan tim (termasuk dokumen progress dan diskusi tim) | 1 (tertinggi) |
| `[SRS]` | Tertulis di SRS 8 Okt 2026 | 2 |
| `[USULAN]` | Rekomendasi, belum disepakati tim | 3 |
| `[TBD-nn]` | Belum ditentukan (daftar di §13) | harus ditanyakan |

Jika dua label bertentangan, label dengan prioritas lebih tinggi menang. Laporkan konfliknya, jangan diam-diam memilih.

---

## 0. Aturan untuk AI (WAJIB)

1. Perlakukan file ini sebagai sumber kebenaran. Rujuk bagian yang relevan dengan menyebut nomor bagian (mis. "sesuai §6.3, FR-USR-02").
2. **Jangan mengarang** kebutuhan, nilai, nama paket, rumus, atau keputusan. Jika informasi tidak ada atau berlabel `[TBD]`/`[USULAN]`:
   - jadikan nilai itu **konfigurasi** (settings/konstanta bernama) dengan komentar `# TBD-nn` atau `# USULAN`, dan
   - tanyakan ke pengguna sebelum mengunci.
3. **Jangan membangun** apa pun di luar ruang lingkup (§12). Jika diminta, ingatkan dulu.
4. Jika permintaan pengguna bertentangan dengan file ini, **sebutkan konfliknya lebih dulu**, lalu tunggu keputusan.
5. Gunakan teks UI, nama status, dan jalur URL **persis** seperti §6, karena skenario Gherkin dipakai sebagai uji penerimaan.
6. Perubahan status yang saling terkait harus dalam satu transaksi atomik (`transaction.atomic()`), terutama persetujuan user story dan pembuatan item backlog (FR-SIM-04).
7. Kegagalan scraping atau NLP tidak boleh merusak atau menghapus data yang sudah ada, dan tidak boleh menghentikan seluruh pipeline (graceful degradation, §10).
8. Setiap fitur baru: buat uji dari kriteria penerimaan di §6 (Gherkin → test), bukan hanya "jalan di browser".
9. Jawab dalam Bahasa Indonesia. Istilah teknis boleh tetap bahasa Inggris.
10. Jika keputusan berubah, usulkan **patch untuk file ini** (bagian + label baru). Jangan hanya mengubah kode.
11. Jangan menaruh data pribadi, kredensial, atau data ulasan mentah ke repo. Username pengulas wajib disamarkan `[TBD-10]`.

---

## 1. Ringkasan produk `[SRS]`

**Masalah.** Ulasan publik di Play Store adalah sumber kebutuhan yang kaya, tetapi dibaca manual (lambat, subjektif). Contoh: 16.245 ulasan SATU SEHAT, 12.551 bersentimen negatif berdasarkan rating bintang.

**Solusi.** Sistem web + pipeline NLP yang:
1. men-scrape ulasan **SATU SEHAT, IKD, M-Pajak** dari Google Play Store (berbahasa Indonesia),
2. menyaring ulasan terlalu pendek atau generik,
3. mengekstraksi **who / what / why** dengan **IndoBERT** (token classification, format BIO),
4. mengelompokkan dan mendeduplikasi hasil berdasarkan kemiripan semantik (cluster),
5. menyusun user story berformat **"Sebagai [who], saya ingin [what], supaya [why]"** dengan skor prioritas,
6. memberi jalur validasi manusia: **Analyst** memvalidasi ekstraksi, **Product Owner** menyetujui user story, **Tim Developer** melacak status eksekusi backlog.

**Sasaran terukur:**

| ID | Sasaran | Indikator |
|---|---|---|
| O-1 | Memproses semua ulasan yang ditarik | 100% ulasan lolos filter punya hasil ekstraksi atau status filter tercatat |
| O-2 | Ekstraksi who-what-why berkualitas | Precision/recall/F1 per elemen vs ground truth ahli; target F1 `[TBD-06]` |
| O-3 | Format requirement seragam | Semua user story berformat baku |
| O-4 | Prioritas kuantitatif | Setiap user story punya skor yang dapat ditelusuri ke ulasan sumber |

Sistem ini **prototipe berbasis web** dengan arsitektur **pipeline-based**.



---

## 3. Stack dan arsitektur

### Keputusan tim `[KEPUTUSAN]`

| Lapisan | Pilihan |
|---|---|
| Bahasa | Python |
| Web framework | **Django** (monolit, server-rendered) |
| Interaksi frontend | **HTMX** (partial update, tanpa SPA) |
| Styling | **Tailwind CSS** |
| Grafik | **Chart.js** |
| NLP | Hugging Face Transformers + PyTorch, model IndoBERT (usulan basis: `indobenchmark/indobert-base-p1`) `[SRS]` |
| Scraping | `google-play-scraper` `[SRS]` |
| Penjadwalan | cron job atau scheduler setara `[SRS]` |
| Basis data | **PostgreSQL** (RDBMS) `[KEPUTUSAN]` |

### Belum diputuskan `[USULAN]`

- **DBMS:** sudah diputuskan **PostgreSQL** `[KEPUTUSAN]`. ERD di SRS memakai tipe gaya Oracle (`NUMBER`, `VARCHAR2`, `CLOB`); terjemahkan ke tipe Django/PostgreSQL.
- **Background job:** pipeline berjalan di background agar web tetap responsif `[SRS]`. Pilihan implementasi: management command + cron, atau Celery + Redis bila tombol "Jalankan Ekstraksi" harus tidak memblokir.
- **Pembagian app Django, model user, dan konvensi kode:** lihat §15 serta `Reference/Folder_Structure.md`.

### Arsitektur logis `[SRS]`

```
Google Play Store (eksternal)
        │ ulasan (HTTPS, jeda + backoff)
        ▼
Scheduler (cron) / tombol "Jalankan Ekstraksi"
        ▼
Scraper & Filter → Ekstraktor who-what-why (IndoBERT, BIO) → Clustering & Deduplikasi → Penyusun User Story & Skor
        └──────────────── semua menyimpan ke ────────────────► Basis Data Relasional ◄──► Antarmuka Web (Dashboard, Pipeline, Backlog, Model Performance) ──► Autentikasi & Otorisasi Peran
```

- Komunikasi klien-server: HTTPS. Seluruh halaman dan endpoint hanya melayani HTTPS.
- Pertukaran data: JSON via endpoint REST (SRS 3.2). Dengan Django + HTMX, respons partial HTML boleh dipakai di UI, tetapi bila ada endpoint data (mis. grafik Chart.js), sediakan JSON.
- Inferensi IndoBERT berbasis **CPU**. GPU hanya opsional untuk fine-tuning di luar server produksi.
- Server: Linux; spesifikasi minimum server aplikasi 4 vCPU, RAM ≥ 8 GB, penyimpanan ≥ 50 GB. Klien: PC/laptop dengan browser modern, lebar layar ≥ 1280 px.
- Berkas server: bobot model, konfigurasi, dan log kegagalan (waktu, aplikasi, penyebab). Akses dibatasi ke proses sistem.

---

## 4. Peran dan RBAC

Empat peran `[SRS]`: `REQUIREMENTS_ENGINEER`, `ANALYST`, `PRODUCT_OWNER`, `TIM_DEVELOPER`.

| Fungsi | Requirements Engineer | Analyst | Product Owner | Tim Developer |
|---|:-:|:-:|:-:|:-:|
| Jalankan/atur pipeline ekstraksi (UC-1), terima notifikasi gagal | ✔ | | | |
| Validasi hasil ekstraksi: Setujui/Tolak (UC-2) | | ✔ | | |
| Susun dan prioritaskan user story (UC-3) | ✔ | | | |
| Setujui/Abaikan user story → backlog (UC-4, UC-5) | | | ✔ (hanya PO) | |
| Eksekusi item backlog: Mulai Kerjakan/Tandai Selesai (UC-6) | | | | ✔ |
| Lihat Dashboard, daftar backlog, Model Performance | `[TBD]` akses baca antar peran | | | |
| Kelola akun dan peran | `[TBD-09]` usulan: Requirements Engineer atau administrator | | | |

- "Hanya Product Owner yang berhak menyetujui user story masuk Backlog" adalah aturan keamanan eksplisit `[SRS 5.3]`.
- Akses ditolak → HTTP 403. Belum login → 401/redirect ke Login. `[SRS 3.2.4]`
- **Sprint 1 berjalan sebelum Login/RBAC jadi** `[KEPUTUSAN]` (Login di Sprint 3, Kelola Akses Role di Sprint 2). Selama itu gunakan **stub peran khusus dev** (mis. setting `DEV_ACTING_ROLE` atau pemilih peran di mode `DEBUG`). Jangan hardcode peran di view. Siapkan pemeriksaan peran sebagai decorator/mixin agar tinggal diaktifkan.

---

## 5. Model data

8 entitas `[SRS: ERD/CDM-PDM]`. Tipe di bawah sudah dipetakan kasar ke Django. Nama kolom aslinya Indonesia (`ID_ULASAN`, dst.); **bahasa penamaan kode belum diputuskan** (OPEN-06).

### Relasi

```
APLIKASI 1──* ULASAN 1──* HASIL_EKSTRAKSI *──* CLUSTER (lewat CLUSTER_ANGGOTA)
CLUSTER 1──0..1 USER_STORY 1──0..1 BACKLOG_ITEM
PENGGUNA 1──* HASIL_EKSTRAKSI (validator), USER_STORY (penyetuju), BACKLOG_ITEM (pengerja)
```

- `USER_STORY.id_cluster` unik: satu cluster menghasilkan paling banyak satu user story.
- `BACKLOG_ITEM.id_user_story` unik: relasi 1:1 user story ↔ backlog item (FR-SIM-02/03).
- Satu ulasan dapat menghasilkan **lebih dari satu** hasil ekstraksi (FR-EKS-06).

### Tabel

| Entitas | Kolom (tipe, catatan) |
|---|---|
| **PENGGUNA** | id, nama (≤150), email (≤150, unik), role (≤30), tanggal_dibuat. *Kredensial (password) tidak ada di ERD; pakai mekanisme auth Django.* |
| **APLIKASI** | id, nama_aplikasi (≤100), package_name (≤150, unik), kategori (≤100, opsional), aktif (bool) |
| **ULASAN** | id, aplikasi (FK), username_reviewer (≤150, opsional; **samarkan**, TBD-10), isi_ulasan (teks panjang), tanggal_ulasan (date), skor_bintang (1 digit), status_filter (≤20: `LOLOS`/`DIBUANG`), tanggal_scraping |
| **HASIL_EKSTRAKSI** | id, ulasan (FK), teks_who (≤100, opsional), teks_what (≤1000, wajib), teks_why (≤1000, opsional), skor_confidence (desimal 5,4), status_validasi (≤20), pengguna (FK validator), tanggal_ekstraksi, tanggal_validasi |
| **CLUSTER** | id, nama_topik (≤200), jumlah_anggota, skor_signifikansi (desimal 5,2), status_cluster (≤20), tanggal_dibuat |
| **CLUSTER_ANGGOTA** | PK gabungan (cluster, hasil_ekstraksi), tanggal_cluster_anggota |
| **USER_STORY** | id, cluster (FK, unik), peran/who (≤200), kebutuhan/what (≤1000), alasan/why (≤1000), skor_prioritas (5,2), kategori_prioritas (≤10), status_persetujuan (≤25), pengguna (FK penyetuju), alasan_diabaikan (≤500, opsional), tanggal_disusun, tanggal_persetujuan (opsional) |
| **BACKLOG_ITEM** | id, user_story (FK, unik), status_eksekusi (≤25), pengguna (FK pengerja = `DIKERJAKAN_OLEH`), tanggal_masuk_backlog, tanggal_mulai_dikerjakan (opsional), tanggal_selesai (opsional) |

### Enumerasi status `[SRS: class diagram]`

| Enum | Nilai |
|---|---|
| `RolePengguna` | `REQUIREMENTS_ENGINEER`, `ANALYST`, `PRODUCT_OWNER`, `TIM_DEVELOPER` |
| `StatusFilter` (ulasan) | `LOLOS`, `DIBUANG` |
| `StatusValidasi` (hasil ekstraksi) | `MENUNGGU_VALIDASI`, `TERVALIDASI`, `DIHAPUS` (soft delete) |
| `StatusCluster` | `MENUNGGU_VALIDASI`, `TERVALIDASI`, `SIGNIFIKAN`, `DIABAIKAN` |
| `StatusUserStory` | `MENUNGGU_PERSETUJUAN`, `DISETUJUI`, `DIABAIKAN` |
| `LevelPrioritas` | `TINGGI`, `SEDANG`, `RENDAH` |
| `StatusEksekusi` (backlog) | `SIAP_DIEKSEKUSI`, `SEDANG_DIKERJAKAN`, `SELESAI` |

### Perhatian pada ERD (lihat juga §14)

- Kolom `pengguna` pada `HASIL_EKSTRAKSI`, `USER_STORY`, `BACKLOG_ITEM` ditandai wajib (NOT NULL) di ERD, padahal baris dibuat oleh pipeline sebelum ada validator/penyetuju/pengerja. **Rekomendasi `[USULAN]`: jadikan nullable** sampai tindakan manusia terjadi, dan tulis keputusannya di sini.
- `HASIL_EKSTRAKSI` memuat dua kolom mirip: `TEXT_WHO` dan `TEKS_WHO` (salah ketik di ERD). Pakai **satu** kolom `teks_who`.
- `CLUSTER_ANGGOTA.TANGGAL_CLUSTER_ANGGOTA` bertipe "UNKNOWN" di ERD; pakai timestamp.
- Hasil ekstraksi yang ditolak ditandai `DIHAPUS` (**soft delete**), tidak dihapus fisik.

---

## 6. Fitur dan kebutuhan fungsional

Pemetaan penomoran: dokumen progress memakai **Backlog #1 sampai 11**; SRS memakai **Fitur/UC-1 sampai 6**.

| Backlog # | Nama | SRS | FR prefix | Priority | Effort | Sprint |
|:-:|---|---|---|---|:-:|:-:|
| 1 | Register | tidak ada | (FR-AUT) | Must | S (1) | 3 |
| 2 | Login | tidak ada (Fitur 4.7, TBD-09) | (FR-AUT) | Must | S (1) | 3 |
| 3 | Logout | tidak ada | (FR-AUT) | Must | S (1) | 3 |
| 4 | Kelola Akses Role | NFR 5.3 saja | (FR-AUT) | Must | M (2) | 2 |
| 5 | Mengekstraksi dan Mengelompokkan Ulasan | UC-1 / Fitur 1 | FR-EKS | Must | XXL (5) | 2 |
| 6 | Memvalidasi Hasil Ekstraksi | UC-2 / Fitur 2 | FR-VAL | Must | M (2) | 2 |
| 7 | Menyusun dan Memprioritaskan User Story | UC-3 / Fitur 3 | FR-USR | Must | XL (4) | 1 |
| 8 | Memvalidasi dan Menyetujui User Story | UC-4 / Fitur 4 | FR-APP | Must | L (3) | 1 |
| 9 | Menyimpan User Story ke Backlog | UC-5 / Fitur 5 | FR-SIM | Must | M (2) | 1 |
| 10 | Mengeksekusi Item Backlog | UC-6 / Fitur 6 | FR-BKL | Must | M (2) | 1 |
| 11 | Melihat Dashboard Overview | Bab 3.1(a) | (FR-DSH) | **Should** | M (2) | 2 |

Prioritas FR memakai MoSCoW: Must = wajib v1.0, Should = sangat dianjurkan, Could = opsional.

Alur end-to-end `[SRS]`:
`UC-1 ekstraksi+cluster → UC-2 Analyst validasi → UC-3 susun user story+skor → UC-4 PO setujui/abaikan → UC-5 simpan ke backlog (otomatis, «include» dari UC-4) → UC-6 Developer eksekusi`

### 6.1 Backlog #5: Mengekstraksi dan Mengelompokkan Ulasan (UC-1, FR-EKS)

- Aktor primer: Requirements Engineer. Sekunder: model IndoBERT, Google Play Store.
- Prakondisi: aplikasi target terkonfigurasi; **model IndoBERT hasil fine-tuning sudah tersedia**; jadwal scraping ada.
- Trigger: cron job, atau tombol manual.
- Pascakondisi sukses: cluster tersimpan berstatus "menunggu validasi Analyst" → UC-2. Gagal: tidak ada perubahan data, log kegagalan, coba ulang di jadwal berikutnya.

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-EKS-01 | Pipeline terpicu otomatis sesuai jadwal yang dapat dikonfigurasi | Must |
| FR-EKS-02 | Tombol **"Jalankan Ekstraksi"** di halaman Extraction Pipeline memicu manual; setelah selesai tampil pesan **"Proses ekstraksi selesai"** dan bagian **`hasil-cluster`** | Must |
| FR-EKS-03 | Tarik ulasan tiap aplikasi aktif; simpan username, isi, tanggal, skor bintang | Must |
| FR-EKS-04 | Cegah ulasan yang sama tersimpan dua kali | Must |
| FR-EKS-05 | Saring ulasan terlalu pendek/generik (mis. "bagus"); catat di `status_filter`; ulasan tersaring tidak muncul di `hasil-cluster`. Kriteria `[TBD-01]` | Must |
| FR-EKS-06 | Ekstraksi who/what/why dengan IndoBERT (BIO) untuk ulasan lolos filter; satu ulasan bisa menghasilkan banyak hasil | Must |
| FR-EKS-07 | Ulasan melebihi batas 512 token dipecah per kalimat atau dipotong terkontrol agar tetap diproses | Should |
| FR-EKS-08 | Cluster + deduplikasi berdasarkan kemiripan semantik (mis. "aplikasi selalu force close saat login" dan "aplikasi keluar sendiri waktu masuk" satu cluster) | Must |
| FR-EKS-09 | Simpan cluster dengan status "menunggu validasi Analyst" | Must |
| FR-EKS-10 | Scraping gagal → catat log (waktu, aplikasi, penyebab), data lama tak berubah, coba ulang di jadwal berikutnya | Must |
| FR-EKS-11 | Kegagalan satu aplikasi tidak menghentikan aplikasi lain | Should |
| FR-EKS-12 | Notifikasi ke Requirements Engineer saat pipeline gagal | Should |
| FR-EKS-13 | Halaman Extraction Pipeline menampilkan kartu ulasan: rating bintang, tag aplikasi, teks dengan highlight who/what/why | Should |

**Kriteria penerimaan (Gherkin 5.2.1), halaman `/ekstraksi`:**
- Happy path: tekan "Jalankan Ekstraksi" → muncul "Proses ekstraksi selesai" dan section `hasil-cluster` baru.
- Ulasan "bagus" untuk SATU SEHAT tidak muncul di `hasil-cluster`.
- Dua ulasan "aplikasi selalu force close saat login" dan "aplikasi keluar sendiri waktu masuk" berada di cluster yang sama.

### 6.2 Backlog #6: Memvalidasi Hasil Ekstraksi (UC-2, FR-VAL)

- Aktor: Analyst (quality gate manusia, sekaligus sumber ground truth).
- Prakondisi: cluster/hasil berstatus "menunggu validasi" dari UC-1.
- Sukses: hasil berstatus `TERVALIDASI` → UC-3. Gagal/ditolak: `DIHAPUS`, dicatat "hasil tidak dimasukkan ke backlog".

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-VAL-01 | Tampilkan daftar hasil/cluster "menunggu validasi" | Must |
| FR-VAL-02 | Detail: teks ulasan asli, label who/what/why (highlight; elemen kosong ditampilkan jelas), anggota cluster | Must |
| FR-VAL-03 | Tombol **"Setujui"** → `TERVALIDASI`; catat validator (pengguna) dan waktu; teruskan ke UC-3 | Must |
| FR-VAL-04 | Tombol **"Tolak"** → `DIHAPUS`; catat "hasil tidak dimasukkan ke backlog"; keluar dari antrean, tidak ke UC-3 | Must |
| FR-VAL-05 | Hasil yang sudah divalidasi/ditolak tidak boleh diproses ulang (aksi ganda ditolak dengan pesan jelas) | Should |
| FR-VAL-06 | Analyst dapat mengoreksi label sebelum menyetujui; koreksi disimpan sebagai ground truth untuk evaluasi model | Could |

**Penerimaan (Gherkin 5.2.3), halaman `/validasi-ekstraksi/{id}`:**
- who "wajib pajak", what "gagal login", tekan "Setujui" → status "Tervalidasi".
- who kosong, tekan "Tolak" → status "Dihapus" dan hasil tidak muncul di section `menunggu-penyusunan`.

### 6.3 Backlog #7: Menyusun dan Memprioritaskan User Story (UC-3, FR-USR)

- Aktor: Requirements Engineer. Trigger: ada cluster baru berstatus tervalidasi (event-driven) atau tombol manual.
- Alt: cluster di bawah ambang → `DIABAIKAN`, tidak jadi user story.

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-USR-01 | Mulai otomatis saat ada cluster tervalidasi baru; sediakan tombol **"Susun User Story"** di halaman penyusunan | Must |
| FR-USR-02 | Nilai signifikansi = jumlah ulasan **unik** anggota vs ambang minimum (nilai awal **5**, `[TBD-02]`); di bawah ambang → "diabaikan", tidak muncul di `daftar-user-story` | Must |
| FR-USR-03 | Rumuskan "Sebagai [who], saya ingin [what], supaya [why]" dari elemen paling representatif cluster `[TBD-03]` | Must |
| FR-USR-04 | Jika cluster tak punya who: pakai bawaan "pengguna aplikasi [nama aplikasi]" dan tandai agar diperiksa PO | Should |
| FR-USR-05 | Hitung skor prioritas dari frekuensi + intensitas sentimen (BR-04, §7) | Must |
| FR-USR-06 | Petakan skor ke kategori Tinggi/Sedang/Rendah (BR-05, §7); tampil di kolom prioritas | Must |
| FR-USR-07 | Simpan user story berstatus "menunggu persetujuan Product Owner" dengan tautan ke cluster dan ulasan sumber | Must |
| FR-USR-08 | Tampilkan user story baru berawalan "Sebagai" di bagian **`daftar-user-story`** | Must |
| FR-USR-09 | Ambang, bobot, batas kategori dapat diubah lewat konfigurasi tanpa mengubah kode | Should |
| FR-USR-10 | Tampilkan rincian skor (jumlah ulasan, rata-rata sentimen, komponen frekuensi) | Should |

**Penerimaan (Gherkin 5.2.2), halaman `/susun-user-story`:**
- Cluster signifikan → user story berawalan "Sebagai" muncul di `daftar-user-story`.
- Cluster "Warna Tombol" dengan 2 ulasan → tidak muncul di `daftar-user-story`.
- Skor menurut ukuran cluster: **150 → Tinggi; 40 → Sedang; 5 → Rendah**.

### 6.4 Backlog #8: Memvalidasi dan Menyetujui User Story (UC-4, FR-APP)

- Aktor: Product Owner. Prakondisi: ada user story `MENUNGGU_PERSETUJUAN`.

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-APP-01 | Daftar user story "menunggu persetujuan", urut skor tertinggi, filter aplikasi dan kategori prioritas | Must |
| FR-APP-02 | Detail: kalimat user story, skor dan kategori, ulasan sumber | Must |
| FR-APP-03 | Tombol **"Setujui"** → status "Disetujui", buat item backlog "siap dieksekusi", arahkan ke halaman backlog | Must |
| FR-APP-04 | Tombol **"Abaikan"** → status "Diabaikan", simpan alasan opsional, tidak muncul di daftar backlog | Must |
| FR-APP-05 | PO dapat menyesuaikan kategori/urutan prioritas dengan alasan; skor otomatis tetap tersimpan sebagai pembanding | Should |
| FR-APP-06 | PO dapat menyunting teks user story sebelum menyetujui; versi asli tetap tersimpan | Could |
| FR-APP-07 | Halaman User Story Backlog menampilkan papan kolom status (To Review, Sprint Backlog, Dismissed; ditambah In Progress dan Done, keputusan D-05) dengan kartu berisi aplikasi, prioritas, skor frekuensi cluster | Should |

**Penerimaan (Gherkin 5.2.4), halaman `/user-story/{id}`:**
- Prioritas "Tinggi", tekan "Setujui" → status "Disetujui" dan diarahkan ke halaman backlog.
- Prioritas "Rendah", tekan "Abaikan" → status "Diabaikan" dan tidak muncul di daftar backlog.

### 6.5 Backlog #9: Menyimpan User Story ke Backlog (UC-5, FR-SIM)

- «include» dari UC-4: jalan **otomatis** saat PO menyetujui.

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-SIM-01 | Jalankan UC-5 otomatis saat PO menyetujui | Must |
| FR-SIM-02 | Buat item backlog "siap dieksekusi", relasi 1:1 ke user story, bawa skor dan kategori | Must |
| FR-SIM-03 | Cegah duplikasi: user story yang sudah di backlog → tampilkan item yang ada dengan pesan **"User story sudah ada di backlog"** | Must |
| FR-SIM-04 | Ubah status user story → "Disetujui" **dan** buat item backlog dalam **satu transaksi**; jika gagal, batalkan keduanya, status tetap "Menunggu Persetujuan", catat log, pesan **"Gagal menyimpan ke backlog"** | Must |
| FR-SIM-05 | Sukses: pesan **"User story berhasil disimpan ke backlog"**, item tampil di daftar backlog, arahkan PO ke halaman backlog | Must |

**Penerimaan (Gherkin 5.2.5):**
- Dari `/user-story/45` (status "Menunggu Persetujuan") tekan "Setujui" → pesan sukses; item "Siap Dieksekusi" muncul di `/backlog`.
- User story yang sudah disetujui muncul **sekali** di `/backlog`.
- Penyimpanan gagal (`/user-story/47`) → "Gagal menyimpan ke backlog"; status tetap "Menunggu Persetujuan"; tidak ada di daftar backlog.

### 6.6 Backlog #10: Mengeksekusi Item Backlog (UC-6, FR-BKL)

- Aktor: Tim Developer. Coding/rilis dilakukan **di luar sistem**; sistem hanya mencatat status.

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-BKL-01 | Daftar item "siap dieksekusi" dan "sedang dikerjakan", urut prioritas | Must |
| FR-BKL-02 | Detail item: user story, skor prioritas, ulasan sumber | Must |
| FR-BKL-03 | Tombol **"Mulai Kerjakan"** → "Sedang Dikerjakan"; catat pengerja (`DIKERJAKAN_OLEH`) dan waktu mulai | Must |
| FR-BKL-04 | Tombol **"Tandai Selesai"** → "Selesai"; pesan **"Keluhan pengguna telah ditangani"** | Must |
| FR-BKL-05 | Hanya transisi `siap dieksekusi → sedang dikerjakan → selesai`; transisi lain ditolak dengan pesan jelas | Must |
| FR-BKL-06 | Simpan waktu selesai agar lama penyelesaian dapat dilaporkan di Dashboard | Could |

**Penerimaan (Gherkin 5.2.6), halaman `/backlog/{id}`:**
- Tekan "Mulai Kerjakan" → status "Sedang Dikerjakan".
- Dari "Sedang Dikerjakan", tekan "Tandai Selesai" → status "Selesai" dan pesan "Keluhan pengguna telah ditangani".

### 6.7 Backlog #1 sampai #4: Register, Login, Logout, Kelola Akses Role

**Belum ada use case, FR, atau Gherkin di SRS.** SRS hanya menyebut: kontrol akses berbasis peran (§2.4, §5.3), "Autentikasi & Otorisasi Peran" di arsitektur, halaman Login (§3.2.4), prefix `FR-AUT` di konvensi, dan `[TBD-09]` (login wajib; akun dibuat oleh Requirements Engineer atau administrator).

Sebelum menulis kode, AI harus **meminta atau menyusun draf use case + FR-AUT + Gherkin** dan mendapatkan persetujuan tim. Titik awal `[USULAN]`:
- Login wajib; sesi berbasis sesi Django; HTTPS.
- Jika TBD-09 memutuskan akun dibuat oleh admin/RE, **Register mungkin tidak dipakai**, atau menjadi "Kelola Akun". Putuskan lebih dulu (OPEN-03).
- Kelola Akses Role: tetapkan peran per pengguna dan enforce matriks §4 di view dan endpoint (403 bila tak berwenang).
- Custom user model dengan kolom peran dibuat **sebelum migrasi pertama**.

### 6.8 Backlog #11: Melihat Dashboard Overview (Should)

**Belum ada FR/Gherkin**; deskripsi UI di SRS §3.1(a) `[SRS]`:
- Empat metrik: **Total Scraped Reviews**, **Filtered Noise Rate**, **Extracted User Stories**, **Model Confidence Score**.
- Grafik garis: dinamika volume sentimen ulasan vs pembentukan user story (Chart.js).
- Grafik batang horizontal: **Biggest Topic Cluster**.
- Panel kanan: status koneksi, waktu sinkronisasi terakhir, rata-rata rating tiga aplikasi.
- Target waktu muat ≤ ~3–5 detik (§10).

Sumber data tiap metrik belum didefinisikan; turunkan dari tabel §5 dan tandai asumsi. Prioritas Should: **kandidat pertama yang dikorbankan** jika Sprint 3 molor.

### 6.9 Di luar backlog saat ini: Model Performance

Modul "Model Performance" (Expert Judgment: ground truth vs prediksi IndoBERT, WHAT/WHY Match, Overall Score) ada di SRS §3.1(e) dan TBD-04/TBD-11, tetapi **tidak ada di backlog 11 item**. Jangan dibangun sebelum tim memutuskan (OPEN-04).

---

## 7. Aturan bisnis dan skor prioritas

Aturan bisnis `[SRS 5.5]`:
1. Hanya ulasan publik berbahasa Indonesia dari tiga aplikasi target di Google Play Store.
2. User story dan skor hanya dihitung untuk cluster yang **sudah divalidasi Analyst**.
3. Cluster di bawah ambang signifikansi otomatis ditandai "diabaikan".
4. User story **tidak boleh** masuk backlog sebelum berstatus "Disetujui" oleh Product Owner.
5. Pengerjaan teknis (coding, uji, rilis) di luar sistem; sistem hanya melacak status.

**Skor prioritas.** BR-04 dan BR-05 dirujuk di SRS tetapi **rumus lengkapnya tidak tertulis**. Nilai berikut hanya **`[USULAN]` / `[TBD-02]`**, harus berupa **konfigurasi**:

| Parameter | Nilai usulan |
|---|---|
| Ambang signifikansi n (ulasan unik) | ≥ 5 |
| N_ref (normalisasi frekuensi) | 100 |
| Bobot frekuensi F / sentimen S | 0,7 / 0,3 |
| Batas kategori | Tinggi ≥ 70; Sedang 35 sampai < 70; Rendah < 35 (inklusif/eksklusif batas perlu dikonfirmasi) |

Yang **belum didefinisikan**: cara menghitung S (intensitas sentimen). SRS §1.4.1 memakai **rating bintang** sebagai proksi sentimen negatif, jadi S dapat diturunkan dari bintang (`[USULAN]`). Kalibrasi dengan data nyata.

Uji acuan yang **harus lulus** (Gherkin): ukuran cluster 150 → Tinggi, 40 → Sedang, 5 → Rendah; cluster 2 ulasan → diabaikan. Parameter apa pun yang dipilih harus memenuhi keempatnya.

---

## 8. Spesifikasi pipeline NLP

- **Scraping:** `google-play-scraper`; ambil username, isi ulasan, tanggal, skor bintang. Jeda antar-permintaan dan **backoff bertahap** untuk menghindari pembatasan akses. Hanya ulasan berbahasa Indonesia. Dedup agar penarikan berulang tidak menggandakan data.
- **Package name** SATU SEHAT, IKD, M-Pajak **tidak ada di SRS**. Jangan ditebak; minta tim mengisinya dan verifikasi.
- **Filter:** buang ulasan terlalu pendek/generik; kriteria (panjang minimum dan daftar pola generik) ditetapkan dari analisis data nyata `[TBD-01]`.
- **Ekstraksi:** IndoBERT fine-tuned, **token classification format BIO** (label who/what/why, mis. `B-WHAT`, `I-WHAT`, dan padanan WHO/WHY, serta `O`), menghasilkan **skor keyakinan**. Batas masukan **512 token**; ulasan lebih panjang dipecah/dipotong terkontrol.
- **Clustering:** kemiripan semantik antar teks what/why; jumlah cluster **otomatis** (tanpa konfigurasi manual di awal). Model representasi kalimat dan algoritma `[TBD-07]` (usulan awal: embedding kalimat bahasa Indonesia + clustering berbasis kepadatan atau hierarkis; bandingkan pada data).
- **Fine-tuning:** bergantung anotasi manual berskala terbatas (belum ada dataset publik). Ukuran dataset, jumlah anotator, kesepakatan antar-anotator `[TBD-11]` (usulan: ≥ 2 anotator pada sebagian sampel, ukur kappa). Fine-tuning dilakukan di luar server produksi.
- **Prasyarat UC-1:** model hasil fine-tuning harus tersedia/ter-deploy. Selama belum ada, pengembangan hilir memakai **data dummy** (§11).
- **Asumsi sistem:** ulasan dianggap autentik; **tidak ada deteksi buzzer** (hanya filter pendek/generik).
- **Batch processing** terjadwal; inferensi tidak boleh mengganggu responsivitas web.

---

## 9. Antarmuka pengguna `[SRS 3.1]`

- **Dark mode**, **sidebar kiri** untuk navigasi modul, area konten di kanan, bilah pencarian di header.
- Modul di sidebar: **Dashboard Overview**, **Extraction Pipeline**, **User Story Backlog**, **Model Performance** (terakhir tidak di backlog saat ini, lihat §6.9). Indikator SYSTEM: status IndoBERT dan Scraper API.
- **Extraction Pipeline:** kartu ulasan dengan bintang + tag aplikasi; highlight **merah = what**, **hijau = why** (di mockup, who tampak berwarna biru; teks SRS tidak menyebut). Tombol "Jalankan Ekstraksi".
- **User Story Backlog:** papan Kanban kolom To Review / Sprint Backlog / Dismissed (+ In Progress, Done). Kartu: tag aplikasi, prioritas (High/Medium), skor, kalimat user story, label cluster, tombol Approve/Dismiss.
- **Dashboard:** lihat §6.8.
- **Catatan:** mockup memuat tombol **"Upload CSV"** di header yang **tidak ada** di SRS/FR. Jangan dibangun tanpa keputusan (OPEN-07).
- **Bahasa label UI:** FR/Gherkin memakai Indonesia ("Setujui", "Abaikan"); mockup memakai Inggris ("Approve", "Dismiss", nama kolom). Pakai teks FR/Gherkin untuk tombol/pesan yang diuji; nama kolom Kanban mengikuti mockup sampai tim memutuskan (OPEN-05).
- **Implementasi `[KEPUTUSAN]`:** Django Templates + HTMX (aksi Setujui/Tolak/Abaikan/Mulai/Selesai, filter, pesan) + Tailwind + Chart.js. Gunakan `id`/`data-testid` sama dengan nama section Gherkin: `hasil-cluster`, `daftar-user-story`, `menunggu-penyusunan`.
- **Jalur URL dari Gherkin** (pertahankan jalur ini, abaikan port `3000`): `/ekstraksi`, `/susun-user-story`, `/validasi-ekstraksi/{id}`, `/user-story/{id}`, `/backlog`, `/backlog/{id}`.

---

## 10. Kebutuhan non-fungsional `[SRS 5]`

- **Performa:** scraping volume besar (belasan ribu ulasan, mis. 16.245) terjadwal tanpa timeout/crash; batch processing wajar sebelum hasil tampil; muat Dashboard dan daftar backlog **ideal ≤ 3–5 detik**. Target waktu pemrosesan `[TBD-05]`.
- **Safety:** gangguan Play Store tidak merusak/menghapus data lama (log + retry); filter di awal mencegah beban dan "cluster sampah"; kegagalan ekstraksi satu ulasan tidak menghentikan pipeline (**graceful degradation**).
- **Keamanan:** RBAC ketat; HTTPS; hanya PO yang menyetujui user story; perubahan user story dan status backlog hanya oleh peran berwenang.
- **Privasi:** UU No. 27/2022 (PDP); samarkan username pengulas; kebijakan retensi/kepatuhan ToS Play Store `[TBD-10]` (usulan: hapus data mentah di luar keperluan penelitian setelah proyek).
- **Kualitas:** Reliability (format user story baku tak rusak), Usability (intuitif untuk PO/Analyst tanpa latar data science), Maintainability (pipeline **modular**, model dapat diganti/di-fine-tune ulang), Portability (browser modern, tanpa instalasi), Efficiency (batch terjadwal, tidak mengganggu web).
- **Kualitas model:** target F1 `[TBD-06]` (usulan awal ≥ 0,70, tetapkan setelah baseline).

---

## 11. Rencana sprint, status, dan Definition of Done

**Total effort: 25.** Bobot: S(1) · M(2) · L(3) · XL(4) · XXL(5). Estimasi T-shirt bersifat **provisional**.

| Sprint | Backlog | Effort |
|:-:|---|:-:|
| 1 | #7 Menyusun/Memprioritaskan (4), #8 Memvalidasi/Menyetujui (3), #9 Menyimpan (2), #10 Mengeksekusi (2) | 11 |
| 2 | #4 Kelola Akses Role (2), #5 Mengekstraksi/Mengelompokkan (5), #6 Memvalidasi Hasil Ekstraksi (2), #11 Dashboard (2) | 11 |
| 3 | #1 Register (1), #2 Login (1), #3 Logout (1) | 3 |

Status saat ini: Sprint 1, Minggu ke-9 `[KEPUTUSAN]`. Tanggal mulai/selesai sprint belum ditulis.

**Konsekuensi urutan ini (penting untuk AI):**
- Sprint 1 membangun fitur **hilir** lebih dulu (#7–#10), padahal masukan aslinya (cluster tervalidasi dari #5, #6) baru ada di Sprint 2. Maka butuh **seed/fixture data dummy**: aplikasi, ulasan, hasil ekstraksi, cluster tervalidasi, minimal satu user story per kategori prioritas (150/40/5 ulasan), dan item backlog. Taruh di fixture/management command agar semua anggota punya data uji sama.
- Auth belum ada di Sprint 1–2; lihat stub peran di §4.
- #5 (XXL) adalah jalur kritis. Persiapannya (anotasi data, fine-tuning IndoBERT, pilihan DBMS, algoritma clustering) dimulai dari Sprint 1 dan fitur dihitung selesai hanya jika memenuhi Definition of Done.

**Definition of Done `[USULAN]`, belum disepakati tim.** Sebuah backlog dianggap selesai bila:
1. semua FR **Must** fitur itu terpenuhi dan skenario Gherkin terkait lulus sebagai test otomatis,
2. teks UI, status, dan jalur URL sesuai §6/§9,
3. pemeriksaan peran sesuai §4 (kecuali selama stub Sprint 1–2),
4. perubahan status terkait dalam transaksi atomik bila relevan,
5. migrasi berjalan di environment bersih,
6. di-review minimal satu anggota lain lewat pull request,
7. tidak ada error/traceback pada alur utama, dan data uji ada di fixture.

**Stand-up Sprint 1 (ringkas):**

| Anggota | Rencana Sprint 1 `[USULAN]` | Kendala utama |
|---|---|---|
| Baari | #7: penilaian signifikansi, perumusan user story, skor dan kategori, penyimpanan dengan tautan, tombol "Susun User Story", data cluster dummy | TBD-02, TBD-03; cluster asli baru dari Sprint 2 |
| Sakha | #8: halaman User Story Backlog (daftar, detail, papan status), Setujui/Abaikan; tampilan tombol untuk #10 | Bergantung keluaran #7; DBMS belum diputuskan |
| Fauzan | Setup environment/DB/migrasi; #9 (item backlog 1:1, dedup, transaksi atomik); #10 (daftar/detail, transisi status) | DBMS (TBD-08); #9 bergantung #8 |

---

## 12. Di luar ruang lingkup `[SRS 1.4.3, 2.5]`

Jangan dibangun, dan peringatkan jika diminta:
- ulasan App Store (iOS) atau sumber selain Google Play; ulasan non-Indonesia;
- aplikasi e-government selain SATU SEHAT, IKD, M-Pajak;
- deteksi buzzer / ulasan palsu;
- integrasi dua arah dengan Jira, Trello, dan sejenisnya;
- balasan otomatis ke pengulas di Play Store;
- pengerjaan teknis perbaikan aplikasi e-government (coding dan rilis oleh Tim Developer terjadi di luar sistem).

---

## 13. Daftar TBD dan keputusan terbuka

### TBD dari SRS (Lampiran C)

| ID | Hal yang perlu ditentukan | Usulan awal | PIC |
|---|---|---|---|
| TBD-01 | Kriteria ulasan terlalu pendek/generik | Panjang minimum (kata) + daftar pola generik; dari data nyata | Baari |
| TBD-02 | Ambang signifikansi, N_ref, bobot F dan S, batas kategori | n ≥ 5; N_ref 100; 0,7/0,3; batas 70/35; kalibrasi | Baari |
| TBD-03 | Pemilihan elemen who/what/why representatif per cluster | Terdekat centroid atau paling sering muncul | Baari |
| TBD-04 | Kriteria WHAT/WHY Match dan skor evaluasi | Exact + parsial (tumpang tindih token), dua-duanya dilaporkan | Baari |
| TBD-05 | Target waktu pemrosesan | Benchmark di server uji, lalu tetapkan | Baari |
| TBD-06 | Target F1 | Usulan ≥ 0,70 setelah baseline | Baari |
| TBD-07 | Algoritma clustering dan model representasi kalimat | Embedding ID + clustering kepadatan/hierarkis; bandingkan | Fauzan |
| TBD-08 | Framework web/backend dan DBMS | **Framework: Django; DBMS: PostgreSQL** `[KEPUTUSAN]` | Fauzan |
| TBD-09 | Apakah ada login; siapa yang membuat/mengelola akun | Login wajib; akun dibuat RE atau admin | Sakha |
| TBD-10 | Kepatuhan ToS Play Store, penyamaran username, retensi data | Periksa ketentuan; samarkan; hapus data mentah setelah proyek | Fauzan |
| TBD-11 | Ukuran dataset anotasi, jumlah anotator, kesepakatan | ≥ 2 anotator pada sebagian sampel (kappa) | Fauzan |
| TBD-12 | Frekuensi scraping, jumlah ulasan per penarikan | Mingguan; menyesuaikan volume | Fauzan |

### Keputusan terbuka tambahan (muncul saat penyusunan sprint)

| ID | Pertanyaan | Rekomendasi / Keputusan |
|---|---|---|
| OPEN-01 | DBMS apa? | **PostgreSQL** `[KEPUTUSAN]` |
| OPEN-02 | **Unit validasi Analyst: hasil ekstraksi atau cluster?** UC-2 menyebut "hasil atau cluster"; model punya status di kedua tabel; UC-3 mengonsumsi "cluster tervalidasi". Kapan sebuah cluster berstatus `TERVALIDASI`? | Tetapkan aturan eksplisit (mis. cluster tervalidasi bila anggota valid-nya memenuhi ambang) dan tulis di §5/§6.2 |
| OPEN-03 | Register dipakai, atau akun dibuat admin/RE (TBD-09)? | Putuskan sebelum backlog #1 dikerjakan |
| OPEN-04 | Model Performance masuk backlog (Could) atau keluar scope? | Tambahkan sebagai Could, atau nyatakan di luar v1.0 |
| OPEN-05 | Bahasa label UI (Indonesia vs Inggris) | Indonesia untuk tombol/pesan; nama kolom Kanban ikut mockup |
| OPEN-06 | Bahasa penamaan kode (model/field/fungsi) | Pilih satu dan catat di §15 |
| OPEN-07 | Tombol "Upload CSV" di mockup dibangun atau dihapus? | Hapus dari mockup bila di luar scope |
| OPEN-08 | Akses baca Dashboard/backlog/Model Performance per peran | Semua pengguna login dapat melihat; aksi ubah tetap dibatasi |
| OPEN-09 | Definition of Done final | Gunakan usulan di §11 |
| OPEN-10 | Kolom pengguna (validator/penyetuju/pengerja) nullable? | Ya, nullable sampai tindakan manusia terjadi |

---

## 14. Ketidakkonsistenan sumber (jangan diperbaiki diam-diam)

1. NIM Sakha berbeda antara cover SRS (187231017) dan lampiran (187241017).
2. SRS menyebut "Fitur 4.7" (login) dan "Fitur 4.8" (Model Performance) serta prefix FR-AUT/FR-DSH/FR-MDL, tetapi bab fiturnya hanya sampai 4.6.
3. BR-04/BR-05 dirujuk (skor/kategori) tetapi isi lengkapnya tidak ada di Bab 5.5.
4. ERD: kolom pengguna wajib; `TEXT_WHO` vs `TEKS_WHO`; tipe "UNKNOWN" (lihat §5).
5. UC-2 menyebut validasi "hasil atau cluster" tanpa aturan transisi status cluster (OPEN-02).
6. Mockup: tombol "Upload CSV", label Inggris, Extraction Pipeline muncul dua kali di §3.1 (huruf b dan c identik).
7. Gherkin memakai `localhost:3000`; Django default port 8000. Yang dipertahankan hanya jalur URL-nya.
8. FR-APP-07 merujuk keputusan "D-05" dan acceptance merujuk "D-09" yang tidak ada di dokumen ini.

---

## 15. Struktur proyek dan konvensi `[KEPUTUSAN]`

Struktur folder lengkap dan panduan teknis tercatat di `Reference/Folder_Structure.md`.

```
katawarga/
├─ Reference/                # Dokumen referensi (Project_Context.md, Folder_Structure.md)
├─ config/                   # Django settings (base/dev/prod), urls, wsgi, asgi
├─ accounts/                 # Pengguna (custom user + peran), Register/Login/Logout, RBAC
├─ reviews/                  # Aplikasi, Ulasan, scraping & filter service
├─ extraction/               # HasilEkstraksi, Cluster, ClusterAnggota, pipeline NLP, validasi Analyst
├─ stories/                  # UserStory, penyusunan & skor, persetujuan PO
├─ backlog/                  # BacklogItem, eksekusi Developer
├─ dashboard/                # Metrik dan grafik (Chart.js)
├─ templates/                # Base layout, partials HTMX, components
├─ static/                   # Tailwind CSS, Chart.js, HTMX, custom JS
├─ fixtures/                 # Data dummy untuk Sprint 1
├─ logs/                     # Log kegagalan scraping & NLP (FR-EKS-10, §3.2)
├─ ml_models/                # Bobot model IndoBERT fine-tuned (§3.2, §8)
├─ media/                    # Django MEDIA_ROOT
├─ requirements/             # Dependencies (base.txt, dev.txt, prod.txt)
├─ docker-compose.yml        # PostgreSQL 16 container lokal
├─ .env.example              # Template environment variables
└─ .gitignore
```

- **Custom user model** dibuat sebelum `migrate` pertama.
- Status sebagai `TextChoices` bernilai persis enum di §5.
- Logika bisnis (skor, signifikansi, transisi status) di **service/domain layer**, bukan di view/template. Transisi status lewat satu fungsi per transisi agar mudah diuji.
- Parameter TBD (ambang, bobot, batas, N_ref, jadwal scraping) di **satu modul konfigurasi** atau `settings`.
- Pipeline NLP modular: `scrape → filter → extract → cluster → compose` sebagai langkah terpisah yang dapat diuji dan diganti.
- Model IndoBERT dimuat di worker/command, **bukan** di proses web.
- Git: cabang per backlog (`feat/<nomor-backlog>-<slug>`), PR dengan satu reviewer, pesan commit menyebut backlog dan FR (mis. `feat(#9): FR-SIM-04 transaksi atomik`).
- Test: satu test per skenario Gherkin; beri nama test dengan ID FR.

---


# #16. User Story Features
User Story 1: Ekstraksi dan Pengelompokan Ulasan
As a Requirements Engineer,
I want to run the automatic review extraction and clustering process,
So that I can obtain structured user complaints/needs without manually reading thousands of raw reviews.
User Story 2: Penyusunan dan Prioritisasi User Story
As a Requirements Engineer,
I want the system to compose user stories from each review cluster along with a priority score,
So that I can immediately obtain a ready-to-use, priority-ordered list of requirements.
User Story 3: Validasi Hasil Ekstraksi
As an Analyst,
I want to validate the who-what-why extraction results before they are processed further,
So that the resulting user stories are accurate and do not mislead the development team.
User Story 4: Validasi dan Persetujuan User Story
As a Product Owner,
I want to review and approve the system-generated user stories based on their priority,
So that only genuinely valuable requirements enter the development backlog.
User Story 5: Penyimpanan User Story ke Backlog
As a Product Owner,
I want the approved user stories to be saved automatically to the development backlog,
So that the Tim Developer can immediately pick up validated requirements without manual re-entry.
User Story 6: Eksekusi Item Backlog
 As a Tim Developer,
 I want to pick up and mark the progress status of backlog items,
 So that the team can track the resolution progress of user complaints.


## 17, User Story Scenarios
 Ekstraksi dan Pengelompokan Ulasan
Feature: Review Extraction and Clustering Feature
  As a Requirements Engineer,
  I want to run the automatic review extraction and clustering process,
  So that I can obtain structured user complaints without manually reading thousands of raw reviews.

  Scenario: Successfully run extraction and get new review clusters (Happy Path)
    Given I open the extraction page at "http://localhost:3000/ekstraksi"
    When I press the "Jalankan Ekstraksi" button
    Then I should see the message "Proses ekstraksi selesai"
    And I should see a new "hasil-cluster" section on the page

  Scenario: Short or generic reviews are automatically filtered out
    Given I have a review "bagus" for the application "SATU SEHAT"
    When I press the "Jalankan Ekstraksi" button
    Then the review "bagus" should not appear in the "hasil-cluster" section

  Scenario: Reviews with similar complaints are grouped into the same cluster
    Given I have a review "aplikasi selalu force close saat login"
    And I have a review "aplikasi keluar sendiri waktu masuk"
    When I press the "Jalankan Ekstraksi" button
    Then both reviews should appear in the same cluster


Penyusunan dan Prioritas User Story
Feature: User Story Composition and Prioritization Feature
  As a Requirements Engineer,
  I want the system to compose user stories from each review cluster along with a priority score,
  So that I can immediately obtain a ready-to-use, priority-ordered list of requirements.

  Scenario: Successfully compose a user story from a significant cluster (Happy Path)
    Given I open the user story composition page at "http://localhost:3000/susun-user-story"
    When I press the "Susun User Story" button
    Then I should see a new user story starting with "Sebagai" in the "daftar-user-story" section

  Scenario: Insignificant clusters are ignored
    Given I have a cluster "Warna Tombol" with 2 reviews
    When I press the "Susun User Story" button
    Then the cluster "Warna Tombol" should not appear in the "daftar-user-story" section

  Scenario Outline: Priority score is calculated based on cluster size
    Given I have a cluster "<cluster_name>" with <review_count> reviews
    When I press the "Susun User Story" button
    Then the priority score field should show "<priority_result>"

    Examples:
      | cluster_name        | review_count | priority_result |
      | Gagal Login         | 150                 | Tinggi           |
      | Notifikasi Lambat| 40                   | Sedang        |
      | Warna Tombol      | 5                     | Rendah         |


Validasi Hasil Ekstraksi
Feature: Extraction Result Validation Feature
  As an Analyst,
  I want to validate the who-what-why extraction results before they are processed further,
  So that the resulting user stories are accurate and do not mislead the development team.

  Scenario: Approve a valid extraction result (Happy Path)
    Given I open the validation page at "http://localhost:3000/validasi-ekstraksi/1"
    And the "who" field contains "wajib pajak"
    And the "what" field contains "gagal login"
    When I press the "Setujui" button
    Then I should see the status "Tervalidasi"

  Scenario: Reject an invalid extraction result
    Given I open the validation page at "http://localhost:3000/validasi-ekstraksi/2"
    And the "who" field is empty
    When I press the "Tolak" button
    Then I should see the status "Dihapus"
    And the extraction result should not appear in the "menunggu-penyusunan" section


Validasi dan Persetujuan User Story
Feature: User Story Approval Feature
  As a Product Owner,
  I want to review and approve the system-generated user stories based on their priority,
  So that only genuinely valuable requirements enter the development backlog.

  Scenario: Approve a high-priority user story (Happy Path)
    Given I open the user story page at "http://localhost:3000/user-story/45"
    And the priority field shows "Tinggi"
    When I press the "Setujui" button
    Then I should see the status "Disetujui"
    And I should be redirected to the backlog page

  Scenario: Ignore a low-priority user story
    Given I open the user story page at "http://localhost:3000/user-story/46"
    And the priority field shows "Rendah"
    When I press the "Abaikan" button
    Then I should see the status "Diabaikan"
    And the user story should not appear in the backlog list


Penyimpanan User Story ke Backlog

Feature: User Story Backlog Saving Feature
  As a Product Owner,
  I want the approved user stories to be saved automatically to the development backlog,
  So that the Tim Developer can immediately pick up validated requirements without manual re-entry.

  Scenario: Approved user story is saved to the backlog (Happy Path)
    Given I open the user story page at "http://localhost:3000/user-story/45"
    And the status field shows "Menunggu Persetujuan"
    When I press the "Setujui" button
    Then I should see the message "User story berhasil disimpan ke backlog"
    And the backlog item status should be "Siap Dieksekusi"
    And I should see the user story in the backlog list at "http://localhost:3000/backlog"

  Scenario: User story that is already in the backlog is not duplicated
    Given I open the user story page at "http://localhost:3000/user-story/45"
    And I have already approved this user story
    When I open the backlog page at "http://localhost:3000/backlog"
    Then the user story should appear only once in the backlog list

  Scenario: Saving to the backlog fails
    Given I open the user story page at "http://localhost:3000/user-story/47"
    And the backlog storage is unavailable
    When I press the "Setujui" button
    Then I should see the message "Gagal menyimpan ke backlog"
    And the status field should still show "Menunggu Persetujuan"
    And I should not see the user story in the backlog list



Eksekusi Item Backlog  
Feature: Backlog Execution Feature
  As a Tim Developer,
  I want to pick up and mark the progress status of backlog items,
  So that the team can track the resolution progress of user complaints.

  Scenario: Mark a backlog item as in progress (Happy Path)
    Given I open the backlog page at "http://localhost:3000/backlog/45"
    When I press the "Mulai Kerjakan" button
    Then the status field should show "Sedang Dikerjakan"

  Scenario: Mark a backlog item as done
    Given I open the backlog page at "http://localhost:3000/backlog/45"
    And the status field shows "Sedang Dikerjakan"
    When I press the "Tandai Selesai" button
    Then the status field should show "Selesai"
    And I should see the message "Keluhan pengguna telah ditangani"




## 18. Glosarium singkat
gi
| Istilah | Arti |
|---|---|
| Who-What-Why | who = pemangku kepentingan; what = kebutuhan/masalah; why = alasan/dampak |
| BIO | Skema label token: B (awal entitas), I (di dalam), O (di luar) |
| Token classification | Memberi label tiap token dalam teks |
| Fine-tuning | Pelatihan lanjutan model pra-latih pada data teranotasi |
| Cluster / deduplikasi | Mengelompokkan dan menggabungkan hasil ekstraksi yang semantik serupa |
| Ground truth | Anotasi acuan dari ahli untuk menilai model |
| Quality gate | Pemeriksaan manual wajib sebelum data lanjut |
| Soft delete | Menandai data sebagai dihapus tanpa membuangnya |
| RBAC | Pembatasan akses menurut peran |
| MoSCoW | Must / Should / Could / Won't |
| «include» | UC induk selalu menjalankan UC yang disertakan (UC-4 → UC-5) |
| PBI / T-shirt size | Item backlog / estimasi relatif S, M, L, XL, XXL (bobot 1-2-3-4-5) |