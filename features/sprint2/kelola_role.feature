# FR-AUT — Kelola Akses Role (Backlog #4)
Feature: Role Management Feature
  As a Requirements Engineer,
  I want to manage user roles in the system,
  So that each team member can only perform actions appropriate to their role.

  Scenario: FR-AUT-01 Requirements Engineer mengubah role pengguna (Happy Path)
    Given saya adalah pengguna dengan peran "REQUIREMENTS_ENGINEER"
    And ada pengguna lain dengan peran "TIM_DEVELOPER"
    When saya mengubah role pengguna tersebut menjadi "ANALYST"
    Then role pengguna berhasil diubah menjadi "ANALYST"

  Scenario: FR-AUT-02 Non-RE tidak bisa mengakses halaman kelola role
    Given saya adalah pengguna dengan peran "TIM_DEVELOPER"
    When saya mengakses halaman kelola role
    Then saya menerima respons 403 Forbidden

  Scenario: FR-AUT-03 Switch acting role di dev mode
    Given saya adalah pengguna dalam mode dev
    When saya berpindah acting role ke "ANALYST"
    Then acting role aktif menjadi "ANALYST"

