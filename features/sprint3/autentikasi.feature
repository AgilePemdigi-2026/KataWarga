# FR-AUT-01 s/d FR-AUT-03 — Autentikasi Pengguna (Backlog #1, #2, #3)
Feature: User Authentication Feature
  As a team member or new user,
  I want to sign up, log in, and log out securely,
  So that access to KataWarga is authenticated and protected.

  Scenario: FR-AUT-04 Pengguna baru mendaftar akun (Sign Up Happy Path)
    Given saya adalah pengunjung yang belum memiliki akun
    When saya mendaftar dengan username "user_baru", email "baru@katawarga.test", dan password "Rahasia123!"
    Then akun "user_baru" berhasil dibuat di database
    And saya dialihkan ke halaman login

  Scenario: FR-AUT-05 Pendaftaran gagal jika email sudah terdaftar
    Given ada pengguna terdaftar dengan email "sama@katawarga.test"
    When saya mendaftar dengan username "user_lain" dan email "sama@katawarga.test"
    Then sistem menolak pendaftaran dan akun "user_lain" tidak dibuat

  Scenario: FR-AUT-06 Pengguna aktif berhasil login (Login Happy Path)
    Given ada pengguna aktif dengan username "user_aktif" dan password "Password123!"
    When saya melakukan login dengan username "user_aktif" dan password "Password123!"
    Then login berhasil dan saya dialihkan ke halaman utama
    And sesi pengguna "user_aktif" aktif

  Scenario: FR-AUT-07 Login ditolak jika password salah
    Given ada pengguna aktif dengan username "user_aktif" dan password "Password123!"
    When saya melakukan login dengan username "user_aktif" dan password salah "Salah123!"
    Then login ditolak dan saya tetap di halaman login

  Scenario: FR-AUT-08 Pengguna login melakukan logout via POST
    Given saya adalah pengguna yang sudah login
    When saya melakukan logout dengan request POST
    Then sesi login berakhir dan saya dialihkan ke halaman login

  Scenario: FR-AUT-09 Request GET pada logout ditolak
    Given saya adalah pengguna yang sudah login
    When saya mengakses logout dengan request GET
    Then saya menerima respons 403 Forbidden

