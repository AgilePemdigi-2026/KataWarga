Project: Sistem Ekstraksi User Story Otomatis berbasis NLP dari Ulasan Aplikasi E-Government Indonesia

## 1. Design Principles

- **Visual Style:** Dark mode, modern, clean, dan profesional.
- **Layout:** Dashboard dengan sidebar.
- **Primary Color:** Electric Indigo (`#6366F1`).
- **Typography:** Inter, dengan fallback Roboto dan system-ui.
- **Responsiveness:** Desktop, tablet, dan mobile.
- **Main Workflow:** Raw Reviews → BIO Entity Tagging → User Stories → Sprint Backlog.

## 2. Color Palette

| Token          | Hex       | Penggunaan            |
| -------------- | --------- | --------------------- |
| Background     | `#0F172A` | Background utama      |
| Surface        | `#1E293B` | Sidebar dan cards     |
| Primary        | `#6366F1` | Tombol dan menu aktif |
| Positive       | `#10B981` | WHY, status aktif     |
| Negative       | `#EF4444` | WHAT, error           |
| Neutral        | `#F59E0B` | Peringatan            |
| Text Primary   | `#F1F5F9` | Judul dan teks utama  |
| Text Secondary | `#94A3B8` | Deskripsi             |
| Border         | `#334155` | Garis pemisah         |

## 3. Global Layout
### Sidebar

- Logo aplikasi.
- Dashboard Overview.
- Extraction Pipeline.
- User Story Backlog.
- Model Performance.
- Settings.
- Profil pengguna

### Header
- Judul halaman.
- Search bar.
- Upload CSV.
- Notifikasi.
- Profil pengguna.

### Main Content
- Konten mengikuti halaman yang sedang dibuka.
- Details Panel tersedia di halaman Extraction Pipeline dan tertutup secara default.

## 4. Pages & Features
### Page 1: Dashboard Overview
- Total Scraped Reviews.
- Filtered Noise Rate.
- Extracted User Stories.
- Model Confidence Score.
- Grafik sentimen dan generasi user story.
- Biggest Topic Cluster.
- Target Applications: SATU SEHAT, IKD, dan M-Pajak.

### Page 2: Extraction Pipeline
- Daftar ulasan aplikasi.
- Rating dan nama aplikasi.
- BIO tagging:
  - WHO: biru.
  - WHAT: merah.
  - WHY: hijau.
- Detail token dan confidence score.
- Search dan Filter.

### Page 3: User Story Backlog
- Kanban tiga kolom:
  - To Review.
  - Sprint Backlog.
  - Dismissed.
- Setiap card berisi aplikasi, prioritas, user story, dan cluster.
- Approve memindahkan card ke Sprint Backlog.
- Dismiss memindahkan card ke Dismissed.

### Page 4: Model Performance
- Expert Judgment Validation Module.
- Perbandingan Ground Truth dan System Prediction.
- Source Review.
- Perbandingan WHAT dan WHY.
- Overall Score.

## 5. Interaction & UX
- Menu aktif menggunakan warna indigo.
- Hover card mengubah warna border.
- Approve dan Dismiss langsung memperbarui posisi card.
- Keyboard focus terlihat jelas.
- Animasi transisi 150–200 ms.
- Layout menyesuaikan ukuran layar.

## 6. Tech Stack
- React + Vite.
- Recharts.
- Lucide Icons.
- CSS.
- pnpm.
