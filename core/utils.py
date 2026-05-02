"""Utilidades compartidas por todos los módulos."""
from datetime import datetime
from zoneinfo import ZoneInfo

LIMA_TZ = ZoneInfo("America/Lima")


def now_lima() -> datetime:
    """Retorna la hora actual en Lima (UTC-5) sin tzinfo para PostgreSQL."""
    return datetime.now(LIMA_TZ).replace(tzinfo=None)


def fecha_emision_nubefact() -> str:
    """Fecha de hoy en formato DD-MM-YYYY requerido por Nubefact."""
    return datetime.now(LIMA_TZ).strftime("%d-%m-%Y")


def calcular_igv(precio_con_igv: float, porcentaje: float = 18.0) -> dict:
    """
    Descompone un precio IGV-incluido en sus partes.
    Retorna: valor_unitario (sin IGV), igv, precio_unitario (con IGV).
    """
    factor = 1 + porcentaje / 100
    valor_unitario = round(precio_con_igv / factor, 10)
    igv = round(precio_con_igv - valor_unitario, 2)
    return {
        "valor_unitario": valor_unitario,
        "igv": igv,
        "precio_unitario": round(precio_con_igv, 2),
    }


def calcular_totales_venta(items: list, porcentaje_igv: float = 18.0) -> dict:
    """
    Calcula totales de una venta (total_gravada, total_igv, total).
    items: lista de dicts con keys: precio_unitario, cantidad, descuento (opcional).
    """
    total_gravada = 0.0
    total_igv_sum = 0.0
    total = 0.0

    for item in items:
        precio = float(item["precio_unitario"])
        cantidad = float(item["cantidad"])
        descuento = float(item.get("descuento", 0))
        line_total = round(precio * cantidad - descuento, 2)
        descomp = calcular_igv(line_total, porcentaje_igv)
        total_gravada += descomp["valor_unitario"] * cantidad
        total_igv_sum += descomp["igv"]
        total += line_total

    return {
        "total_gravada": round(total_gravada, 2),
        "total_igv": round(total_igv_sum, 2),
        "total": round(total, 2),
    }
