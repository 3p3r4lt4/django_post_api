from django.urls import path
from .views import (
    ResumenVentasView,
    TopProductosView,
    ResumenDiarioView,
    EstadoComprobantesView,
)

urlpatterns = [
    path("ventas/", ResumenVentasView.as_view(), name="reporte-ventas"),
    path("productos/top/", TopProductosView.as_view(), name="reporte-top-productos"),
    path("diario/", ResumenDiarioView.as_view(), name="reporte-diario"),
    path("comprobantes/", EstadoComprobantesView.as_view(), name="reporte-comprobantes"),
]
