from rest_framework import serializers
from .models import Producto


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = [
            "id", "nombre", "precio", "stock", "categoria",
            "activo", "es_servicio", "codigo", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo.")
        return value


class ProductoListSerializer(serializers.ModelSerializer):
    """Serializer liviano para listados."""
    class Meta:
        model = Producto
        fields = ["id", "nombre", "precio", "stock", "categoria", "es_servicio", "activo"]
