from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class AccountManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        if extra_fields["role"] != "admin":
            raise ValueError("A superuser must have the admin application role.")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    objects = AccountManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["admin", "staff"]), name="user_role_valid"
            )
        ]

    @property
    def display_name(self):
        return self.get_full_name() or self.username
