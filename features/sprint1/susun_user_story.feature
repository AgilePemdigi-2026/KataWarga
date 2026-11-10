# FR-USR — Penyusunan dan Prioritisasi User Story (Backlog #7)
Feature: User Story Composition and Prioritization Feature
  As a Requirements Engineer,
  I want the system to compose user stories from each review cluster along with a priority score,
  So that I can immediately obtain a ready-to-use, priority-ordered list of requirements.

  Scenario: FR-USR-01 Susun user story dari cluster signifikan (Happy Path)
    Given ada cluster dengan 10 anggota dan status "TERVALIDASI"
    When saya menjalankan penyusunan user story
    Then user story baru dibuat dengan teks dimulai dari "Sebagai"

  Scenario: FR-USR-02 Cluster tidak signifikan diabaikan
    Given ada cluster bernama "Warna Tombol" dengan 2 anggota dan status "TERVALIDASI"
    When saya menjalankan penyusunan user story
    Then cluster "Warna Tombol" tidak menghasilkan user story

  Scenario Outline: FR-USR-03 Skor prioritas dihitung berdasarkan ukuran cluster
    Given ada cluster "<nama_cluster>" dengan <jumlah_ulasan> anggota dan status "TERVALIDASI"
    When saya menjalankan penyusunan user story
    Then kategori prioritas user story adalah "<hasil_prioritas>"

    Examples:
      | nama_cluster     | jumlah_ulasan | hasil_prioritas |
      | Gagal Login      | 150           | TINGGI          |
      | Notifikasi Lambat| 40            | SEDANG          |
      | Warna Tombol     | 5             | RENDAH          |

