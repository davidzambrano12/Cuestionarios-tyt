from django.contrib.auth.models import User
from django.db import models


class PermisoSistema(models.Model):
    codigo = models.CharField(max_length=60, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True, default="")
    modulo = models.CharField(max_length=50, default="General")

    class Meta:
        verbose_name = "Permiso del Sistema"
        verbose_name_plural = "Permisos del Sistema"
        ordering = ["modulo", "nombre"]

    def __str__(self):
        return f"{self.modulo}: {self.nombre} ({self.codigo})"


class Rol(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)
    es_sistema = models.BooleanField(default=False)
    permisos = models.ManyToManyField(PermisoSistema, related_name="roles", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def tiene_permiso(self, codigo_permiso: str) -> bool:
        if not self.activo:
            return False
        return self.permisos.filter(codigo=codigo_permiso).exists()


class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True, related_name="usuarios")
    codigo_institucional = models.CharField(max_length=50, blank=True, null=True)
    programa_academico = models.CharField(max_length=150, default="Ingeniería de Sistemas")
    semestre = models.CharField(max_length=50, default="6° Semestre")
    documento_identidad = models.CharField(max_length=50, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    modulo_asignado = models.CharField(max_length=150, blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.rol.nombre if self.rol else 'Sin Rol'}"

    def tiene_permiso(self, codigo_permiso: str) -> bool:
        if not self.user.is_active:
            return False
        if self.user.is_superuser:
            return True
        if self.rol and self.rol.activo:
            return self.rol.tiene_permiso(codigo_permiso)
        return False

    @property
    def es_admin(self) -> bool:
        return self.user.is_superuser or (self.rol and self.rol.codigo == "admin" and self.rol.activo)

    @property
    def es_docente(self) -> bool:
        return bool(self.rol and self.rol.codigo in ["docente", "docente_evaluador"] and self.rol.activo)

    @property
    def es_estudiante(self) -> bool:
        return bool(self.rol and self.rol.codigo == "estudiante" and self.rol.activo)


class ConfiguracionSistema(models.Model):
    """
    Datos institucionales editables desde Ajustes. Hay un único registro
    (pk=1); usar siempre ConfiguracionSistema.actual().
    """
    nombre_sistema = models.CharField("nombre del sistema", max_length=120, default="Simulador Saber TyT")
    institucion = models.CharField("institución", max_length=150, default="Institución Universitaria del Putumayo")
    sigla = models.CharField("sigla", max_length=30, default="Uniputumayo")
    correo_soporte = models.EmailField("correo de soporte", default="soporte.sistemas@uniputumayo.edu.co")
    telefono_soporte = models.CharField("teléfono de soporte", max_length=40, blank=True, default="")
    ubicacion = models.CharField("ubicación", max_length=150, blank=True, default="Sede Mocoa, Putumayo")
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "Configuración del sistema"
        verbose_name_plural = "Configuración del sistema"

    def __str__(self):
        return f"Configuración de {self.nombre_sistema}"

    def save(self, *args, **kwargs):
        self.pk = 1  # registro único
        super().save(*args, **kwargs)

    @classmethod
    def actual(cls):
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion
