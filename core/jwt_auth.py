from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from core.models import PerfilUsuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Permite iniciar sesión con username O email institucional,
    e incluye en el payload JWT el rol y los permisos del usuario.
    """
    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field)
        password = attrs.get("password")

        # Intentar buscar por correo si parece un email
        user = None
        if "@" in username_or_email:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                attrs[self.username_field] = user_obj.username

        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise PermissionError("Esta cuenta ha sido desactivada o suspendida.")

        perfil = getattr(user, "perfil", None)
        rol_codigo = perfil.rol.codigo if (perfil and perfil.rol) else ("admin" if user.is_superuser else "estudiante")
        rol_nombre = perfil.rol.nombre if (perfil and perfil.rol) else ("Administrador" if user.is_superuser else "Estudiante")
        
        # Recopilar permisos del rol
        permisos_codigos = []
        if user.is_superuser:
            permisos_codigos = ["*"]
        elif perfil and perfil.rol and perfil.rol.activo:
            permisos_codigos = list(perfil.rol.permisos.values_list("codigo", flat=True))

        # Añadir al payload del access token
        refresh = self.get_token(user)
        refresh["username"] = user.username
        refresh["email"] = user.email
        refresh["full_name"] = user.get_full_name() or user.username
        refresh["rol_codigo"] = rol_codigo
        refresh["rol_nombre"] = rol_nombre
        refresh["permisos"] = permisos_codigos

        # Añadir al cuerpo de la respuesta HTTP
        data["access"] = str(refresh.access_token)
        data["refresh"] = str(refresh)
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.get_full_name() or user.username,
            "rol": rol_codigo,
            "rol_nombre": rol_nombre,
            "codigo_institucional": perfil.codigo_institucional if perfil else "",
            "permisos": permisos_codigos,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """
    Cierre de sesión que revoca el refresh token (blacklist)
    y limpia la sesión de Django.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        
        response = Response({"detail": "Sesión cerrada exitosamente."}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


class UserProfileMeView(APIView):
    """
    Endpoint para que la interfaz o cliente JWT verifique el token y sus permisos.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        perfil = getattr(user, "perfil", None)
        rol_codigo = perfil.rol.codigo if (perfil and perfil.rol) else ("admin" if user.is_superuser else "estudiante")
        rol_nombre = perfil.rol.nombre if (perfil and perfil.rol) else ("Administrador" if user.is_superuser else "Estudiante")
        
        permisos_codigos = []
        if user.is_superuser:
            permisos_codigos = ["*"]
        elif perfil and perfil.rol and perfil.rol.activo:
            permisos_codigos = list(perfil.rol.permisos.values_list("codigo", flat=True))

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "rol": rol_codigo,
            "rol_nombre": rol_nombre,
            "codigo_institucional": perfil.codigo_institucional if perfil else "",
            "programa_academico": perfil.programa_academico if perfil else "",
            "semestre": perfil.semestre if perfil else "",
            "permisos": permisos_codigos,
        })
