"""
Modelo de perfil que extiende el User de Django.
Patrón: perfil con rol (admin / vendedor), manteniendo el auth estándar de Django.
"""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROL_CHOICES = [
        ("admin", "Administrador"),
        ("vendedor", "Vendedor"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="vendedor")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        return f"{self.user.username} ({self.rol})"

    def to_dict(self) -> dict:
        return {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "rol": self.rol,
            "activo": self.activo,
        }


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crea perfil automáticamente al crear un User."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
