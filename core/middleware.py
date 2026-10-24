from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthCookieMiddleware:
    """
    Middleware que permite autenticar al usuario usando el token JWT guardado
    en la cookie 'access_token' o en la cabecera 'Authorization: Bearer <token>',
    garantizando que las vistas normales de Django y las llamadas fetch compartan
    la misma sesión JWT.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        if not request.user.is_authenticated:
            # 1. Intentar cabecera Authorization
            header = request.headers.get("Authorization")
            raw_token = None
            if header and header.startswith("Bearer "):
                raw_token = header.split(" ")[1]
            
            # 2. Si no hay cabecera, intentar cookie 'access_token'
            if not raw_token:
                raw_token = request.COOKIES.get("access_token")

            if raw_token:
                try:
                    validated_token = self.jwt_auth.get_validated_token(raw_token)
                    user = self.jwt_auth.get_user(validated_token)
                    if user and user.is_active:
                        request.user = user
                except Exception:
                    # Token inválido o expirado; continúa como no autenticado
                    pass

        return self.get_response(request)
