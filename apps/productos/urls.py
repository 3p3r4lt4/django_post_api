from django.urls import path
from .views import ProductoListCreateView, ProductoDetailView

urlpatterns = [
    path("", ProductoListCreateView.as_view(), name="producto-list"),
    path("<int:pk>/", ProductoDetailView.as_view(), name="producto-detail"),
]
