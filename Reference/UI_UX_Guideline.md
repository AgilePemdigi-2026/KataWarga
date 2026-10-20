# KataWarga: UI/UX Guidelines

> Letakkan di `Reference/UI_UX_Guidelines.md`. Pelengkap `Project_Context.md` §9 dan `Folder_Structure.md`.
> Label sumber sama seperti `Project_Context.md`: `[KEPUTUSAN]`, `[SRS]`, `[USULAN]`, `[OPEN]`. Jika bertentangan, `Project_Context.md` menang; laporkan konfliknya.
> **Stack UI: Django Templates + HTMX + Tailwind CSS + Chart.js** `[KEPUTUSAN]`. Tidak memakai React, Vite, atau Recharts.

---

## 1. Prinsip desain

- **Gaya:** dark mode, modern, bersih, profesional `[KEPUTUSAN]`.
- **Layout:** dashboard dengan sidebar kiri `[SRS 3.1]`.
- **Warna utama:** Electric Indigo `#6366F1`.
- **Alur utama:** Raw Reviews → BIO Entity Tagging → User Stories → Sprint Backlog.
- **Prioritas platform:** desktop dulu (SRS: layar ≥ 1280 px). Tablet dan mobile adalah tambahan `[USULAN]`, jangan mengorbankan jadwal fitur Must.
- **Server-rendered:** logika tampilan di template Django. Interaksi lewat HTMX (partial HTML), bukan SPA.
- **Satu sumber kebenaran status:** UI tidak boleh menampilkan status yang belum disimpan server (tanpa optimistic update), karena perubahan status berupa transaksi atomik (FR-SIM-04).

## 2. Design tokens

### Warna

| Token | Hex | Pemakaian | Kontras (WCAG) |
|---|---|---|---|
| `bg` | `#0F172A` | Latar utama | - |
| `surface` | `#1E293B` | Sidebar, kartu, panel | - |
| `border` | `#334155` | Garis pemisah | 1,41 vs surface (dekoratif; **bukan** penanda elemen interaktif) |
| `text` | `#F1F5F9` | Judul, teks utama | 13,35 di surface |
| `text-muted` | `#94A3B8` | Deskripsi, meta | 5,71 di surface |
| `primary` | `#6366F1` | Aksen, indikator menu aktif, ikon | 3,27 di surface: **jangan untuk teks kecil** |
| `primary-300` | `#818CF8` | Teks/tautan aksen, **focus ring** | 4,90 di surface |
| `primary-600` | `#4F46E5` | **Isi tombol utama** (teks putih) | 6,29 dengan teks putih (`#6366F1` hanya 4,47) |
| `who` | `#60A5FA` | Elemen WHO | 5,75 di surface |
| `what` | `#EF4444` | Elemen WHAT (highlight) | 3,89 di surface: hanya untuk highlight/garis |
| `why` | `#10B981` | Elemen WHY, status aktif/online | 5,77 di surface |
| `warning` | `#F59E0B` | Peringatan, prioritas Sedang | 6,81 di surface |
| `danger-text` | `#F87171` | Teks error / aksi destruktif | 5,29 di surface |

Aturan: warna **tidak boleh jadi satu-satunya penanda** (lihat §8). `#EF4444` dipakai untuk WHAT (sesuai SRS) sekaligus error; teks error memakai `danger-text` dan selalu disertai ikon/kata.

### CSS variables dan Tailwind

```css
/* static/src/input.css */
:root {
  --bg: #0F172A;  --surface: #1E293B;  --border: #334155;
  --text: #F1F5F9; --text-muted: #94A3B8;
  --primary: #6366F1; --primary-300: #818CF8; --primary-600: #4F46E5;
  --who: #60A5FA; --what: #EF4444; --why: #10B981;
  --warning: #F59E0B; --danger-text: #F87171;
}
```

```js
// tailwind.config.js (theme.extend.colors); nama kelas: bg-surface, text-muted, border-line, dst.
colors: {
  bg: 'var(--bg)', surface: 'var(--surface)', line: 'var(--border)',
  ink: 'var(--text)', muted: 'var(--text-muted)',
  primary: { DEFAULT: 'var(--primary)', 300: 'var(--primary-300)', 600: 'var(--primary-600)' },
  who: 'var(--who)', what: 'var(--what)', why: 'var(--why)',
  warning: 'var(--warning)', danger: 'var(--danger-text)',
}
```

Warna Chart.js dibaca dari CSS variables yang sama (`getComputedStyle`), jangan menulis hex ulang di JS.

### Tipografi

- Font: **Inter**, fallback `Roboto, system-ui, sans-serif`. Self-host `Inter` variable `.woff2` di `static/fonts/` dengan `font-display: swap` (tanpa CDN) `[USULAN]`.
- Skala: 12 px (meta) · 14 px (isi padat/kartu) · 16 px (isi) · 20 px (judul halaman) · 24 px (angka metrik, `tabular-nums`).
- Bobot: 400 isi, 500 label, 600 judul/tombol.

### Bentuk dan gerak

- Radius: kartu 12 px, tombol/input 8 px, badge penuh (pill).
- Transisi **150–200 ms** (warna, border, bayangan). Hormati `prefers-reduced-motion` (matikan transisi dan animasi).
- Target sentuh/klik minimal **40 px** tinggi.

## 3. Layout global

### Sidebar `[SRS 3.1]`

- Lebar 256 px, tetap (fixed) pada ≥ 1024 px; di bawahnya menjadi **drawer** yang dibuka tombol di header (fokus terkunci, `Esc` menutup).
- Isi: logo KataWarga · modul · (opsional) indikator SYSTEM (status IndoBERT dan Scraper API) · kartu pengguna di bawah (nama dan peran).
- Modul: Dashboard Overview · Extraction Pipeline · User Story Backlog.
- **Hanya tampilkan menu untuk halaman yang sudah ada dan boleh diakses peran** `[USULAN]` (hindari tautan mati). Tetap enforce 403 di server.
- **Model Performance** dan **Settings** tidak ditampilkan: Model Performance belum masuk backlog (OPEN-04), Settings tidak ada di SRS.
- Menu aktif: latar `primary` 15%, garis kiri 3 px `primary`, teks `primary-300`, `aria-current="page"`.

### Header

- Tinggi 64 px, sticky. Isi: tombol drawer (di bawah lg) · judul halaman · pencarian (hanya di halaman yang punya fungsi pencarian) · notifikasi · menu profil.
- **Upload CSV dihapus** dari guideline: tidak ada di SRS/FR (OPEN-07). Kembalikan hanya jika tim memutuskan.
- **Notifikasi:** pipeline gagal diberitahukan ke Requirements Engineer (FR-EKS-12, Should).
- **Menu profil:** nama, peran, **Logout** (Backlog #3).
- Pesan sistem (Django `messages`) tampil sebagai toast, bukan di header.

### Konten utama

- Padding 24 px (≥ lg) / 16 px. Lebar penuh; grid 12 kolom untuk dashboard.
- **Details Panel** (khusus Extraction Pipeline): tertutup default, dibuka dengan klik kartu; di ≥ lg berupa panel kanan 400 px, di bawahnya overlay penuh. `Esc` menutup.

## 4. Halaman

| Halaman | Route | Backlog | Sprint | Prio |
|---|---|:-:|:-:|---|
| Dashboard Overview | `/` | #11 | 2 | Should |
| Extraction Pipeline | `/ekstraksi` | #5 | 2 | Must |
| Validasi Ekstraksi | `/validasi-ekstraksi`, `/validasi-ekstraksi/{id}` | #6 | 2 | Must |
| Susun User Story | `/susun-user-story` | #7 | 1 | Must |
| User Story Backlog (Kanban) | `/backlog` (**UI-01**) | #8, #9, #10 | 1 | Must |
| Detail User Story | `/user-story/{id}` | #8 | 1 | Must |
| Detail Backlog | `/backlog/{id}` | #10 | 1 | Must |
| Login, Register | `/login`, `/register` | #1-3 | 3 | Must |
| Model Performance | - | belum di backlog | - | jangan dibangun |

Teks tombol/pesan dan jalur URL harus **persis** seperti Gherkin (`Project_Context.md` §6).

### 4.1 Dashboard Overview (#11, Should)

- Empat kartu metrik: **Total Scraped Reviews**, **Filtered Noise Rate**, **Extracted User Stories**, **Model Confidence Score** (grid 1/2/4 kolom).
- Grafik garis: volume sentimen ulasan vs pembentukan user story. Sentimen diturunkan dari rating bintang (proksi, SRS Bab 1.4.1).
- Grafik batang horizontal: **Biggest Topic Cluster**.
- Panel **Target Applications** (SATU SEHAT, IKD, M-Pajak): status koneksi, sinkronisasi terakhir, rata-rata rating, distribusi bintang.
- Chart.js: `responsive: true`, `maintainAspectRatio: false` dalam kontainer tinggi tetap; data dari endpoint JSON; destroy/re-init saat swap HTMX; setiap `<canvas>` punya `aria-label` dan ringkasan angka sebagai teks; seri dibedakan juga lewat pola garis/penanda, bukan warna saja.
- Muat ≤ 3-5 detik (NFR); tampilkan skeleton selama memuat.

### 4.2 Extraction Pipeline (#5)

- Tombol **"Jalankan Ekstraksi"** (primary, hanya Requirements Engineer). Selama berjalan: indikator progres dan tombol nonaktif; selesai: toast **"Proses ekstraksi selesai"** dan section `id="hasil-cluster"` diperbarui.
- Daftar kartu ulasan: rating bintang, tag aplikasi, teks dengan **highlight BIO** (lihat §5.3).
- Search dan Filter (aplikasi, rating) `[USULAN, Could]`: `hx-get` dengan debounce 300 ms.
- **Details Panel** `[USULAN]`: teks asli, entitas WHO/WHAT/WHY, dan **skor keyakinan per hasil**. Model data hanya menyimpan `skor_confidence` per hasil ekstraksi, **bukan per token**; detail confidence per token tidak dibangun sampai ada keputusan (UI-03).

### 4.3 Validasi Ekstraksi (#6)

- Daftar hasil/cluster "menunggu validasi" → detail: teks ulasan asli, label dengan highlight (elemen kosong ditulis jelas, mis. "WHO: tidak terdeteksi"), anggota cluster.
- Tombol **"Setujui"** dan **"Tolak"** (hanya Analyst). Setelah aksi: status "Tervalidasi" atau "Dihapus" tampil, dan hasil tidak muncul lagi di `menunggu-penyusunan`.

### 4.4 Susun User Story (#7)

- Tombol **"Susun User Story"** (Requirements Engineer) dan section `id="daftar-user-story"` sebagai target `hx-swap`.
- Kartu user story: kalimat "Sebagai [who], saya ingin [what], supaya [why]", badge kategori prioritas, skor, tag aplikasi, rincian skor (jumlah ulasan, rata-rata sentimen, komponen frekuensi; FR-USR-10).

### 4.5 User Story Backlog / Kanban (#8, #9, #10)

- **Tiga kolom:** To Review · Sprint Backlog · Dismissed (nama kolom Inggris mengikuti mockup, OPEN-05). Kolom *In Progress* dan *Done* (FR-APP-07/D-05) ditambahkan bersama #10 `[USULAN]`. Tiap kolom punya penghitung.
- Kartu: tag aplikasi, badge prioritas, skor, kalimat user story, label cluster.
- Aksi pada kartu To Review (hanya Product Owner): **"Setujui"** dan **"Abaikan"** (alasan opsional lewat popover kecil). Peran lain tidak melihat tombol.
- Filter: aplikasi dan kategori prioritas; urut skor menurun (FR-APP-01).
- **Perilaku `[USULAN]`:** aksi mengirim `hx-post`; server mengembalikan kolom yang berubah (OOB swap) beserta penghitung dan toast. Kartu pindah hanya setelah server sukses. Jika gagal, kartu tetap di tempat dan toast menampilkan **"Gagal menyimpan ke backlog"**.
- **Dua pintu masuk, satu logika:** "Setujui" dari **papan** memperbarui papan di tempat; "Setujui" dari **halaman detail** (`/user-story/{id}`) mengarahkan ke `/backlog` (FR-APP-03, Gherkin 5.2.4). Keduanya memanggil endpoint dan service yang sama.
- **Tanpa drag-and-drop** di v1: perpindahan status punya aturan bisnis dan hanya lewat tombol.
- Mobile: kolom menjadi tab (dengan penghitung).

### 4.6 Model Performance (belum dibangun)

Spesifikasi disimpan untuk nanti (SRS 3.1e, TBD-04): Expert Judgment Validation Module · Source Review · dua kolom Ground Truth vs System Prediction · WHAT Match dan WHY Match · Overall Score.

## 5. Komponen

### 5.1 Tombol

| Varian | Gaya | Dipakai untuk |
|---|---|---|
| Primary | isi `primary-600`, teks putih; hover `#4338CA` | Jalankan Ekstraksi, Susun User Story, Setujui |
| Secondary | border `line`, teks `ink`; hover border `primary` | aksi netral |
| Destructive | border `danger`, teks `danger-text` | Abaikan, Tolak |

Tinggi 40 px, teks 14 px/600. Status disabled dan loading (spinner `htmx-indicator`) wajib ada.

### 5.2 Kartu

Latar `surface`, border 1 px `line`, radius 12 px, padding 16 px. Hover: border berubah ke `primary` (transisi 150 ms); hover hanya pada kartu yang bisa diklik.

### 5.3 Highlight BIO `[KEPUTUSAN]`

| Elemen | Warna | Label |
|---|---|---|
| WHO | biru `who` | `WHO` |
| WHAT | merah `what` | `WHAT` |
| WHY | hijau `why` | `WHY` |

Implementasi `<mark>`: latar warna elemen alpha 20%, **garis bawah 2 px** warna elemen, dan label kecil (WHO/WHAT/WHY) di atas/samping. Teks `#F1F5F9` di atas tint tetap berkontras ≥ 9,3. Legenda warna ditampilkan di halaman yang memakai highlight. Catatan: SRS teks hanya menyebut WHAT merah dan WHY hijau; WHO biru berasal dari guideline tim dan mockup.

### 5.4 Badge prioritas `[USULAN]`

Tinggi = tint merah + teks `danger-text` · Sedang = tint `warning` · Rendah = tint slate. Selalu berisi **teks** ("Tinggi"/"Sedang"/"Rendah"), bukan hanya warna. Elemen detail memakai `data-testid="prioritas"`; status memakai `data-testid="status"`.

### 5.5 Toast, empty, loading, error

- **Toast:** dari Django `messages`; `role="status"` (sukses, hilang 5 detik) atau `role="alert"` (error, menetap sampai ditutup).
- **Empty state:** satu kalimat + satu aksi (mis. "Belum ada user story. Tekan Susun User Story.").
- **Loading:** `htmx-indicator` untuk aksi; skeleton untuk kartu metrik dan grafik.
- **Error:** halaman 403/404/500 memakai layout yang sama; aksi ditolak server menampilkan toast, tanpa perubahan tampilan.

## 6. Interaksi dan UX

- Menu aktif indigo; hover kartu mengubah border; transisi 150-200 ms.
- Aksi Setujui/Abaikan/Mulai/Selesai memakai HTMX dan memperbarui bagian halaman yang berubah.
- Semua rute tanpa trailing slash, sesuai Gherkin; POST ke jalur yang sama dengan Gherkin.
- Aksi final (Abaikan, Tolak) tidak punya undo di SRS: tanpa dialog konfirmasi, tetapi label harus jelas, Abaikan menyediakan alasan opsional, dan hasilnya ditegaskan lewat toast.

## 7. Responsif `[USULAN]`

| Lebar | Perilaku |
|---|---|
| ≥ 1280 px | Target utama SRS: sidebar tetap, Kanban 3 kolom, Details Panel 400 px |
| 1024-1279 px | Sidebar tetap, grid metrik 2 kolom |
| 768-1023 px | Sidebar menjadi drawer, Kanban 2-3 kolom scroll horizontal |
| < 768 px | Satu kolom; Kanban menjadi tab; daftar tabel menjadi kartu bertumpuk; Details Panel layar penuh |

## 8. Aksesibilitas (target WCAG 2.1 AA)

- Kontras sesuai tabel §2; teks `primary` di atas gelap memakai `primary-300`.
- Warna bukan satu-satunya penanda: label WHO/WHAT/WHY + garis bawah, teks pada badge prioritas, ikon+kata untuk error.
- **Focus** selalu terlihat: ring 2 px `primary-300` dengan offset 2 px; pakai `:focus-visible`.
- Landmark: `<nav>`, `<main>`, `<aside>`; tautan "Lewati ke konten" di awal halaman.
- Area yang diperbarui HTMX (`#hasil-cluster`, `#daftar-user-story`, penghitung kolom) memakai `aria-live="polite"`; setelah swap, fokus tidak boleh hilang (pindahkan ke judul bagian atau toast).
- Drawer/panel/popover: fokus terkunci saat terbuka, `Esc` menutup, fokus kembali ke pemicu.
- Semua tombol ikon punya `aria-label`.
- ID/atribut uji dari Gherkin dipertahankan: `hasil-cluster`, `daftar-user-story`, `menunggu-penyusunan`, `data-testid="prioritas"`, `data-testid="status"`.

## 9. Teknis frontend

| Aspek | Keputusan |
|---|---|
| Rendering | Django Templates (global `templates/<app>/`, partial diawali `_`) `[KEPUTUSAN]` |
| Interaksi | HTMX; header CSRF lewat `hx-headers` di `<body>` |
| Styling | Tailwind CSS (`static/src/input.css` → `static/dist/output.css`), tanpa framework CSS lain |
| Grafik | Chart.js, file lokal di `static/js/` |
| Ikon | Lucide sebagai **inline SVG** (salin ikon yang dipakai ke `templates/components/icons/`), tanpa pustaka JS runtime `[USULAN]` |
| Font | Inter self-host `[USULAN]` |
| Node | Hanya untuk build Tailwind; manajer paket **pnpm** |
| Aset pihak ketiga | Disalin lokal dan versinya dikunci (tidak memakai CDN) |

Tidak dipakai: React, Vite, Recharts, dan CSS kustom di luar token dan highlight BIO.

## 10. Keputusan terbuka UI

| ID | Pertanyaan | Rekomendasi |
|---|---|---|
| UI-01 | Route Kanban: `/backlog` (menurut `Folder_Structure.md`) atau `/user-story`? Dan siapa pemilik view (stories atau backlog)? Papan memadukan `UserStory` (To Review, Dismissed) dan item backlog (Sprint Backlog). | Satu halaman `/backlog` sebagai "User Story Backlog"; selama #9 belum ada, kolom Sprint Backlog membaca `UserStory` berstatus Disetujui |
| UI-02 | Search/Filter di Extraction Pipeline dibangun? | Could; setelah #5 stabil |
| UI-03 | Confidence **per token** di Details Panel? | Tidak ada datanya di model; tampilkan skor per hasil saja |
| UI-04 | Kolom In Progress dan Done | Tambahkan bersama #10 |
| OPEN-04 | Model Performance masuk backlog? | Lihat `Project_Context.md` §13 |
| OPEN-05 | Bahasa label UI | Tombol/pesan Indonesia; nama kolom Kanban Inggris |
| OPEN-07 | Upload CSV | Dihapus dari guideline sampai diputuskan |