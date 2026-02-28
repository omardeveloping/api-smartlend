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


class TurneroViewSetTests(APITestCase):
    def setUp(self):
        self.role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.usuario = Usuario.objects.create(
            correo='turnos@example.com',
            rut='33333333-3',
            nombres='Grace',
            apellidos='Hopper',
            id_rol=self.role,
        )
        base = timezone.now()
        self.pendiente_antiguo = prestamo.objects.create(
            fecha_prestamo=base - timedelta(hours=2),
            fecha_devolucion_esperada=base + timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
            id_usuario=self.usuario,
            codigo='AA-GH1001',
        )
        self.pendiente_reciente = prestamo.objects.create(
            fecha_prestamo=base - timedelta(hours=1),
            fecha_devolucion_esperada=base + timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
            id_usuario=self.usuario,
            codigo='BB-GH1002',
        )
        self.pendiente_futuro = prestamo.objects.create(
            fecha_prestamo=base + timedelta(days=1),
            fecha_devolucion_esperada=base + timedelta(days=2),
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
            id_usuario=self.usuario,
            codigo='DD-GH1004',
        )
        prestamo.objects.create(
            fecha_prestamo=base - timedelta(hours=3),
            fecha_devolucion_esperada=base + timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.ENTREGADO,
            id_usuario=self.usuario,
            codigo='CC-GH1003',
        )

    def test_actual_publico_muestra_un_solo_prestamo_sin_datos_sensibles(self):
        response = self.client.get('/operaciones/api/turnero/actual/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['hay_turno'])
        self.assertEqual(response.data['pendientes_listos'], 2)
        self.assertEqual(response.data['turno']['codigo_publico'], 'AA-...1001')
        self.assertEqual(set(response.data['turno'].keys()), {'codigo_publico', 'estado_prestamo'})

        alias_response = self.client.get('/operaciones/api/prestamos/pantalla-turnos/')
        self.assertEqual(alias_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alias_response.data['turno']['codigo_publico'], 'AA-...1001')

    def test_siguiente_saltea_turno_actual_y_muestra_el_siguiente(self):
        self.client.get('/operaciones/api/turnero/actual/')

        response = self.client.post('/operaciones/api/turnero/siguiente/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['anterior']['codigo_publico'], 'AA-...1001')
        self.assertEqual(response.data['actual']['codigo_publico'], 'BB-...1002')
        self.pendiente_antiguo.refresh_from_db()
        self.pendiente_reciente.refresh_from_db()
        self.assertEqual(self.pendiente_antiguo.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.SALTADO)
        self.assertEqual(self.pendiente_reciente.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.MOSTRADO)

    def test_rellamar_vuelve_a_poner_un_prestamo_saltado_en_pantalla(self):
        self.client.get('/operaciones/api/turnero/actual/')
        self.client.post('/operaciones/api/turnero/siguiente/', {}, format='json')

        response = self.client.post(
            '/operaciones/api/turnero/rellamar/',
            {'prestamo_id': self.pendiente_antiguo.id_prestamo},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['actual']['codigo_publico'], 'AA-...1001')
        self.pendiente_antiguo.refresh_from_db()
        self.pendiente_reciente.refresh_from_db()
        self.assertEqual(self.pendiente_antiguo.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.MOSTRADO)
        self.assertEqual(self.pendiente_reciente.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.SALTADO)


class ReportesViewSetTests(APITestCase):
    def setUp(self):
        self.role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.usuario = Usuario.objects.create(
            correo='reportes@example.com',
            rut='11112222-3',
            nombres='Linus',
            apellidos='Torvalds',
            id_rol=self.role,
        )
        self.categoria = categoria_herramienta.objects.create(nombre='Electricas')
        self.tipo = tipo_herramienta.objects.create(
            nombre='Taladro',
            descripcion='Taladro de banco',
            id_categoria=self.categoria,
        )
        base = timezone.now()
        herramienta_individual.objects.create(
            codigo_barras='INV-1',
            estado_herramienta=herramienta_individual.EstadoHerramienta.BUENO,
            disponible=True,
            fecha_adquisicion=base,
            id_tipo_herramienta=self.tipo,
        )
        herramienta_individual.objects.create(
            codigo_barras='INV-2',
            estado_herramienta=herramienta_individual.EstadoHerramienta.BUENO,
            disponible=False,
            fecha_adquisicion=base,
            id_tipo_herramienta=self.tipo,
        )
        self.tipo.recalcular_stock()
        self.prestamo_finalizado = prestamo.objects.create(
            fecha_prestamo=base - timedelta(days=5),
            fecha_devolucion_esperada=base - timedelta(days=3),
            fecha_devolucion_real=base - timedelta(days=2),
            estado_prestamo=prestamo.EstadoPrestamo.FINALIZADO,
            id_usuario=self.usuario,
        )
        self.prestamo_moroso = prestamo.objects.create(
            fecha_prestamo=base - timedelta(days=4),
            fecha_devolucion_esperada=base - timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.VENCIDO,
            id_usuario=self.usuario,
        )

    def test_reporte_inventario_agrupa_por_tipo(self):
        response = self.client.get('/operaciones/api/reportes/inventario/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['resultados'][0]['nombre'], 'Taladro')
        self.assertEqual(response.data['resultados'][0]['total_herramientas'], 2)

    def test_reporte_prestamos_filtra_por_rango(self):
        fecha = (timezone.now() - timedelta(days=5)).date().isoformat()
        fecha_hasta = (timezone.now() - timedelta(days=5)).date().isoformat()

        response = self.client.get(
            f'/operaciones/api/reportes/prestamos/?fecha_desde={fecha}&fecha_hasta={fecha_hasta}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item['id_prestamo'] for item in response.data['resultados']}
        self.assertIn(self.prestamo_finalizado.id_prestamo, ids)
        self.assertNotIn(self.prestamo_moroso.id_prestamo, ids)

    def test_reporte_morosos_retorna_usuario_asociado(self):
        response = self.client.get('/operaciones/api/reportes/morosos/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['resultados'][0]['usuario_id'], self.usuario.id)
        self.assertEqual(response.data['resultados'][0]['correo'], self.usuario.correo)

    def test_reporte_inventario_pdf_retorna_archivo(self):
        response = self.client.get('/operaciones/api/reportes/inventario/?formato=pdf')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
