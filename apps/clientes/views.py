from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Cliente
from .serializers import ClienteSerializer
from core.permissions import IsAdmin


class ClienteListCreateView(generics.ListCreateAPIView):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "numero_documento", "email"]
    ordering_fields = ["nombre", "created_at"]
    ordering = ["nombre"]

    def get_queryset(self):
        qs = Cliente.objects.filter(activo=True)
        tipo = self.request.query_params.get("tipo_documento")
        if tipo:
            qs = qs.filter(tipo_documento=tipo)
        return qs

    @extend_schema(summary="Listar clientes", tags=["Clientes"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Crear cliente", tags=["Clientes"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ClienteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()

    @extend_schema(summary="Detalle de cliente", tags=["Clientes"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Actualizar cliente", tags=["Clientes"])
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Actualizar cliente (parcial)", tags=["Clientes"])
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Desactivar cliente (soft-delete)", tags=["Clientes"])
    def delete(self, request, *args, **kwargs):
        cliente = self.get_object()
        cliente.activo = False
        cliente.save()
        return Response(
            {"message": f"Cliente '{cliente.nombre}' desactivado."},
            status=status.HTTP_200_OK,
        )
