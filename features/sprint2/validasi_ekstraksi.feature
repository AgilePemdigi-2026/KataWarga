# FR-VAL-01 s/d FR-VAL-05 — Validasi Hasil Ekstraksi (Backlog #6)
Feature: Extraction Result Validation Feature
  As an Analyst,
  I want to validate the who-what-why extraction results before they are processed further,
  So that the resulting user stories are accurate and do not mislead the development team.

  Scenario: FR-VAL-01 Setujui hasil ekstraksi yang valid (Happy Path)
    Given saya memiliki cluster dengan status "MENUNGGU_VALIDASI"
    And field "who" berisi "wajib pajak"
    And field "what" berisi "gagal login"
    When saya menyetujui cluster tersebut sebagai Analyst
    Then status cluster berubah menjadi "TERVALIDASI"

  Scenario: FR-VAL-02 Tolak hasil ekstraksi yang tidak valid
    Given saya memiliki cluster dengan status "MENUNGGU_VALIDASI"
    And field "who" kosong
    When saya menolak cluster tersebut sebagai Analyst
    Then status cluster berubah menjadi "DIABAIKAN"
    And cluster tidak muncul di antrian menunggu penyusunan

  Scenario: FR-VAL-03 Non-Analyst tidak bisa mengakses validasi
    Given saya adalah pengguna dengan peran "TIM_DEVELOPER"
    When saya mengakses halaman validasi ekstraksi
    Then saya menerima respons 403 Forbidden

