from django.core.management.base import BaseCommand

from apps.academico.services import asignar_cursos_pendientes


class Command(BaseCommand):
    help = "Asigna el curso a los intentos anteriores según la matrícula vigente del estudiante en esa fecha."

    def handle(self, *args, **options):
        total = asignar_cursos_pendientes()
        self.stdout.write(self.style.SUCCESS(f"{total} intento(s) quedaron asociados a su curso."))
