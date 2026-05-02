from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer, LoginSerializer, UserProfileSerializer
from core.permissions import IsAdmin


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        summary="Registrar nuevo usuario",
        tags=["Autenticación"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"message": "Usuario registrado exitosamente.", "usuario": user.profile.to_dict()},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        summary="Iniciar sesión y obtener tokens JWT",
        tags=["Autenticación"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not user or not user.profile.activo:
            return Response(
                {"message": "Credenciales inválidas o usuario inactivo."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        # Añadir claims personalizados al token
        refresh["rol"] = user.profile.rol
        refresh["username"] = user.username

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "usuario": user.profile.to_dict(),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Cerrar sesión (blacklist del refresh token)", tags=["Autenticación"])
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Sesión cerrada correctamente."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"message": "Token inválido o ya expirado."}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Perfil del usuario autenticado", tags=["Autenticación"])
    def get(self, request):
        return Response(UserProfileSerializer(request.user.profile).data)

    @extend_schema(summary="Actualizar perfil propio", tags=["Autenticación"])
    def patch(self, request):
        user = request.user
        data = request.data
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "email" in data:
            email = data["email"].strip().lower()
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                return Response({"message": "El email ya está en uso."}, status=400)
            user.email = email
        user.save()
        return Response(UserProfileSerializer(user.profile).data)


class UserListView(APIView):
    """Solo admin puede listar y gestionar usuarios."""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(summary="Listar todos los usuarios (admin)", tags=["Usuarios"])
    def get(self, request):
        profiles = [u.profile for u in User.objects.select_related("profile").filter(profile__activo=True)]
        return Response(UserProfileSerializer(profiles, many=True).data)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_user(self, user_id: int):
        try:
            return User.objects.select_related("profile").get(pk=user_id)
        except User.DoesNotExist:
            return None

    @extend_schema(summary="Detalle de un usuario (admin)", tags=["Usuarios"])
    def get(self, request, user_id: int):
        user = self._get_user(user_id)
        if not user:
            return Response({"message": "Usuario no encontrado."}, status=404)
        return Response(UserProfileSerializer(user.profile).data)

    @extend_schema(summary="Cambiar rol o estado de usuario (admin)", tags=["Usuarios"])
    def patch(self, request, user_id: int):
        user = self._get_user(user_id)
        if not user:
            return Response({"message": "Usuario no encontrado."}, status=404)
        data = request.data
        if "rol" in data and data["rol"] in ["admin", "vendedor"]:
            user.profile.rol = data["rol"]
        if "activo" in data:
            user.profile.activo = bool(data["activo"])
        user.profile.save()
        return Response(UserProfileSerializer(user.profile).data)
