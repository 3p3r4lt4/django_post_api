from django.contrib import admin
from .models import Venta, DetalleVenta, Comprobante


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    readonly_fields = ["subtotal", "total"]


class ComprobanteInline(admin.StackedInline):
    model = Comprobante
    extra = 0
    readonly_fields = [
        "serie", "numero", "enlace_nubefact", "enlace_pdf",
        "estado_sunat", "aceptada_por_sunat", "sunat_descripcion",
    ]


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "cliente", "total", "estado", "created_at"]
    list_filter = ["estado", "created_at"]
    search_fields = ["usuario__username", "cliente__nombre", "cliente__numero_documento"]
    readonly_fields = ["subtotal", "descuento_total", "total", "created_at"]
    inlines = [DetalleVentaInline, ComprobanteInline]


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ["__str__", "venta", "estado_sunat", "aceptada_por_sunat", "anulada", "created_at"]
    list_filter = ["tipo_comprobante", "estado_sunat", "aceptada_por_sunat", "anulada"]
    search_fields = ["serie", "venta__id"]
    readonly_fields = ["created_at", "updated_at"]
