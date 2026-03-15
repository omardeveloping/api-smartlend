from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from inventario.models import (
    categoria_herramienta,
    herramienta_individual,
    historial_herramienta,
    tipo_herramienta,
)
from operaciones.models import PrestamoTipoHerramienta, prestamo
from operaciones.tasks import (
    expirar_prestamo_pendiente,
    reconciliar_prestamos_pendientes_expirados,
)
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
        self.bodeguero_role = rol_usuarios.objects.create(
            nombre='Bodeguero',
            desc='Bodeguero',
            permisos='inventario',
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
        self.bodeguero = Usuario.objects.create(
            correo='bodeguero-reserva@example.com',
            rut='99999999-9',
            nombres='Bodega',
            apellidos='Reservas',
            id_rol=self.bodeguero_role,
        )
        self.client.force_authenticate(user=self.docente)
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
        self.client.force_authenticate(user=self.alumno)
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

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

        self.client.force_authenticate(user=self.alumno)
        non_docente_response = self.client.post(self.url, non_docente_payload, format='json')
        self.client.force_authenticate(user=self.docente)
        docente_response = self.client.post(self.url, docente_payload, format='json')

        self.assertEqual(non_docente_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tipos', non_docente_response.data)
        self.assertEqual(docente_response.status_code, status.HTTP_201_CREATED)

    def test_bodeguero_puede_crear_reserva_docente_para_estudiante(self):
        self.client.force_authenticate(user=self.bodeguero)
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PrestamoExpiracionSafetyTests(APITestCase):
    def setUp(self):
        self.role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.usuario = Usuario.objects.create(
            correo='expiracion-safety@example.com',
            rut='44444444-4',
            nombres='Katherine',
            apellidos='Johnson',
            id_rol=self.role,
        )
        self.categoria = categoria_herramienta.objects.create(nombre='Seguridad')
        self.tipo = tipo_herramienta.objects.create(
            nombre='Alicate',
            descripcion='Alicate de pruebas',
            id_categoria=self.categoria,
        )
        herramienta_individual.objects.create(
            codigo_barras='SEG-1',
            estado_herramienta=herramienta_individual.EstadoHerramienta.BUENO,
            disponible=True,
            fecha_adquisicion=timezone.now(),
            id_tipo_herramienta=self.tipo,
        )

    def _crear_prestamo_pendiente(self, fecha_prestamo):
        loan = prestamo.objects.create(
            fecha_prestamo=fecha_prestamo,
            fecha_devolucion_esperada=fecha_prestamo + timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
            id_usuario=self.usuario,
        )
        PrestamoTipoHerramienta.objects.create(
            prestamo=loan,
            tipo_herramienta=self.tipo,
            cantidad=1,
        )
        self.tipo.ajustar_reserva(1)
        return loan

    def test_reconciliacion_expira_pendiente_atrasado_y_libera_reserva(self):
        now = timezone.now()
        loan = self._crear_prestamo_pendiente(now - timedelta(minutes=40))

        result = reconciliar_prestamos_pendientes_expirados()

        loan.refresh_from_db()
        self.tipo.refresh_from_db()
        self.assertEqual(loan.estado_prestamo, prestamo.EstadoPrestamo.EXPIRADO)
        self.assertEqual(self.tipo.reservado, 0)
        self.assertEqual(result['expirados'], 1)

    def test_expirar_prestamo_pendiente_no_expira_antes_de_30_min(self):
        now = timezone.now()
        loan = self._crear_prestamo_pendiente(now - timedelta(minutes=10))

        result = expirar_prestamo_pendiente(loan.id_prestamo)

        loan.refresh_from_db()
        self.tipo.refresh_from_db()
        self.assertEqual(loan.estado_prestamo, prestamo.EstadoPrestamo.PENDIENTE)
        self.assertEqual(self.tipo.reservado, 1)
        self.assertEqual(result['status'], 'too_early')

    def test_reconciliacion_ignora_pendiente_dentro_de_ventana(self):
        now = timezone.now()
        vencido = self._crear_prestamo_pendiente(now - timedelta(minutes=45))
        vigente = self._crear_prestamo_pendiente(now - timedelta(minutes=5))

        result = reconciliar_prestamos_pendientes_expirados()

        vencido.refresh_from_db()
        vigente.refresh_from_db()
        self.tipo.refresh_from_db()
        self.assertEqual(vencido.estado_prestamo, prestamo.EstadoPrestamo.EXPIRADO)
        self.assertEqual(vigente.estado_prestamo, prestamo.EstadoPrestamo.PENDIENTE)
        self.assertEqual(self.tipo.reservado, 1)
        self.assertEqual(result['expirados'], 1)


class TurneroViewSetTests(APITestCase):
    def setUp(self):
        self.bodeguero_role = rol_usuarios.objects.create(
            nombre='Bodeguero',
            desc='Bodeguero',
            permisos='inventario',
        )
        self.bodeguero = Usuario.objects.create(
            correo='turnero-bodeguero@example.com',
            rut='33333333-1',
            nombres='Bodega',
            apellidos='Turnero',
            id_rol=self.bodeguero_role,
        )
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
        self.assertEqual(response.data['turno']['codigo_publico'], 'AA-GH10...')
        self.assertEqual(set(response.data['turno'].keys()), {'codigo_publico', 'estado_prestamo'})

        alias_response = self.client.get('/operaciones/api/prestamos/pantalla-turnos/')
        self.assertEqual(alias_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alias_response.data['turno']['codigo_publico'], 'AA-GH10...')

    def test_cola_es_publica(self):
        response = self.client.get('/operaciones/api/turnero/cola/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 2)
        self.assertEqual(len(response.data['pendientes']), 2)

    def test_siguiente_saltea_turno_actual_y_muestra_el_siguiente(self):
        self.client.get('/operaciones/api/turnero/actual/')
        self.client.force_authenticate(user=self.bodeguero)

        response = self.client.post('/operaciones/api/turnero/siguiente/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['anterior']['codigo_publico'], 'AA-GH10...')
        self.assertEqual(response.data['actual']['codigo_publico'], 'BB-GH10...')
        self.pendiente_antiguo.refresh_from_db()
        self.pendiente_reciente.refresh_from_db()
        self.assertEqual(self.pendiente_antiguo.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.SALTADO)
        self.assertEqual(self.pendiente_reciente.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.MOSTRADO)

    def test_rellamar_vuelve_a_poner_un_prestamo_saltado_en_pantalla(self):
        self.client.get('/operaciones/api/turnero/actual/')
        self.client.force_authenticate(user=self.bodeguero)
        self.client.post('/operaciones/api/turnero/siguiente/', {}, format='json')

        response = self.client.post(
            '/operaciones/api/turnero/rellamar/',
            {'prestamo_id': self.pendiente_antiguo.id_prestamo},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['actual']['codigo_publico'], 'AA-GH10...')
        self.pendiente_antiguo.refresh_from_db()
        self.pendiente_reciente.refresh_from_db()
        self.assertEqual(self.pendiente_antiguo.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.MOSTRADO)
        self.assertEqual(self.pendiente_reciente.estado_turno_pantalla, prestamo.EstadoTurnoPantalla.SALTADO)


class ReportesViewSetTests(APITestCase):
    def setUp(self):
        self.bodeguero_role = rol_usuarios.objects.create(
            nombre='Bodeguero',
            desc='Bodeguero',
            permisos='inventario',
        )
        self.bodeguero = Usuario.objects.create(
            correo='reportes-bodeguero@example.com',
            rut='11112222-1',
            nombres='Bodega',
            apellidos='Reportes',
            id_rol=self.bodeguero_role,
        )
        self.client.force_authenticate(user=self.bodeguero)
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


class PrestamoHerramientasNoUsablesTests(APITestCase):
    def setUp(self):
        self.role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.bodeguero_role = rol_usuarios.objects.create(
            nombre='bodeguero',
            desc='Bodeguero',
            permisos='inventario',
        )
        self.usuario = Usuario.objects.create(
            correo='no-usables@example.com',
            rut='77777777-7',
            nombres='Marie',
            apellidos='Curie',
            id_rol=self.role,
        )
        self.bodeguero = Usuario.objects.create(
            correo='bodeguero-no-usables@example.com',
            rut='88888888-8',
            nombres='Bodega',
            apellidos='Tester',
            id_rol=self.bodeguero_role,
        )
        self.categoria = categoria_herramienta.objects.create(nombre='Manual')
        self.tipo = tipo_herramienta.objects.create(
            nombre='Llave inglesa',
            descripcion='Herramienta para pruebas',
            id_categoria=self.categoria,
        )
        base = timezone.now()
        self.herramienta = herramienta_individual.objects.create(
            codigo_barras='NO-USA-1',
            estado_herramienta=herramienta_individual.EstadoHerramienta.BUENO,
            disponible=True,
            fecha_adquisicion=base,
            id_tipo_herramienta=self.tipo,
        )
        self.loan = prestamo.objects.create(
            fecha_prestamo=base - timedelta(minutes=5),
            fecha_devolucion_esperada=base + timedelta(days=1),
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
            id_usuario=self.usuario,
        )
        PrestamoTipoHerramienta.objects.create(
            prestamo=self.loan,
            tipo_herramienta=self.tipo,
            cantidad=1,
        )
        self.client.force_authenticate(user=self.bodeguero)

    def test_no_permite_asignar_herramienta_no_usable(self):
        herramienta_individual.objects.filter(pk=self.herramienta.pk).update(
            estado_herramienta=herramienta_individual.EstadoHerramienta.DEFECTUOSO,
            disponible=True,
        )

        response = self.client.post(
            f'/operaciones/api/prestamos/{self.loan.id_prestamo}/asignar_herramientas/',
            {'codigos': [self.herramienta.codigo_barras]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no usables', response.data.get('detail', '').lower())

    def test_devolucion_danada_no_reactiva_disponibilidad(self):
        self.herramienta.disponible = False
        self.herramienta.save(update_fields=['disponible'])
        self.loan.herramientas.add(self.herramienta)
        self.loan.estado_prestamo = prestamo.EstadoPrestamo.ENTREGADO
        self.loan.save(update_fields=['estado_prestamo'])
        self.client.force_authenticate(user=self.bodeguero)

        response = self.client.post(
            f'/operaciones/api/prestamos/{self.loan.id_prestamo}/devolver_herramientas/',
            {
                'codigos': [self.herramienta.codigo_barras],
                'estados': {
                    self.herramienta.codigo_barras: herramienta_individual.EstadoHerramienta.DANADO,
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.herramienta.refresh_from_db()
        self.assertEqual(
            self.herramienta.estado_herramienta,
            herramienta_individual.EstadoHerramienta.DANADO,
        )
        self.assertFalse(self.herramienta.disponible)
        registro = historial_herramienta.objects.get(
            prestamo=self.loan,
            herramienta=self.herramienta,
        )
        self.assertEqual(registro.usuario_id, self.bodeguero.id)
        self.assertEqual(registro.prestamo.id_usuario_id, self.usuario.id)

    def test_asignar_herramientas_incrementa_numero_prestamos(self):
        self.assertEqual(self.herramienta.numero_prestamos, 0)

        response = self.client.post(
            f'/operaciones/api/prestamos/{self.loan.id_prestamo}/asignar_herramientas/',
            {'codigos': [self.herramienta.codigo_barras]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.herramienta.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertEqual(self.herramienta.numero_prestamos, 1)
        self.assertEqual(self.loan.estado_prestamo, prestamo.EstadoPrestamo.ENTREGADO)
