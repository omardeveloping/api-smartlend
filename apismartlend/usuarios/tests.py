from datetime import timedelta
from unittest.mock import patch

import numpy as np
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from operaciones.models import prestamo
from usuarios.models import Usuario, rol_usuarios


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@smartlend.test',
    SMARTLEND_SUPPORT_EMAIL='soporte@smartlend.test',
)
class AsistenciaTecnicaTests(APITestCase):
    url = '/usuarios/api/soporte/enviar-asistencia/'

    def test_enviar_asistencia_tecnica_envia_correo(self):
        payload = {
            'rol': 'bodeguero',
            'ventana': 'Reportes',
            'descripcion': 'No carga el reporte de inventario',
            'destinatario': 'smartlend.notificacion@gmail.com',
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mensaje'], 'Solicitud enviada correctamente')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['soporte@smartlend.test'])
        self.assertEqual(
            mail.outbox[0].subject,
            '[SOPORTE] Nueva Solicitud de Asistencia - bodeguero',
        )
        self.assertIn('Rol del Usuario: bodeguero', mail.outbox[0].body)
        self.assertIn('Ventana/Página: Reportes', mail.outbox[0].body)
        self.assertIn('No carga el reporte de inventario', mail.outbox[0].body)

    def test_enviar_asistencia_tecnica_exige_campos_obligatorios(self):
        response = self.client.post(
            self.url,
            {'rol': 'bodeguero', 'descripcion': 'Falta ventana'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Faltan campos obligatorios')

    @patch('usuarios.views.send_mail', side_effect=Exception('smtp down'))
    def test_enviar_asistencia_tecnica_retorna_500_si_falla_correo(self, _mock_send_mail):
        response = self.client.post(
            self.url,
            {
                'rol': 'estudiante',
                'ventana': 'Prestamos',
                'descripcion': 'Error al crear préstamo',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['detail'], 'Error al conectar con el servidor de correo')


class UsuarioDashboardBodegueroTests(APITestCase):
    def setUp(self):
        self.alumno_role = rol_usuarios.objects.create(
            nombre='Alumno',
            desc='Alumno',
            permisos='prestamos',
        )
        self.usuario = Usuario.objects.create(
            correo='usuario@example.com',
            rut='12345678-9',
            nombres='Grace',
            apellidos='Hopper',
            id_rol=self.alumno_role,
            esta_baneado=True,
            aviso_ban_enviado=True,
            baneado_en=timezone.now(),
        )
        self.otro_usuario = Usuario.objects.create(
            correo='otro@example.com',
            rut='98765432-1',
            nombres='Otro',
            apellidos='Usuario',
            id_rol=self.alumno_role,
        )
        now = timezone.now()
        self.finalizado = prestamo.objects.create(
            fecha_prestamo=now - timedelta(days=7),
            fecha_devolucion_esperada=now - timedelta(days=5),
            fecha_devolucion_real=now - timedelta(days=4),
            estado_prestamo=prestamo.EstadoPrestamo.FINALIZADO,
            id_usuario=self.usuario,
        )
        self.entregado = prestamo.objects.create(
            fecha_prestamo=now - timedelta(days=1),
            fecha_devolucion_esperada=now + timedelta(days=2),
            estado_prestamo=prestamo.EstadoPrestamo.ENTREGADO,
            id_usuario=self.usuario,
        )
        self.vencido = prestamo.objects.create(
            fecha_prestamo=now - timedelta(days=10),
            fecha_devolucion_esperada=now - timedelta(days=2),
            estado_prestamo=prestamo.EstadoPrestamo.VENCIDO,
            id_usuario=self.usuario,
        )
        self.cancelado_otro = prestamo.objects.create(
            fecha_prestamo=now - timedelta(days=3),
            fecha_devolucion_esperada=now - timedelta(days=2),
            estado_prestamo=prestamo.EstadoPrestamo.CANCELADO,
            id_usuario=self.otro_usuario,
        )
        self.client.force_authenticate(user=self.usuario)

    def test_historial_prestamos_retorna_solo_finalizados_del_usuario(self):
        response = self.client.get(f'/usuarios/api/usuarios/{self.usuario.id}/historial-prestamos/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['prestamos'][0]['id_prestamo'], self.finalizado.id_prestamo)

    def test_prestamos_activos_retorna_abiertos_y_vencidos(self):
        response = self.client.get(f'/usuarios/api/usuarios/{self.usuario.id}/prestamos-activos/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item['id_prestamo'] for item in response.data['prestamos']}
        self.assertEqual(response.data['total'], 2)
        self.assertSetEqual(ids, {self.entregado.id_prestamo, self.vencido.id_prestamo})

    def test_estado_bloqueo_retorna_flags_del_usuario(self):
        response = self.client.get(f'/usuarios/api/usuarios/{self.usuario.id}/estado-bloqueo/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['esta_baneado'])
        self.assertEqual(response.data['prestamos_vencidos_activos'], 1)

    def test_dashboard_bodeguero_consolida_historial_activos_y_bloqueo(self):
        response = self.client.get(f'/usuarios/api/usuarios/{self.usuario.id}/dashboard-bodeguero/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['historial_finalizados']['total'], 1)
        self.assertEqual(response.data['prestamos_activos']['total'], 2)
        self.assertTrue(response.data['estado_bloqueo']['esta_baneado'])


class LoginFaceTests(APITestCase):
    def setUp(self):
        self.docente_role = rol_usuarios.objects.create(
            nombre='Docente',
            desc='Docente',
            permisos='prestamos',
        )
        self.usuario = Usuario.objects.create(
            correo='docente@example.com',
            rut='11111111-1',
            nombres='Ada',
            apellidos='Lovelace',
            id_rol=self.docente_role,
            embedding='dummy-encrypted-embedding',
        )

    @patch('usuarios.views.processor.match_embeddings', return_value=(True, 0.1))
    @patch('usuarios.views.processor.decrypt_embedding', return_value=np.zeros(128))
    def test_login_face_incluye_rol_y_correo_en_respuesta(self, _mock_decrypt, _mock_match):
        response = self.client.post(
            '/usuarios/auth/login/',
            {'embedding': [0.0] * 128},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['existe_embedding'])
        self.assertEqual(response.data['usuario_id'], self.usuario.id)
        self.assertEqual(response.data['correo'], self.usuario.correo)
        self.assertEqual(response.data['rol'], 'Docente')
        self.assertIn('token', response.data)
