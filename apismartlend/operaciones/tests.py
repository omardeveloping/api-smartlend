from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from inventario.models import categoria_herramienta, herramienta_individual, tipo_herramienta
from operaciones.models import prestamo
from usuarios.models import Usuario, rol_usuarios


class PrestamoReservaDocenteTests(APITestCase):
    def setUp(self):
        self.docente_role = rol_usuarios.objects.create(
            nombre='Docente',
            desc='Docente',
            permisos='prestamos',
        )
        self.alumno_role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.docente = Usuario.objects.create(
            correo='docente@example.com',
            rut='11111111-1',
            nombres='Ada',
            apellidos='Lovelace',
            id_rol=self.docente_role,
        )
        self.alumno = Usuario.objects.create(
            correo='alumno@example.com',
            rut='22222222-2',
            nombres='Alan',
            apellidos='Turing',
            id_rol=self.alumno_role,
        )
        self.categoria = categoria_herramienta.objects.create(nombre='Manual')
        self.tipo = tipo_herramienta.objects.create(
            nombre='Martillo',
            descripcion='Martillo de prueba',
            id_categoria=self.categoria,
        )
        self._crear_herramientas_disponibles(3)
        self.url = '/operaciones/api/prestamos/'
        self.reserva_docente_url = '/operaciones/api/prestamos/reserva-docente/'

    def _crear_herramientas_disponibles(self, cantidad):
        base = timezone.now()
        for idx in range(cantidad):
            herramienta_individual.objects.create(
                codigo_barras=f'BAR-{idx}',
                estado_herramienta=herramienta_individual.EstadoHerramienta.BUENO,
                disponible=True,
                fecha_adquisicion=base,
                id_tipo_herramienta=self.tipo,
            )

    def test_docente_puede_crear_reserva_para_manana(self):
        tomorrow = timezone.now() + timedelta(days=1)
        payload = {
            'id_usuario': self.docente.id,
            'fecha_inicio_reserva': tomorrow.isoformat(),
            'tipos': [
                {
                    'tipo_herramienta': self.tipo.id_tipo_herramienta,
                    'cantidad': 2,
                }
            ],
        }

        response = self.client.post(self.reserva_docente_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = prestamo.objects.get(id_prestamo=response.data['id_prestamo'])
        self.assertEqual(timezone.localdate(loan.fecha_prestamo), timezone.localdate(tomorrow))
        self.assertEqual(loan.fecha_devolucion_esperada, loan.fecha_prestamo + timedelta(days=1))
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.reservado, 2)

    def test_alumno_no_puede_reservar_para_manana(self):
        tomorrow = timezone.now() + timedelta(days=1)
        payload = {
            'id_usuario': self.alumno.id,
            'fecha_inicio_reserva': tomorrow.isoformat(),
            'tipos': [
                {
                    'tipo_herramienta': self.tipo.id_tipo_herramienta,
                    'cantidad': 1,
                }
            ],
        }

        response = self.client.post(self.reserva_docente_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id_usuario', response.data)

    def test_endpoint_reserva_docente_exige_fecha_inicio_reserva(self):
        payload = {
            'id_usuario': self.docente.id,
            'tipos': [
                {
                    'tipo_herramienta': self.tipo.id_tipo_herramienta,
                    'cantidad': 1,
                }
            ],
        }

        response = self.client.post(self.reserva_docente_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha_inicio_reserva', response.data)

    @override_settings(SMARTLEND_MAX_ITEMS_PER_LOAN=1)
    def test_limite_configurable_aplica_a_no_docente_y_se_omite_para_docente(self):
        now = timezone.now()
        non_docente_payload = {
            'id_usuario': self.alumno.id,
            'fecha_prestamo': now.isoformat(),
            'fecha_devolucion_esperada': (now + timedelta(days=1)).isoformat(),
            'tipos': [
                {
                    'tipo_herramienta': self.tipo.id_tipo_herramienta,
                    'cantidad': 2,
                }
            ],
        }

        docente_payload = {
            'id_usuario': self.docente.id,
            'fecha_prestamo': now.isoformat(),
            'fecha_devolucion_esperada': (now + timedelta(days=1)).isoformat(),
            'tipos': [
                {
                    'tipo_herramienta': self.tipo.id_tipo_herramienta,
                    'cantidad': 2,
                }
            ],
        }

        non_docente_response = self.client.post(self.url, non_docente_payload, format='json')
        docente_response = self.client.post(self.url, docente_payload, format='json')

        self.assertEqual(non_docente_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tipos', non_docente_response.data)
        self.assertEqual(docente_response.status_code, status.HTTP_201_CREATED)
