from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=80)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)
    first_name = serializers.CharField(max_length=50, required=False, default="")
    last_name = serializers.CharField(max_length=50, required=False, default="")
    rol = serializers.ChoiceField(choices=["admin", "vendedor"], default="vendedor")

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("El username ya existe.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("El email ya está registrado.")
        return value.lower()

    def create(self, validated_data):
        rol = validated_data.pop("rol", "vendedor")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        # El perfil se crea vía signal; solo actualizamos el rol
        user.profile.rol = rol
        user.profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "first_name", "last_name", "rol", "activo"]
