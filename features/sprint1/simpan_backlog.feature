# FR-SIM — Penyimpanan User Story ke Backlog (Backlog #9)
Feature: User Story Backlog Saving Feature
  As a Product Owner,
  I want the approved user stories to be saved automatically to the development backlog,
  So that the Tim Developer can immediately pick up validated requirements without manual re-entry.

  Scenario: FR-SIM-01 User story yang disetujui tersimpan ke backlog (Happy Path)
    Given ada user story dengan status "MENUNGGU_PERSETUJUAN"
    When Product Owner menyetujui user story tersebut
    Then user story tersimpan di backlog dengan status "SIAP_DIEKSEKUSI"

  Scenario: FR-SIM-02 User story yang sudah ada di backlog tidak terduplikasi
    Given ada user story yang sudah disetujui dan masuk ke backlog
    When sistem mencoba menyimpan user story yang sama ke backlog lagi
    Then backlog hanya berisi satu item untuk user story tersebut

  Scenario: FR-SIM-03 Gagal menyimpan ke backlog melakukan rollback
    Given ada user story dengan status "MENUNGGU_PERSETUJUAN"
    And penyimpanan backlog gagal karena kesalahan sistem
    When Product Owner menyetujui user story tersebut
    Then status user story tetap "MENUNGGU_PERSETUJUAN"
    And backlog tidak bertambah item baru

