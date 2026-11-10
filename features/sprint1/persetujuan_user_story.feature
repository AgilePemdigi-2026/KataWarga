# FR-APP — Validasi dan Persetujuan User Story (Backlog #8)
Feature: User Story Approval Feature
  As a Product Owner,
  I want to review and approve the system-generated user stories based on their priority,
  So that only genuinely valuable requirements enter the development backlog.

  Scenario: FR-APP-01 Setujui user story berprioritas tinggi (Happy Path)
    Given ada user story dengan kategori prioritas "TINGGI" dan status "MENUNGGU_PERSETUJUAN"
    When Product Owner menyetujui user story tersebut
    Then status user story berubah menjadi "DISETUJUI"
    And tanggal persetujuan tercatat

  Scenario: FR-APP-02 Abaikan user story berprioritas rendah
    Given ada user story dengan kategori prioritas "RENDAH" dan status "MENUNGGU_PERSETUJUAN"
    When Product Owner mengabaikan user story tersebut
    Then status user story berubah menjadi "DIABAIKAN"
    And user story tidak masuk ke backlog

