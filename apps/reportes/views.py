"""
Módulo de Reportes.

Endpoints:
  GET /api/reportes/ventas/          → resumen por rango de fechas
  GET /api/reportes/productos/top/   → top productos más vendidos
  GET /api/reportes/diario/          → resumen del día actual
  GET /api/reportes/comprobantes/    → estado de comprobantes emitidos
"""
from datetime import date, datetime, timedelta

from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import TruncDate
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.ventas.models import Venta, DetalleVenta, Comprobante
from core.permissions import IsAdmin


def _parse_date(date_str: str | None, fallback: date) -> date:
    if not date_str:
        return fallback
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return fallback


class ResumenVentasView(APIView):
    """
    GET /api/reportes/ventas/?fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD

    Retorna:
      - Total facturado en el período
      - Número de ventas completadas / anuladas
      - Desglose diario
    Solo admin.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Resumen de ventas por rango de fechas (admin)",
        tags=["Reportes"],
    )
    def get(self, request):
        today = date.today()
        fecha_inicio = _parse_date(request.query_params.get("fecha_inicio"), today - timedelta(days=30))
        fecha_fin = _parse_date(request.query_params.get("fecha_fin"), today)

        qs = Venta.objects.filter(
            created_at__date__gte=fecha_inicio,
            created_at__date__lte=fecha_fin,
        )

        completadas = qs.filter(estado="completada")
        anuladas = qs.filter(estado="anulada")

        # Totales generales
        total_facturado = completadas.aggregate(t=Sum("total"))["t"] or 0
        total_descuentos = completadas.aggregate(d=Sum("descuento_total"))["d"] or 0

        # Desglose diario
        diario = (
            completadas.annotate(dia=TruncDate("created_at"))
            .values("dia")
            .annotate(
                num_ventas=Count("id"),
                total_dia=Sum("total"),
            )
            .order_by("dia")
        )

        return Response({
            "periodo": {
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat(),
            },
            "resumen": {
                "ventas_completadas": completadas.count(),
                "ventas_anuladas": anuladas.count(),
                "total_facturado": float(total_facturado),
                "total_descuentos": float(total_descuentos),
                "total_neto": float(total_facturado - total_descuentos),
            },
            "desglose_diario": [
                {
                    "fecha": row["dia"].isoformat(),
                    "num_ventas": row["num_ventas"],
                    "total": float(row["total_dia"] or 0),
                }
                for row in diario
            ],
        })


class TopProductosView(APIView):
    """
    GET /api/reportes/productos/top/?limite=10&fecha_inicio=...&fecha_fin=...

    Retorna los productos más vendidos por cantidad y por monto.
    Solo admin.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Top productos más vendidos (admin)",
        tags=["Reportes"],
    )
    def get(self, request):
        today = date.today()
        fecha_inicio = _parse_date(request.query_params.get("fecha_inicio"), today - timedelta(days=30))
        fecha_fin = _parse_date(request.query_params.get("fecha_fin"), today)
        limite = int(request.query_params.get("limite", 10))

        top = (
            DetalleVenta.objects.filter(
                venta__estado="completada",
                venta__created_at__date__gte=fecha_inicio,
                venta__created_at__date__lte=fecha_fin,
            )
            .values("producto__id", "producto__nombre", "producto__categoria")
            .annotate(
                unidades_vendidas=Sum("cantidad"),
                ingresos_total=Sum("total"),
                num_ventas=Count("venta", distinct=True),
            )
            .order_by("-unidades_vendidas")[:limite]
        )

        return Response({
            "periodo": {
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat(),
            },
            "top_productos": [
                {
                    "producto_id": row["producto__id"],
                    "nombre": row["producto__nombre"],
                    "categoria": row["producto__categoria"],
                    "unidades_vendidas": row["unidades_vendidas"],
                    "ingresos_total": float(row["ingresos_total"] or 0),
                    "num_ventas": row["num_ventas"],
                }
                for row in top
            ],
        })


class ResumenDiarioView(APIView):
    """
    GET /api/reportes/diario/?fecha=YYYY-MM-DD (default: hoy)

    Resumen rápido del día: ventas, ingresos, comprobantes emitidos.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Resumen del día (admin)",
        tags=["Reportes"],
    )
    def get(self, request):
        fecha = _parse_date(request.query_params.get("fecha"), date.today())

        ventas_dia = Venta.objects.filter(created_at__date=fecha)
        completadas = ventas_dia.filter(estado="completada")

        total = completadas.aggregate(t=Sum("total"))["t"] or 0
        descuentos = completadas.aggregate(d=Sum("descuento_total"))["d"] or 0

        comprobantes = Comprobante.objects.filter(created_at__date=fecha)
        boletas = comprobantes.filter(tipo_comprobante=2).count()
        facturas = comprobantes.filter(tipo_comprobante=1).count()
        aceptadas = comprobantes.filter(aceptada_por_sunat=True).count()

        return Response({
            "fecha": fecha.isoformat(),
            "ventas": {
                "completadas": completadas.count(),
                "anuladas": ventas_dia.filter(estado="anulada").count(),
                "total_facturado": float(total),
                "total_descuentos": float(descuentos),
            },
            "comprobantes": {
                "boletas_emitidas": boletas,
                "facturas_emitidas": facturas,
                "total_emitidos": boletas + facturas,
                "aceptadas_sunat": aceptadas,
            },
        })


class EstadoComprobantesView(APIView):
    """
    GET /api/reportes/comprobantes/?estado_sunat=pendiente|aceptada|error

    Lista comprobantes filtrados por estado SUNAT.
    Útil para identificar comprobantes pendientes de reenvío.
    Solo admin.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Estado de comprobantes electrónicos (admin)",
        tags=["Reportes"],
    )
    def get(self, request):
        qs = Comprobante.objects.select_related("venta__cliente").order_by("-created_at")

        estado = request.query_params.get("estado_sunat")
        if estado:
            qs = qs.filter(estado_sunat=estado)

        tipo = request.query_params.get("tipo_comprobante")
        if tipo:
            qs = qs.filter(tipo_comprobante=tipo)

        return Response({
            "total": qs.count(),
            "comprobantes": [
                {
                    **c.to_dict(),
                    "venta_id": c.venta_id,
                    "cliente": c.venta.cliente.nombre if c.venta.cliente else "VARIOS",
                    "total_venta": float(c.venta.total),
                }
                for c in qs[:100]  # Máximo 100 por llamada
            ],
        })
