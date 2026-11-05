"""
Reglas de identidad y acceso compartidas por todos los módulos.

Centraliza preguntas que antes se repetían en cada vista: ¿qué código
identifica al participante?, ¿es personal docente?, ¿puede auditar notas?
"""
def perfil_de(user):
    return getattr(user, "perfil", None)


def codigo_participante(user) -> str:
    """Código institucional con el que se registran los intentos del usuario."""
    perfil = perfil_de(user)
    return getattr(perfil, "codigo_institucional", None) or user.username


def es_personal_docente(user) -> bool:
    """Docentes y administradores: previsualizan exámenes en lugar de presentarlos."""
    perfil = perfil_de(user)
    return bool(
        user.is_staff
        or user.is_superuser
        or getattr(perfil, "es_docente", False)
        or getattr(perfil, "es_admin", False)
    )


def tiene_permiso(user, codigo_permiso: str) -> bool:
    if user.is_superuser:
        return True
    perfil = perfil_de(user)
    return bool(perfil and perfil.tiene_permiso(codigo_permiso))


def puede_auditar_resultados(user) -> bool:
    """Docentes y administradores auditan cualquier intento (CU-05)."""
    return (
        user.is_superuser
        or tiene_permiso(user, "resultados.consultar_todos")
        or tiene_permiso(user, "cuestionarios.gestionar")
    )


def es_dueno_del_intento(user, intento) -> bool:
    return intento.participante_codigo == codigo_participante(user)
