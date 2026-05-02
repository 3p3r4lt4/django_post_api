"""
Modelo Cliente – equivale al Customers del barbershop pero adaptado a POS peruano.
Soporta personas naturales (DNI) y jurídicas (RUC).
"""
from django.db import models


class Cliente(models.Model):
    TIPO_DOC_CHOICES = [
        ("1", "DNI"),
        ("6", "RUC"),
        ("4", "Carnet de Extranjería"),
        ("7", "Pasaporte"),
        ("-", "Varios (sin documento)"),
    ]

    tipo_documento = models.CharField(max_length=2, choices=TIPO_DOC_CHOICES, default="1")
    numero_documento = models.CharField(max_length=15, unique=True)
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefono = models.CharField(max_length=20, blank=True, default="")
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.numero_documento})"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo_documento": self.tipo_documento,
            "tipo_documento_label": self.get_tipo_documento_display(),
            "numero_documento": self.numero_documento,
            "nombre": self.nombre,
            "direccion": self.direccion,
            "email": self.email,
            "telefono": self.telefono,
            "activo": self.activo,
        }
