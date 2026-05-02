from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "tipo_documento", "numero_documento", "email", "activo"]
    list_filter = ["tipo_documento", "activo"]
    search_fields = ["nombre", "numero_documento", "email"]
