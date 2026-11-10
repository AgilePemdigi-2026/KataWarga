# FR-BKL — Eksekusi Item Backlog (Backlog #10)
Feature: Backlog Execution Feature
  As a Tim Developer,
  I want to pick up and mark the progress status of backlog items,
  So that the team can track the resolution progress of user complaints.

  Scenario: FR-BKL-01 Tandai item backlog mulai dikerjakan (Happy Path)
    Given ada backlog item dengan status "SIAP_DIEKSEKUSI"
    When Tim Developer menekan tombol Mulai Kerjakan
    Then status backlog item berubah menjadi "SEDANG_DIKERJAKAN"
    And waktu mulai dikerjakan tercatat

  Scenario: FR-BKL-02 Tandai item backlog selesai dikerjakan
    Given ada backlog item dengan status "SEDANG_DIKERJAKAN"
    When Tim Developer menekan tombol Tandai Selesai
    Then status backlog item berubah menjadi "SELESAI"

  Scenario: FR-BKL-03 Non-developer tidak bisa mengeksekusi backlog
    Given ada backlog item dengan status "SIAP_DIEKSEKUSI"
    And saya adalah pengguna dengan peran "PRODUCT_OWNER"
    When saya mencoba memulai pengerjaan item backlog
    Then saya menerima respons 403 Forbidden

  Scenario: FR-BKL-04 Transisi tidak valid ditolak
    Given ada backlog item dengan status "SIAP_DIEKSEKUSI"
    When Tim Developer menekan tombol Tandai Selesai secara langsung
    Then sistem menolak dengan pesan error transisi tidak valid

