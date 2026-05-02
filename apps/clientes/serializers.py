from rest_framework import serializers
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    tipo_documento_label = serializers.CharField(
        source="get_tipo_documento_display", read_only=True
    )

    class Meta:
        model = Cliente
        fields = [
            "id", "tipo_documento", "tipo_documento_label",
            "numero_documento", "nombre", "direccion",
            "email", "telefono", "activo",
        ]
        read_only_fields = ["id", "tipo_documento_label"]
