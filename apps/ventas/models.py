"""
Modelos de Ventas:
  - Venta        → cabecera de la transacción (equivale al modelo Venta del flask-pos)
  - DetalleVenta → líneas de la venta (múltiples productos por venta)
  - Comprobante  → registro del comprobante electrónico emitido por Nubefact

Mejoras sobre el flask-pos-api original:
  + Soporte multi-producto por venta (DetalleVenta)
  + Vinculación con Cliente
  + Comprobante electrónico (Boleta/Factura) como entidad propia
  + Estado del comprobante en SUNAT
  + Campo de anulación con motivo
"""
from django.db import models
from django.contrib.auth.models import User

from apps.clientes.models import Cliente
from apps.productos.models import Producto


class Venta(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("completada", "Completada"),
        ("anulada", "Anulada"),
    ]

    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="ventas"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="ventas",
        null=True,
        blank=True,
        help_text="Opcional para ventas rápidas sin cliente registrado.",
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="completada")
    observaciones = models.TextField(blank=True, default="")
    medio_de_pago = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Venta #{self.id} – S/ {self.total}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario": self.usuario.username,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "detalles": [d.to_dict() for d in self.detalles.all()],
            "subtotal": float(self.subtotal),
            "descuento_total": float(self.descuento_total),
            "total": float(self.total),
            "estado": self.estado,
            "observaciones": self.observaciones,
            "medio_de_pago": self.medio_de_pago,
            "comprobante": self.comprobante.to_dict() if hasattr(self, "comprobante") else None,
            "created_at": self.created_at.isoformat(),
        }


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles_venta")
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "producto_id": self.producto_id,
            "producto": self.producto.nombre,
            "es_servicio": self.producto.es_servicio,
            "codigo": self.producto.codigo,
            "cantidad": self.cantidad,
            "precio_unitario": float(self.precio_unitario),
            "descuento": float(self.descuento),
            "subtotal": float(self.subtotal),
            "total": float(self.total),
        }


class Comprobante(models.Model):
    TIPO_CHOICES = [
        (1, "Factura"),
        (2, "Boleta"),
        (3, "Nota de Crédito"),
        (4, "Nota de Débito"),
    ]
    ESTADO_SUNAT = [
        ("pendiente", "Pendiente"),
        ("aceptada", "Aceptada por SUNAT"),
        ("rechazada", "Rechazada por SUNAT"),
        ("anulada", "Anulada (Baja)"),
        ("error", "Error al emitir"),
    ]

    venta = models.OneToOneField(
        Venta, on_delete=models.CASCADE, related_name="comprobante"
    )
    tipo_comprobante = models.IntegerField(choices=TIPO_CHOICES)
    serie = models.CharField(max_length=4)
    numero = models.IntegerField()

    # Respuesta de Nubefact
    enlace_nubefact = models.URLField(blank=True, default="", null=True)
    enlace_pdf = models.URLField(blank=True, default="", null=True)
    enlace_xml = models.URLField(blank=True, default="", null=True)
    enlace_cdr = models.URLField(blank=True, default="", null=True)
    sunat_descripcion = models.TextField(blank=True, default="", null=True)

    # Estado SUNAT
    estado_sunat = models.CharField(max_length=15, choices=ESTADO_SUNAT, default="pendiente")
    aceptada_por_sunat = models.BooleanField(default=False)
    sunat_descripcion = models.TextField(blank=True, default="")
    codigo_hash = models.CharField(max_length=100, blank=True, default="")
    cadena_qr = models.TextField(blank=True, default="")

    # Anulación
    anulada = models.BooleanField(default=False)
    motivo_anulacion = models.CharField(max_length=200, blank=True, default="")
    ticket_anulacion = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comprobante Electrónico"
        verbose_name_plural = "Comprobantes Electrónicos"
        # Garantiza correlatividad única por tipo y serie
        unique_together = [("tipo_comprobante", "serie", "numero")]

    def __str__(self):
        tipo_label = dict(self.TIPO_CHOICES).get(self.tipo_comprobante, "?")
        return f"{tipo_label} {self.serie}-{self.numero:08d}"

    @classmethod
    def siguiente_numero(cls, tipo_comprobante: int, serie: str) -> int:
        """Obtiene el siguiente número correlativo para la serie dada."""
        ultimo = (
            cls.objects.filter(tipo_comprobante=tipo_comprobante, serie=serie)
            .order_by("-numero")
            .first()
        )
        return (ultimo.numero + 1) if ultimo else 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo_comprobante": self.tipo_comprobante,
            "tipo_label": dict(self.TIPO_CHOICES).get(self.tipo_comprobante),
            "serie": self.serie,
            "numero": self.numero,
            "enlace_nubefact": self.enlace_nubefact,
            "enlace_pdf": self.enlace_pdf,
            "enlace_xml": self.enlace_xml,
            "enlace_cdr": self.enlace_cdr,
            "estado_sunat": self.estado_sunat,
            "aceptada_por_sunat": self.aceptada_por_sunat,
            "sunat_descripcion": self.sunat_descripcion,
            "codigo_hash": self.codigo_hash,
            "anulada": self.anulada,
            "motivo_anulacion": self.motivo_anulacion,
        }
