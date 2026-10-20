"""Model Pengguna — custom user dengan role (§4, §5)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class RolePengguna(models.TextChoices):
        REQUIREMENTS_ENGINEER = 'REQUIREMENTS_ENGINEER', 'Requirements Engineer'
        ANALYST = 'ANALYST', 'Analyst'
        PRODUCT_OWNER = 'PRODUCT_OWNER', 'Product Owner'
        TIM_DEVELOPER = 'TIM_DEVELOPER', 'Tim Developer'

    role = models.CharField(
        max_length=30,
        choices=RolePengguna.choices,
        default=RolePengguna.REQUIREMENTS_ENGINEER,
    )

    class Meta:
        verbose_name = 'Pengguna'
        verbose_name_plural = 'Pengguna'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
