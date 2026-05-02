"""
Modelo Producto – migrado desde flask-pos-api/app/models/productos.py.
Mantiene la misma lógica de negocio: soft-delete, stock, categoría.
"""
from django.db import models


class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    categoria = models.CharField(max_length=50, blank=True, default="Sin categoría")
    activo = models.BooleanField(default=True)
    # Es servicio: no descuenta stock y usa UM "ZZ" en Nubefact
    es_servicio = models.BooleanField(default=False)
    codigo = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} (S/ {self.precio})"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "precio": float(self.precio),
            "stock": self.stock,
            "categoria": self.categoria,
            "activo": self.activo,
            "es_servicio": self.es_servicio,
            "codigo": self.codigo,
        }
