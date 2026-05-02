from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Documentación OpenAPI ────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # ── Apps ─────────────────────────────────────────────────────────────────
    path("api/auth/", include("apps.authentication.urls")),
    path("api/productos/", include("apps.productos.urls")),
    path("api/clientes/", include("apps.clientes.urls")),
    path("api/ventas/", include("apps.ventas.urls")),
    path("api/reportes/", include("apps.reportes.urls")),
]
