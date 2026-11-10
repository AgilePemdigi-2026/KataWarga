# FR-EKS-08, FR-EKS-09 — Ekstraksi dan Pengelompokan Ulasan (Backlog #5)
Feature: Review Extraction and Clustering Feature
  As a Requirements Engineer,
  I want to run the automatic review extraction and clustering process,
  So that I can obtain structured user complaints without manually reading thousands of raw reviews.

  Scenario: FR-EKS-01 Jalankan ekstraksi dan dapatkan cluster baru (Happy Path)
    Given saya memiliki ulasan yang sudah diekstraksi dengan status TERVALIDASI
    When saya menjalankan proses clustering
    Then cluster baru berhasil dibuat dari hasil ekstraksi

  Scenario: FR-EKS-02 Ulasan pendek atau generik difilter otomatis
    Given saya memiliki ulasan "bagus" untuk aplikasi "SATU SEHAT"
    When saya menjalankan proses ekstraksi
    Then ulasan "bagus" tidak muncul di hasil ekstraksi

  Scenario: FR-EKS-03 Ulasan dengan keluhan serupa dikelompokkan ke cluster yang sama
    Given saya memiliki ulasan "aplikasi selalu force close saat login"
    And saya memiliki ulasan "aplikasi keluar sendiri waktu masuk"
    When saya menjalankan proses clustering
    Then kedua ulasan masuk ke dalam cluster yang sama

