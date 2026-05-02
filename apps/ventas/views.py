"""
Views de Ventas:
  - VentaListCreateView   → GET (listado) / POST (nueva venta)
  - VentaDetailView       → GET (detalle)
  - VentaAnularView       → POST (anular venta + comunicación de baja en SUNAT)
  - ComprobanteEmitirView → POST (emitir comprobante a una venta existente)
  - ComprobanteConsultarView → GET (consultar estado en SUNAT)
  - AnulacionConsultarView   → GET (consultar estado de la baja en SUNAT)
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import Venta, Comprobante
from .serializers import VentaCreateSerializer, VentaSerializer
from .services import crear_venta

from core import nubefact as nubefact_service
from core.nubefact import NubefactError
from core.permissions import IsAdmin

logger = logging.getLogger(__name__)


# ─── Ventas ────────────────────────────────────────────────────────────────────
class VentaListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Listar ventas",
        description=(
            "Admins ven todas las ventas. "
            "Vendedores solo ven las propias. "
            "Filtra por `?estado=completada|anulada` o `?cliente_id=<id>`."
        ),
        tags=["Ventas"],
    )
    def get(self, request):
        es_admin = hasattr(request.user, "profile") and request.user.profile.rol == "admin"

        if es_admin:
            qs = Venta.objects.select_related("usuario", "cliente").prefetch_related(
                "detalles__producto", "comprobante"
            )
        else:
            qs = Venta.objects.filter(usuario=request.user).select_related(
                "cliente"
            ).prefetch_related("detalles__producto", "comprobante")

        # Filtros opcionales
        estado = request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        cliente_id = request.query_params.get("cliente_id")
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        serializer = VentaSerializer(qs.order_by("-created_at"), many=True)
        return Response({"ventas": serializer.data, "total": qs.count()}, status=200)

    @extend_schema(
        request=VentaCreateSerializer,
        summary="Crear nueva venta",
        description=(
            "Registra una venta con uno o más productos. "
            "Aplica descuento por volumen automáticamente. "
            "Si `emitir_comprobante=true`, emite Boleta o Factura en Nubefact."
        ),
        tags=["Ventas"],
    )
    def post(self, request):
        serializer = VentaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = crear_venta(
            usuario=request.user,
            items_data=data["items"],
            cliente_id=data.get("cliente_id"),
            observaciones=data.get("observaciones", ""),
            medio_de_pago=data.get("medio_de_pago", ""),
            emitir_comprobante=data.get("emitir_comprobante", False),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class VentaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_venta(self, venta_id: int, request):
        try:
            venta = Venta.objects.select_related("usuario", "cliente").prefetch_related(
                "detalles__producto", "comprobante"
            ).get(pk=venta_id)
        except Venta.DoesNotExist:
            return None, Response({"message": "Venta no encontrada."}, status=404)

        es_admin = hasattr(request.user, "profile") and request.user.profile.rol == "admin"
        if not es_admin and venta.usuario != request.user:
            return None, Response({"message": "Acceso denegado."}, status=403)

        return venta, None

    @extend_schema(summary="Detalle de venta", tags=["Ventas"])
    def get(self, request, venta_id: int):
        venta, err = self._get_venta(venta_id, request)
        if err:
            return err
        return Response(VentaSerializer(venta).data)


# ─── Anulación de venta ────────────────────────────────────────────────────────
class VentaAnularView(APIView):
    """
    POST /api/ventas/<id>/anular/
    Anula la venta localmente y, si tiene comprobante, genera la
    comunicación de baja (Operación 3) en Nubefact/SUNAT.
    Solo admin puede anular.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Anular venta y emitir comunicación de baja (admin)",
        tags=["Ventas"],
    )
    @transaction.atomic
    def post(self, request, venta_id: int):
        try:
            venta = Venta.objects.select_related("comprobante").get(pk=venta_id)
        except Venta.DoesNotExist:
            return Response({"message": "Venta no encontrada."}, status=404)

        if venta.estado == "anulada":
            return Response({"message": "La venta ya está anulada."}, status=400)

        motivo = request.data.get("motivo", "ANULADO POR ADMINISTRADOR")
        if not motivo.strip():
            return Response({"message": "El campo 'motivo' es requerido."}, status=400)

        # Revertir stock de los productos físicos
        for detalle in venta.detalles.select_related("producto").all():
            if not detalle.producto.es_servicio:
                detalle.producto.stock += detalle.cantidad
                detalle.producto.save(update_fields=["stock", "updated_at"])

        venta.estado = "anulada"
        venta.save(update_fields=["estado", "updated_at"])

        # Comunicación de baja en SUNAT si hay comprobante aceptado
        nubefact_response = None
        nubefact_error = None

        if hasattr(venta, "comprobante") and not venta.comprobante.anulada:
            comp = venta.comprobante
            try:
                nubefact_response = nubefact_service.generar_anulacion(
                    tipo_comprobante=comp.tipo_comprobante,
                    serie=comp.serie,
                    numero=comp.numero,
                    motivo=motivo,
                )
                comp.anulada = True
                comp.motivo_anulacion = motivo
                comp.ticket_anulacion = nubefact_response.get("sunat_ticket_numero", "")
                comp.estado_sunat = "anulada"
                comp.save(update_fields=[
                    "anulada", "motivo_anulacion", "ticket_anulacion",
                    "estado_sunat", "updated_at"
                ])
            except NubefactError as e:
                logger.error("Error Nubefact anulando comprobante: %s", e)
                nubefact_error = str(e)

        response = {
            "message": "Venta anulada correctamente.",
            "venta_id": venta.id,
            "motivo": motivo,
        }
        if nubefact_response:
            response["comunicacion_baja"] = nubefact_response
        if nubefact_error:
            response["nubefact_warning"] = f"Venta anulada localmente. Error SUNAT: {nubefact_error}"

        return Response(response, status=200)


# ─── Comprobantes electrónicos ────────────────────────────────────────────────
class ComprobanteEmitirView(APIView):
    """
    POST /api/ventas/<id>/comprobante/emitir/
    Emite el comprobante electrónico de una venta que aún no lo tiene.
    Útil para reintentar si hubo error en la emisión original.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Emitir comprobante electrónico de una venta",
        tags=["Comprobantes"],
    )
    def post(self, request, venta_id: int):
        try:
            venta = Venta.objects.prefetch_related("detalles__producto").get(pk=venta_id)
        except Venta.DoesNotExist:
            return Response({"message": "Venta no encontrada."}, status=404)

        # Verificar acceso
        es_admin = hasattr(request.user, "profile") and request.user.profile.rol == "admin"
        if not es_admin and venta.usuario != request.user:
            return Response({"message": "Acceso denegado."}, status=403)

        if venta.estado == "anulada":
            return Response({"message": "No se puede emitir comprobante de una venta anulada."}, status=400)

        # Si ya tiene comprobante emitido exitosamente, no duplicar
        if hasattr(venta, "comprobante") and venta.comprobante.estado_sunat not in ["error"]:
            return Response(
                {"message": "Esta venta ya tiene un comprobante emitido.", "comprobante": venta.comprobante.to_dict()},
                status=400,
            )

        # Reconstruir items para Nubefact
        items_para_nubefact = [
            {
                "descripcion": d.producto.nombre,
                "codigo": d.producto.codigo or f"P-{d.producto.id:04d}",
                "cantidad": float(d.cantidad),
                "precio_unitario": float(d.precio_unitario),
                "descuento": float(d.descuento),
                "es_servicio": d.producto.es_servicio,
            }
            for d in venta.detalles.all()
        ]

        from .services import _emitir_comprobante
        comprobante_dict, error = _emitir_comprobante(
            venta=venta,
            cliente=venta.cliente,
            items_para_nubefact=items_para_nubefact,
            observaciones=venta.observaciones,
            medio_de_pago=venta.medio_de_pago,
        )

        if error:
            return Response({"message": error}, status=502)

        return Response(
            {"message": "Comprobante emitido exitosamente.", "comprobante": comprobante_dict},
            status=201,
        )


class ComprobanteConsultarView(APIView):
    """
    GET /api/ventas/<id>/comprobante/consultar/
    Consulta el estado del comprobante directamente en SUNAT vía Nubefact.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Consultar estado del comprobante en SUNAT", tags=["Comprobantes"])
    def get(self, request, venta_id: int):
        try:
            venta = Venta.objects.get(pk=venta_id)
            comp = venta.comprobante
        except (Venta.DoesNotExist, Comprobante.DoesNotExist):
            return Response({"message": "Venta o comprobante no encontrado."}, status=404)

        try:
            nf_response = nubefact_service.consultar_comprobante(
                tipo_comprobante=comp.tipo_comprobante,
                serie=comp.serie,
                numero=comp.numero,
            )
            # Actualizar estado local
            comp.aceptada_por_sunat = nf_response.get("aceptada_por_sunat", False)
            comp.sunat_descripcion = nf_response.get("sunat_description", "")
            if nf_response.get("anulado"):
                comp.anulada = True
                comp.estado_sunat = "anulada"
            elif nf_response.get("aceptada_por_sunat"):
                comp.estado_sunat = "aceptada"
            comp.save(update_fields=["aceptada_por_sunat", "sunat_descripcion", "anulada", "estado_sunat", "updated_at"])

            return Response({"comprobante": comp.to_dict(), "nubefact_response": nf_response})
        except NubefactError as e:
            return Response({"message": str(e), "codigo_nubefact": e.codigo}, status=502)


class AnulacionConsultarView(APIView):
    """
    GET /api/ventas/<id>/comprobante/consultar-anulacion/
    Consulta el estado de la comunicación de baja en SUNAT.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Consultar estado de comunicación de baja en SUNAT", tags=["Comprobantes"])
    def get(self, request, venta_id: int):
        try:
            venta = Venta.objects.get(pk=venta_id)
            comp = venta.comprobante
        except (Venta.DoesNotExist, Comprobante.DoesNotExist):
            return Response({"message": "Venta o comprobante no encontrado."}, status=404)

        if not comp.anulada:
            return Response({"message": "Este comprobante no ha sido anulado."}, status=400)

        try:
            nf_response = nubefact_service.consultar_anulacion(
                tipo_comprobante=comp.tipo_comprobante,
                serie=comp.serie,
                numero=comp.numero,
            )
            return Response({"comprobante": comp.to_dict(), "nubefact_response": nf_response})
        except NubefactError as e:
            return Response({"message": str(e), "codigo_nubefact": e.codigo}, status=502)
