from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import PermisoSistema, Rol, PerfilUsuario

class Command(BaseCommand):
    help = 'Inicializa permisos, roles por defecto y usuarios de prueba'

    def handle(self, *args, **kwargs):
        self.stdout.write("Inicializando permisos del sistema...")
        
        permisos_data = [
            # Módulo Usuarios
            ("usuarios.crear", "Crear usuarios", "Permite registrar nuevos usuarios en la plataforma", "Usuarios"),
            ("usuarios.editar", "Editar usuarios", "Permite modificar datos de usuarios", "Usuarios"),
            ("usuarios.activar_desactivar", "Suspender/Reactivar cuentas", "Permite activar o suspender el acceso de usuarios", "Usuarios"),
            # Módulo Roles
            ("roles.gestionar", "Administrar roles y permisos", "Permite crear, editar y configurar roles y permisos", "Roles"),
            # Módulo Banco de Preguntas
            ("preguntas.gestionar", "Gestionar banco de preguntas", "Permite consultar, crear, editar y desactivar reactivos", "Banco de Preguntas"),
            ("preguntas.importar", "Importar preguntas Excel", "Permite subir plantillas masivas de preguntas", "Banco de Preguntas"),
            # Módulo Cuestionarios
            ("cuestionarios.gestionar", "Configurar y habilitar cuestionarios", "Permite crear exámenes, asignar preguntas y abrir fechas", "Cuestionarios"),
            ("cuestionarios.ver_disponibles", "Ver cuestionarios disponibles", "Permite listar evaluaciones habilitadas", "Cuestionarios"),
            # Módulo Evaluaciones
            ("evaluaciones.responder", "Responder cuestionarios", "Permite iniciar y enviar intentos de examen", "Evaluaciones"),
            ("evaluaciones.ver_propias", "Consultar calificaciones propias", "Permite revisar notas e historial de intentos propios", "Evaluaciones"),
            ("resultados.consultar_todos", "Consultar resultados generales", "Permite auditar notas e informes de todos los estudiantes", "Reportes"),
        ]

        permisos_map = {}
        for codigo, nombre, descripcion, modulo in permisos_data:
            p, _ = PermisoSistema.objects.update_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "descripcion": descripcion, "modulo": modulo}
            )
            permisos_map[codigo] = p

        self.stdout.write("Inicializando roles del sistema...")
        
        # 1. Administrador
        rol_admin, _ = Rol.objects.update_or_create(
            codigo="admin",
            defaults={
                "nombre": "Administrador",
                "descripcion": "Acceso total al sistema, seguridad institucional, usuarios y cuestionarios",
                "activo": True,
                "es_sistema": True,
            }
        )
        rol_admin.permisos.set(list(permisos_map.values()))

        # 2. Docente Evaluador
        rol_docente, _ = Rol.objects.update_or_create(
            codigo="docente",
            defaults={
                "nombre": "Docente Evaluador",
                "descripcion": "Gestión de reactivos, configuración de cuestionarios y análisis de resultados",
                "activo": True,
                "es_sistema": False,
            }
        )
        docente_permisos = [
            permisos_map["preguntas.gestionar"],
            permisos_map["preguntas.importar"],
            permisos_map["cuestionarios.gestionar"],
            permisos_map["resultados.consultar_todos"],
        ]
        rol_docente.permisos.set(docente_permisos)

        # 3. Estudiante
        rol_estudiante, _ = Rol.objects.update_or_create(
            codigo="estudiante",
            defaults={
                "nombre": "Estudiante",
                "descripcion": "Acceso al simulador para presentar pruebas Saber TyT y consultar calificaciones",
                "activo": True,
                "es_sistema": True,
            }
        )
        estudiante_permisos = [
            permisos_map["cuestionarios.ver_disponibles"],
            permisos_map["evaluaciones.responder"],
            permisos_map["evaluaciones.ver_propias"],
        ]
        rol_estudiante.permisos.set(estudiante_permisos)

        # Asociar perfil al usuario admin existente (david)
        david = User.objects.filter(username="david").first()
        if david:
            david.is_staff = True
            david.is_superuser = True
            david.save()
            perfil, _ = PerfilUsuario.objects.get_or_create(user=david)
            perfil.rol = rol_admin
            perfil.codigo_institucional = "ADM-01"
            perfil.programa_academico = "Dirección de Sistemas IUP"
            perfil.save()
            self.stdout.write(f"Perfil de admin configurado para '{david.username}'.")

        # Crear o actualizar docente de prueba
        u_docente, created = User.objects.get_or_create(
            username="docente",
            defaults={
                "first_name": "Patricia",
                "last_name": "Jaramillo",
                "email": "p.jaramillo@uniputumayo.edu.co",
                "is_active": True,
            }
        )
        if created or not u_docente.check_password("123456"):
            u_docente.set_password("123456")
            u_docente.save()
        perfil_d, _ = PerfilUsuario.objects.get_or_create(user=u_docente)
        perfil_d.rol = rol_docente
        perfil_d.codigo_institucional = "DOC-104"
        perfil_d.programa_academico = "Ingeniería de Sistemas"
        perfil_d.modulo_asignado = "Razonamiento Cuantitativo"
        perfil_d.save()

        # Crear o actualizar estudiante de prueba
        u_estudiante, created = User.objects.get_or_create(
            username="estudiante",
            defaults={
                "first_name": "Carlos Andrés",
                "last_name": "Villota Narváez",
                "email": "c.villota@uniputumayo.edu.co",
                "is_active": True,
            }
        )
        if created or not u_estudiante.check_password("123456"):
            u_estudiante.set_password("123456")
            u_estudiante.save()
        perfil_e, _ = PerfilUsuario.objects.get_or_create(user=u_estudiante)
        perfil_e.rol = rol_estudiante
        perfil_e.codigo_institucional = "EST-20242-8819"
        perfil_e.programa_academico = "Ingeniería de Sistemas"
        perfil_e.semestre = "6° Semestre"
        perfil_e.documento_identidad = "CC 1.124.890.345"
        perfil_e.telefono = "+57 312 456 7890"
        perfil_e.save()

        self.stdout.write(self.style.SUCCESS("Sembrado inicial de roles, permisos y usuarios completado exitosamente."))
