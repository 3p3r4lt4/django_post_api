"""
Servicio de integración con Nubefact (SUNAT e-invoicing).

Implementa las 4 operaciones de la API JSON v2.9:
  1. generar_comprobante  → emitir Factura o Boleta
  2. consultar_comprobante → estado en SUNAT
  3. generar_anulacion    → comunicación de baja
  4. consultar_anulacion  → estado de la baja

Referencia: NUBEFACT_DOC_API_JSON_V1.docx
"""

import requests
from django.conf import settings

from core.utils import fecha_emision_nubefact, calcular_igv


# ─── Constantes ───────────────────────────────────────────────────────────────
TIPO_BOLETA = 2
TIPO_FACTURA = 1
TIPO_NOTA_CREDITO = 3
TIPO_NOTA_DEBITO = 4

# tipo_de_igv: 1 = Gravado - Operación Onerosa (el más común)
TIPO_IGV_GRAVADO = 1

# Unidades de medida SUNAT
UM_PRODUCTO = "NIU"
UM_SERVICIO = "ZZ"


# ─── Helper interno ───────────────────────────────────────────────────────────
def _headers() -> dict:
    token = settings.NUBEFACT["TOKEN"]
    return {
        "Authorization": token,
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> dict:
    """Realiza el POST a Nubefact y normaliza la respuesta."""
    url = settings.NUBEFACT["URL"]
    response = requests.post(url=url, headers=_headers(), json=payload, timeout=30)
    data = response.json()
    if response.status_code != 200:
        error_msg = data.get("errors", "Error desconocido en Nubefact")
        codigo = data.get("codigo", response.status_code)
        raise NubefactError(str(error_msg), codigo=codigo)
    return data


# ─── Excepción personalizada ──────────────────────────────────────────────────
class NubefactError(Exception):
    """Error devuelto por la API de Nubefact."""

    def __init__(self, message: str, codigo: int = 0):
        super().__init__(message)
        self.codigo = codigo

    def to_dict(self) -> dict:
        return {"error": str(self), "codigo_nubefact": self.codigo}


# ─── Operación 1: Generar comprobante ────────────────────────────────────────
def generar_boleta(
    numero: int,
    cliente_doc_tipo: str,
    cliente_doc_numero: str,
    cliente_nombre: str,
    cliente_email: str,
    items_venta: list,
    observaciones: str = "",
    medio_de_pago: str = "",
) -> dict:
    """
    Emite una Boleta de Venta electrónica vía Nubefact.

    items_venta: lista de dicts con:
      - descripcion (str)
      - cantidad (float)
      - precio_unitario (float, CON IGV)
      - codigo (str, opcional)
      - es_servicio (bool, opcional)
    """
    igv_pct = settings.NUBEFACT["IGV_PORCENTAJE"]
    serie = settings.NUBEFACT["SERIE_BOLETA"]

    items_nubefact, total_gravada, total_igv, total = _construir_items(items_venta, igv_pct)

    payload = {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": TIPO_BOLETA,
        "serie": serie,
        "numero": numero,
        "sunat_transaction": 1,
        "cliente_tipo_de_documento": cliente_doc_tipo,   # "1"=DNI, "6"=RUC, "-"=varios
        "cliente_numero_de_documento": cliente_doc_numero,
        "cliente_denominacion": cliente_nombre,
        "cliente_direccion": "",
        "cliente_email": cliente_email,
        "fecha_de_emision": fecha_emision_nubefact(),
        "moneda": 1,                            # 1 = Soles
        "porcentaje_de_igv": igv_pct,
        "total_gravada": total_gravada,
        "total_igv": total_igv,
        "total": total,
        "detraccion": False,
        "enviar_automaticamente_a_la_sunat": True,
        "enviar_automaticamente_al_cliente": bool(cliente_email),
        "observaciones": observaciones,
        "medio_de_pago": medio_de_pago,
        "formato_de_pdf": "A4",
        "items": items_nubefact,
    }
    return _post(payload)


def generar_factura(
    numero: int,
    cliente_ruc: str,
    cliente_razon_social: str,
    cliente_direccion: str,
    cliente_email: str,
    items_venta: list,
    observaciones: str = "",
    medio_de_pago: str = "",
) -> dict:
    """
    Emite una Factura electrónica vía Nubefact.
    cliente_ruc debe ser RUC válido de 11 dígitos.
    """
    igv_pct = settings.NUBEFACT["IGV_PORCENTAJE"]
    serie = settings.NUBEFACT["SERIE_FACTURA"]

    items_nubefact, total_gravada, total_igv, total = _construir_items(items_venta, igv_pct)

    payload = {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": TIPO_FACTURA,
        "serie": serie,
        "numero": numero,
        "sunat_transaction": 1,
        "cliente_tipo_de_documento": "6",       # 6 = RUC (obligatorio en facturas)
        "cliente_numero_de_documento": cliente_ruc,
        "cliente_denominacion": cliente_razon_social,
        "cliente_direccion": cliente_direccion,
        "cliente_email": cliente_email,
        "fecha_de_emision": fecha_emision_nubefact(),
        "moneda": 1,
        "porcentaje_de_igv": igv_pct,
        "total_gravada": total_gravada,
        "total_igv": total_igv,
        "total": total,
        "detraccion": False,
        "enviar_automaticamente_a_la_sunat": True,
        "enviar_automaticamente_al_cliente": bool(cliente_email),
        "observaciones": observaciones,
        "medio_de_pago": medio_de_pago,
        "formato_de_pdf": "A4",
        "items": items_nubefact,
    }
    return _post(payload)


# ─── Operación 2: Consultar comprobante ──────────────────────────────────────
def consultar_comprobante(
    tipo_comprobante: int,
    serie: str,
    numero: int,
) -> dict:
    """
    Consulta el estado de una Factura o Boleta en SUNAT.
    tipo_comprobante: 1=Factura, 2=Boleta, 3=NC, 4=ND
    """
    payload = {
        "operacion": "consultar_comprobante",
        "tipo_de_comprobante": tipo_comprobante,
        "serie": serie,
        "numero": numero,
    }
    return _post(payload)


# ─── Operación 3: Generar anulación (comunicación de baja) ───────────────────
def generar_anulacion(
    tipo_comprobante: int,
    serie: str,
    numero: int,
    motivo: str,
) -> dict:
    """
    Genera la comunicación de baja de un comprobante ante SUNAT.
    Solo aplica a comprobantes emitidos el mismo día.
    """
    payload = {
        "operacion": "generar_anulacion",
        "tipo_de_comprobante": tipo_comprobante,
        "serie": serie,
        "numero": numero,
        "motivo": motivo,
    }
    return _post(payload)


# ─── Operación 4: Consultar anulación ────────────────────────────────────────
def consultar_anulacion(
    tipo_comprobante: int,
    serie: str,
    numero: int,
) -> dict:
    """Consulta el estado de una comunicación de baja."""
    payload = {
        "operacion": "consultar_anulacion",
        "tipo_de_comprobante": tipo_comprobante,
        "serie": serie,
        "numero": numero,
    }
    return _post(payload)


# ─── Helper: construir items ──────────────────────────────────────────────────
def _construir_items(items_venta: list, igv_pct: float) -> tuple:
    """
    Convierte los items de la venta al formato que espera Nubefact.
    Retorna: (items_nubefact, total_gravada, total_igv, total)
    """
    items_nubefact = []
    total_gravada = 0.0
    total_igv_sum = 0.0
    total_sum = 0.0

    for item in items_venta:
        precio_con_igv = float(item["precio_unitario"])
        cantidad = float(item["cantidad"])
        descuento = float(item.get("descuento", 0))
        es_servicio = item.get("es_servicio", False)

        descomp = calcular_igv(precio_con_igv, igv_pct)
        valor_unitario = descomp["valor_unitario"]

        subtotal = round(valor_unitario * cantidad - descuento / (1 + igv_pct / 100), 2)
        igv_linea = round(subtotal * igv_pct / 100, 2)
        total_linea = round(subtotal + igv_linea, 2)

        total_gravada += subtotal
        total_igv_sum += igv_linea
        total_sum += total_linea

        items_nubefact.append({
            "unidad_de_medida": UM_SERVICIO if es_servicio else UM_PRODUCTO,
            "codigo": item.get("codigo", "P-001"),
            "descripcion": item["descripcion"],
            "cantidad": cantidad,
            "valor_unitario": round(valor_unitario, 10),
            "precio_unitario": round(precio_con_igv, 10),
            "descuento": descuento if descuento else "",
            "subtotal": subtotal,
            "tipo_de_igv": TIPO_IGV_GRAVADO,
            "igv": igv_linea,
            "total": total_linea,
            "anticipo_regularizacion": False,
        })

    return (
        items_nubefact,
        round(total_gravada, 2),
        round(total_igv_sum, 2),
        round(total_sum, 2),
    )
