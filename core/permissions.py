"""
Permisos personalizados reutilizables en todo el proyecto.
Espejo del patrón _require_admin del flask-pos-api original.
"""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Solo usuarios con rol 'admin' pueden acceder."""
    message = "Acceso denegado: se requiere rol admin."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.profile.rol == "admin"
        )


class IsAdminOrReadOnly(BasePermission):
    """Admin puede todo; vendedor solo puede leer (GET, HEAD, OPTIONS)."""
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return request.user.profile.rol == "admin"
