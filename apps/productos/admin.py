from django.contrib import admin
from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "precio", "stock", "categoria", "es_servicio", "activo"]
    list_filter = ["categoria", "es_servicio", "activo"]
    search_fields = ["nombre", "codigo"]
    list_editable = ["precio", "stock", "activo"]
