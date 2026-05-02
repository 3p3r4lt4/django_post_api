from django.urls import path
from .views import (
    VentaListCreateView,
    VentaDetailView,
    VentaAnularView,
    ComprobanteEmitirView,
    ComprobanteConsultarView,
    AnulacionConsultarView,
)

urlpatterns = [
    # Ventas
    path("", VentaListCreateView.as_view(), name="venta-list"),
    path("<int:venta_id>/", VentaDetailView.as_view(), name="venta-detail"),
    path("<int:venta_id>/anular/", VentaAnularView.as_view(), name="venta-anular"),

    # Comprobantes Nubefact (4 operaciones de la API)
    path("<int:venta_id>/comprobante/emitir/", ComprobanteEmitirView.as_view(), name="comprobante-emitir"),
    path("<int:venta_id>/comprobante/consultar/", ComprobanteConsultarView.as_view(), name="comprobante-consultar"),
    path("<int:venta_id>/comprobante/consultar-anulacion/", AnulacionConsultarView.as_view(), name="anulacion-consultar"),
]
