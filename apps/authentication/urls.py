from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, LoginView, LogoutView, MeView, UserListView, UserDetailView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    # Gestión de usuarios (admin)
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:user_id>/", UserDetailView.as_view(), name="user-detail"),
]
