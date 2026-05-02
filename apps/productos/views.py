from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Producto
from .serializers import ProductoSerializer, ProductoListSerializer
from core.permissions import IsAdminOrReadOnly


class ProductoListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "categoria", "codigo"]
    ordering_fields = ["nombre", "precio", "stock", "created_at"]
    ordering = ["nombre"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProductoListSerializer
        return ProductoSerializer

    def get_queryset(self):
        qs = Producto.objects.all()
        # Admin ve todos; vendedor solo activos
        if not (hasattr(self.request.user, "profile") and self.request.user.profile.rol == "admin"):
            qs = qs.filter(activo=True)
        categoria = self.request.query_params.get("categoria")
        if categoria:
            qs = qs.filter(categoria__iexact=categoria)
        es_servicio = self.request.query_params.get("es_servicio")
        if es_servicio is not None:
            qs = qs.filter(es_servicio=es_servicio.lower() == "true")
        return qs

    @extend_schema(summary="Listar productos/servicios", tags=["Productos"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Crear producto/servicio (admin)", tags=["Productos"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ProductoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
        if hasattr(self.request.user, "profile") and self.request.user.profile.rol == "admin":
            return Producto.objects.all()
        return Producto.objects.filter(activo=True)

    @extend_schema(summary="Detalle de producto", tags=["Productos"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Actualizar producto (admin)", tags=["Productos"])
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Actualizar producto parcial (admin)", tags=["Productos"])
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Desactivar producto soft-delete (admin)", tags=["Productos"])
    def delete(self, request, *args, **kwargs):
        producto = self.get_object()
        producto.activo = False
        producto.save()
        return Response(
            {"message": f"Producto '{producto.nombre}' desactivado."},
            status=status.HTTP_200_OK,
        )
