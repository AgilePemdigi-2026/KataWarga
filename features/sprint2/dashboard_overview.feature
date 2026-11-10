# FR-DSH — Melihat Dashboard Overview (Backlog #11)
Feature: Dashboard Overview Feature
  As an authenticated user (RE, Analyst, PO, Developer),
  I want to view the high-level overview dashboard with summary metrics,
  So that I can monitor the review extraction pipeline and backlog progress in real time.

  Scenario: FR-DSH-01 Pengguna login melihat ringkasan metrik di dashboard (Happy Path)
    Given saya adalah pengguna terotentikasi yang sudah login
    And sistem memiliki data ulasan, cluster, dan user story
    When saya membuka halaman dashboard
    Then saya melihat halaman dashboard dengan status 200
    And saya melihat metrik ringkasan ulasan, cluster, dan user story

  Scenario: FR-DSH-02 Pengguna belum login dialihkan ke halaman login
    Given saya adalah pengguna anonim yang belum login
    When saya membuka halaman dashboard
    Then saya dialihkan ke halaman login
