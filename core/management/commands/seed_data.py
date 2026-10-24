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

        # Vincular perfil de Administrador a todos los superusuarios existentes (ej. Johan)
        for su in User.objects.filter(is_superuser=True):
            perfil_su, _ = PerfilUsuario.objects.get_or_create(user=su)
            perfil_su.rol = rol_admin
            perfil_su.codigo_institucional = perfil_su.codigo_institucional or f"ADM-{su.username.upper()}"
            perfil_su.programa_academico = "Ingeniería de Sistemas - IUP"
            perfil_su.save()
            self.stdout.write(f"Perfil de Administrador vinculado al superusuario '{su.username}'.")

        # Crear o actualizar usuario administrador estándar para demostración
        u_admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "Administrador",
                "last_name": "Institucional",
                "email": "admin@uniputumayo.edu.co",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }
        )
        if created or not u_admin.check_password("admin123"):
            u_admin.set_password("admin123")
            u_admin.is_staff = True
            u_admin.is_superuser = True
            u_admin.save()
        perfil_adm, _ = PerfilUsuario.objects.get_or_create(user=u_admin)
        perfil_adm.rol = rol_admin
        perfil_adm.codigo_institucional = "ADM-001"
        perfil_adm.programa_academico = "Dirección de Sistemas IUP"
        perfil_adm.save()

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

        # ----------------------------------------------------------------------
        # Categorías / Competencias oficiales Saber TyT
        # ----------------------------------------------------------------------
        from preguntas.models import Categoria, Pregunta, OpcionRespuesta, Cuestionario, CuestionarioPregunta
        from preguntas.services.importador_excel import calcular_huella
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal

        self.stdout.write("Inicializando competencias Saber TyT...")
        categorias_data = [
            ("Razonamiento Cuantitativo", "Resolución de problemas numéricos, estadísticos, geométricos y algebraicos."),
            ("Lectura Crítica", "Comprensión de textos continuos y discontinuos, análisis reflexivo y postura crítica."),
            ("Competencias Ciudadanas", "Conocimiento de la Constitución, resolución pacífica de conflictos y ética."),
            ("Inglés", "Comprensión lectora, gramática y vocabulario de lengua inglesa (niveles A1 a B2)."),
            ("Comunicación Escrita", "Producción de argumentos claros, coherencia, cohesión y estructura formal."),
            ("Desarrollo de Software", "Algoritmia, bases de datos relacionales, POO y frameworks de desarrollo."),
        ]
        cat_map = {}
        for nom, desc in categorias_data:
            c, _ = Categoria.objects.get_or_create(nombre=nom, defaults={"descripcion": desc})
            cat_map[nom] = c

        # ----------------------------------------------------------------------
        # Banco de Preguntas inicial de prueba si está vacío
        # ----------------------------------------------------------------------
        if Pregunta.objects.count() == 0:
            self.stdout.write("Poblando banco de reactivos iniciales...")
            preguntas_seed = [
                {
                    "categoria": cat_map["Razonamiento Cuantitativo"],
                    "tipo": Pregunta.TIPO_MULTIPLE,
                    "texto_base": "Una empresa de software tiene 40 desarrolladores. El 60% son programadores backend y el resto son frontend. Se planea contratar 10 programadores frontend más.",
                    "enunciado": "¿Qué porcentaje del total de desarrolladores serán ahora los programadores frontend?",
                    "puntaje": Decimal("1.25"),
                    "retroalimentacion": "Inicialmente hay 16 frontend (40%). Al sumar 10, hay 26 frontend de 50 en total: (26/50)*100 = 52%.",
                    "opciones": [
                        ("52%", True),
                        ("48%", False),
                        ("50%", False),
                        ("40%", False),
                    ]
                },
                {
                    "categoria": cat_map["Desarrollo de Software"],
                    "tipo": Pregunta.TIPO_MULTIPLE,
                    "texto_base": "En una base de datos relacional para gestión académica se tiene una entidad 'Estudiantes' y otra 'Cuestionarios'.",
                    "enunciado": "¿Qué característica define fundamentalmente a una clave primaria (PRIMARY KEY)?",
                    "puntaje": Decimal("1.25"),
                    "retroalimentacion": "Una clave primaria identifica de forma unívoca a cada registro y bajo ninguna circunstancia admite valores nulos (NOT NULL).",
                    "opciones": [
                        ("Identificar unívocamente cada fila y no admitir valores nulos", True),
                        ("Permitir valores nulos siempre que no se repitan", False),
                        ("Relacionar dos tablas distintas mediante integridad referencial", False),
                        ("Ser de tipo texto obligatoriamente", False),
                    ]
                },
                {
                    "categoria": cat_map["Desarrollo de Software"],
                    "tipo": Pregunta.TIPO_VF,
                    "texto_base": None,
                    "enunciado": "En la arquitectura MVC de Django (MTV), el ORM permite interactuar con la base de datos sin necesidad de escribir sentencias SQL nativas.",
                    "puntaje": Decimal("1.25"),
                    "retroalimentacion": "El Object-Relational Mapping (ORM) de Django abstrae las operaciones CRUD en modelos de Python.",
                    "opciones": [
                        ("Verdadero", True),
                        ("Falso", False),
                    ]
                },
                {
                    "categoria": cat_map["Competencias Ciudadanas"],
                    "tipo": Pregunta.TIPO_MULTIPLE,
                    "texto_base": "En una institución educativa se genera un debate sobre la privacidad de los datos personales en plataformas digitales académicas.",
                    "enunciado": "¿Cuál principio constitucional garantiza a los ciudadanos conocer, actualizar y rectificar las informaciones recogidas sobre ellos en bancos de datos?",
                    "puntaje": Decimal("1.25"),
                    "retroalimentacion": "El artículo 15 de la Constitución consagra el derecho al Habeas Data.",
                    "opciones": [
                        ("Derecho al Habeas Data", True),
                        ("Derecho a la Libertad de Cátedra", False),
                        ("Acción de Tutela", False),
                        ("Derecho de Petición General", False),
                    ]
                },
            ]

            preguntas_creadas = []
            for p_info in preguntas_seed:
                huella = calcular_huella(p_info["enunciado"], [o[0] for o in p_info["opciones"]])
                p_obj = Pregunta.objects.create(
                    categoria=p_info["categoria"],
                    tipo=p_info["tipo"],
                    texto_base=p_info["texto_base"],
                    enunciado=p_info["enunciado"],
                    retroalimentacion=p_info["retroalimentacion"],
                    puntaje=p_info["puntaje"],
                    huella_contenido=huella,
                    activa=True,
                )
                for idx, (txt, es_corr) in enumerate(p_info["opciones"], 1):
                    OpcionRespuesta.objects.create(
                        pregunta=p_obj,
                        texto=txt,
                        es_correcta=es_corr,
                        orden=idx,
                    )
                preguntas_creadas.append(p_obj)

            # ------------------------------------------------------------------
            # Cuestionario oficial disponible para la prueba en vivo
            # ------------------------------------------------------------------
            ahora = timezone.now()
            cuestionario_demo, _ = Cuestionario.objects.get_or_create(
                nombre="Simulacro Saber TyT 2026 - Prueba Oficial Uniputumayo",
                defaults={
                    "descripcion": "Simulacro de evaluación con calificación en tiempo real según los parámetros de la Unidad 2 de Frameworks.",
                    "fecha_apertura": ahora - timedelta(days=1),
                    "fecha_cierre": ahora + timedelta(days=30),
                    "tiempo_limite_minutos": 60,
                    "intentos_permitidos": 3,
                    "calificacion_maxima": Decimal("5.00"),
                    "calificacion_aprobacion": Decimal("3.00"),
                    "mezclar_preguntas": True,
                    "mezclar_respuestas": True,
                    "permitir_revision": True,
                    "estado": "disponible",
                }
            )
            for idx, p_obj in enumerate(preguntas_creadas, 1):
                CuestionarioPregunta.objects.get_or_create(
                    cuestionario=cuestionario_demo,
                    pregunta=p_obj,
                    defaults={"orden": idx, "puntaje_asignado": p_obj.puntaje}
                )
            self.stdout.write(f"Cuestionario '{cuestionario_demo.nombre}' configurado y disponible para estudiantes.")

        self.stdout.write(self.style.SUCCESS("Sembrado completo de roles, permisos, usuarios, competencias y cuestionario ejecutado con éxito."))
