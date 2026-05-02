"""
Capa de servicio para Ventas.

Separa la lógica de negocio de las vistas (patrón Service Layer).
Responsabilidades:
  - Crear venta con múltiples items
  - Descontar stock atómicamente
  - Aplicar descuento por volumen
  - Emitir comprobante electrónico vía Nubefact (Boleta o Factura)
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.contrib.auth.models import User

from apps.clientes.models import Cliente
from apps.productos.models import Producto

from .models import Venta, DetalleVenta, Comprobante
from .serializers import calcular_descuento_volumen

from core import nubefact as nubefact_service
from core.nubefact import NubefactError

logger = logging.getLogger(__name__)


# ─── Constantes Nubefact ─────────────────────────────────────────────────────
TIPO_BOLETA = 2
TIPO_FACTURA = 1


def _tipo_comprobante(cliente: Cliente | None) -> int:
    """
    Determina el tipo de comprobante según el documento del cliente:
    - RUC (tipo "6")  → Factura (tipo 1)
    - Cualquier otro → Boleta  (tipo 2)
    """
    if cliente and cliente.tipo_documento == "6":
        return TIPO_FACTURA
    return TIPO_BOLETA


# ─── Servicio principal ───────────────────────────────────────────────────────
@transaction.atomic
def crear_venta(
    usuario: User,
    items_data: list,
    cliente_id: int | None = None,
    observaciones: str = "",
    medio_de_pago: str = "",
    emitir_comprobante: bool = False,
) -> dict:
    """
    Crea una venta completa con todos sus detalles.

    items_data: lista de {'producto_id': int, 'cantidad': int}
    Retorna un dict con la venta creada y, si corresponde, el comprobante.
    """
    cliente = Cliente.objects.get(pk=cliente_id) if cliente_id else None

    # ── 1. Construir detalles y calcular totales ───────────────────────────
    detalles_a_crear = []
    subtotal_total = Decimal("0")
    descuento_global = Decimal("0")

    items_para_nubefact = []

    for item_data in items_data:
        producto = Producto.objects.select_for_update().get(pk=item_data["producto_id"])
        cantidad = item_data["cantidad"]

        # Precio histórico en el momento de la venta
        precio_unitario = producto.precio
        subtotal_linea = precio_unitario * cantidad

        # Descuento por volumen (misma lógica que flask-pos-api)
        descuento_pct = Decimal(str(calcular_descuento_volumen(cantidad)))
        descuento_monto = (subtotal_linea * descuento_pct).quantize(Decimal("0.01"))
        total_linea = subtotal_linea - descuento_monto

        # Descontar stock solo para productos físicos
        if not producto.es_servicio:
            producto.stock -= cantidad
            producto.save(update_fields=["stock", "updated_at"])

        detalle = DetalleVenta(
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            descuento=descuento_monto,
            subtotal=subtotal_linea,
            total=total_linea,
        )
        detalles_a_crear.append(detalle)

        subtotal_total += subtotal_linea
        descuento_global += descuento_monto

        items_para_nubefact.append({
            "descripcion": producto.nombre,
            "codigo": producto.codigo or f"P-{producto.id:04d}",
            "cantidad": float(cantidad),
            "precio_unitario": float(precio_unitario),
            "descuento": float(descuento_monto),
            "es_servicio": producto.es_servicio,
        })

    total_final = subtotal_total - descuento_global

    # ── 2. Guardar venta y detalles ────────────────────────────────────────
    venta = Venta.objects.create(
        usuario=usuario,
        cliente=cliente,
        subtotal=subtotal_total,
        descuento_total=descuento_global,
        total=total_final,
        observaciones=observaciones,
        medio_de_pago=medio_de_pago,
        estado="completada",
    )

    for detalle in detalles_a_crear:
        detalle.venta = venta

    DetalleVenta.objects.bulk_create(detalles_a_crear)

    # ── 3. Emitir comprobante electrónico (opcional) ───────────────────────
    comprobante_dict = None
    nubefact_error = None

    if emitir_comprobante:
        comprobante_dict, nubefact_error = _emitir_comprobante(
            venta=venta,
            cliente=cliente,
            items_para_nubefact=items_para_nubefact,
            observaciones=observaciones,
            medio_de_pago=medio_de_pago,
        )

    # ── 4. Construir respuesta ─────────────────────────────────────────────
    response = {
        "message": "Venta registrada exitosamente.",
        "venta": venta.to_dict(),
    }
    if descuento_global > 0:
        response["descuento_aplicado"] = float(descuento_global)
    if nubefact_error:
        response["nubefact_warning"] = nubefact_error

    return response


def _emitir_comprobante(
    venta: Venta,
    cliente: Cliente | None,
    items_para_nubefact: list,
    observaciones: str,
    medio_de_pago: str,
) -> tuple:
    """
    Emite el comprobante electrónico y guarda el Comprobante en BD.
    Retorna (comprobante_dict | None, error_str | None).
    """
    tipo = _tipo_comprobante(cliente)
    from django.conf import settings

    if tipo == TIPO_BOLETA:
        serie = settings.NUBEFACT["SERIE_BOLETA"]
    else:
        serie = settings.NUBEFACT["SERIE_FACTURA"]

    numero = Comprobante.siguiente_numero(tipo, serie)

    # Datos del cliente
    if cliente:
        doc_tipo = cliente.tipo_documento
        doc_numero = cliente.numero_documento
        nombre = cliente.nombre
        email = cliente.email
        direccion = cliente.direccion
    else:
        doc_tipo = "-"
        doc_numero = "00000000"
        nombre = "VARIOS"
        email = ""
        direccion = ""

    try:
        if tipo == TIPO_BOLETA:
            nf_response = nubefact_service.generar_boleta(
                numero=numero,
                cliente_doc_tipo=doc_tipo,
                cliente_doc_numero=doc_numero,
                cliente_nombre=nombre,
                cliente_email=email,
                items_venta=items_para_nubefact,
                observaciones=observaciones,
                medio_de_pago=medio_de_pago,
            )
        else:
            nf_response = nubefact_service.generar_factura(
                numero=numero,
                cliente_ruc=doc_numero,
                cliente_razon_social=nombre,
                cliente_direccion=direccion,
                cliente_email=email,
                items_venta=items_para_nubefact,
                observaciones=observaciones,
                medio_de_pago=medio_de_pago,
            )

        comprobante = Comprobante.objects.create(
            venta=venta,
            tipo_comprobante=tipo,
            serie=serie,
            numero=numero,
            enlace_nubefact=nf_response.get("enlace") or "",
            enlace_pdf=nf_response.get("enlace_del_pdf") or "",
            enlace_xml=nf_response.get("enlace_del_xml") or "",
            enlace_cdr=nf_response.get("enlace_del_cdr") or "",      # ← era None
            aceptada_por_sunat=nf_response.get("aceptada_por_sunat", False),
            sunat_descripcion=nf_response.get("sunat_description") or "",
            codigo_hash=nf_response.get("codigo_hash") or "",
            cadena_qr=nf_response.get("cadena_para_codigo_qr") or "",
            estado_sunat="aceptada" if nf_response.get("aceptada_por_sunat") else "pendiente",
        )
        return comprobante.to_dict(), None

    except NubefactError as e:
        logger.error("Error Nubefact al emitir comprobante venta #%d: %s", venta.id, e)
        # Guardamos el comprobante con estado error para reintento posterior
        Comprobante.objects.create(
            venta=venta,
            tipo_comprobante=tipo,
            serie=serie,
            numero=numero,
            estado_sunat="error",
            sunat_descripcion=str(e),
        )
        return None, f"Venta guardada. Error al emitir comprobante Nubefact: {e}"

    except Exception as e:
        logger.exception("Error inesperado emitiendo comprobante venta #%d", venta.id)
        return None, f"Error inesperado al emitir comprobante: {e}"
