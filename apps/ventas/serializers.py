"""
Serializers de Ventas.
VentaCreateSerializer maneja la lógica compleja de creación:
  - Valida stock por cada producto
  - Aplica descuento por volumen (idéntico al flask-pos original)
  - Soporta múltiples items por venta
  - Vincula cliente opcional
"""
from rest_framework import serializers

from apps.clientes.models import Cliente
from apps.clientes.serializers import ClienteSerializer
from apps.productos.models import Producto

from .models import Venta, DetalleVenta, Comprobante


# ─── Descuento por volumen (mismo que flask-pos-api) ─────────────────────────
DESCUENTO_POR_VOLUMEN = {
    10: 0.05,   # 5%  si cantidad >= 10
    20: 0.10,   # 10% si cantidad >= 20
    50: 0.15,   # 15% si cantidad >= 50
}


def calcular_descuento_volumen(cantidad: int) -> float:
    descuento = 0.0
    for umbral in sorted(DESCUENTO_POR_VOLUMEN.keys(), reverse=True):
        if cantidad >= umbral:
            descuento = DESCUENTO_POR_VOLUMEN[umbral]
            break
    return descuento


# ─── Sub-serializer: item de entrada ────────────────────────────────────────
class ItemVentaInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


# ─── Serializer principal de creación ───────────────────────────────────────
class VentaCreateSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField(required=False, allow_null=True)
    items = ItemVentaInputSerializer(many=True, min_length=1)
    observaciones = serializers.CharField(required=False, default="", allow_blank=True)
    medio_de_pago = serializers.CharField(required=False, default="", allow_blank=True)
    emitir_comprobante = serializers.BooleanField(required=False, default=False)

    def validate_items(self, items):
        errores = []
        for idx, item in enumerate(items):
            try:
                producto = Producto.objects.get(pk=item["producto_id"], activo=True)
            except Producto.DoesNotExist:
                errores.append(f"Item {idx + 1}: Producto ID {item['producto_id']} no encontrado o inactivo.")
                continue
            if not producto.es_servicio and producto.stock < item["cantidad"]:
                errores.append(
                    f"Item {idx + 1} ({producto.nombre}): stock insuficiente. "
                    f"Disponible: {producto.stock}, solicitado: {item['cantidad']}."
                )
        if errores:
            raise serializers.ValidationError(errores)
        return items

    def validate_cliente_id(self, value):
        if value is not None:
            if not Cliente.objects.filter(pk=value, activo=True).exists():
                raise serializers.ValidationError("Cliente no encontrado o inactivo.")
        return value


# ─── Serializers de lectura ───────────────────────────────────────────────────
class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    es_servicio = serializers.BooleanField(source="producto.es_servicio", read_only=True)

    class Meta:
        model = DetalleVenta
        fields = [
            "id", "producto_id", "producto_nombre", "es_servicio",
            "cantidad", "precio_unitario", "descuento", "subtotal", "total",
        ]


class ComprobanteSerializer(serializers.ModelSerializer):
    tipo_label = serializers.SerializerMethodField()

    class Meta:
        model = Comprobante
        fields = [
            "id", "tipo_comprobante", "tipo_label", "serie", "numero",
            "enlace_nubefact", "enlace_pdf", "enlace_xml", "enlace_cdr",
            "estado_sunat", "aceptada_por_sunat", "sunat_descripcion",
            "codigo_hash", "anulada", "motivo_anulacion", "created_at",
        ]

    def get_tipo_label(self, obj):
        return dict(Comprobante.TIPO_CHOICES).get(obj.tipo_comprobante, "")


class VentaSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source="usuario.username", read_only=True)
    cliente = ClienteSerializer(read_only=True)
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    comprobante = ComprobanteSerializer(read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id", "usuario", "cliente", "detalles",
            "subtotal", "descuento_total", "total",
            "estado", "observaciones", "medio_de_pago",
            "comprobante", "created_at",
        ]
