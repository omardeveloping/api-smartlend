from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from operaciones.models import alerta, prestamo
from usuarios.models import DirectorCarrera

@shared_task
def expirar_prestamo_pendiente(prestamo_id):
    """
    Marca como Expirado un préstamo pendiente si siguen pasando 30 minutos sin entrega.
    Libera las herramientas asignadas para que vuelvan a estar disponibles.
    """
    try:
        loan = prestamo.objects.prefetch_related('herramientas', 'tipos_prestamo__tipo_herramienta').get(pk=prestamo_id)
    except prestamo.DoesNotExist:
        return {'status': 'not_found'}

    if loan.estado_prestamo != prestamo.EstadoPrestamo.PENDIENTE:
        return {'status': 'no_change'}

    with transaction.atomic():
        loan.estado_prestamo = prestamo.EstadoPrestamo.EXPIRADO
        loan.save(update_fields=['estado_prestamo'])

        # liberar reservas virtuales
        for tp in loan.tipos_prestamo.all():
            if tp.tipo_herramienta:
                tp.tipo_herramienta.ajustar_reserva(-tp.cantidad)

        herramientas = list(loan.herramientas.all())
        for herramienta in herramientas:
            if not herramienta.disponible:
                herramienta.disponible = True
                herramienta.save(update_fields=['disponible'])

    return {'status': 'expired', 'herramientas_liberadas': len(herramientas)}


### Tengo que echarle una mirada a esto después de tener todo lo demás listo. (Aprendizaje para el futuro)
@shared_task
def ban_overdue_prestamos():
    """
    Bans users with loans that have been marked as Vencido for 20+ days
    and notifies their director de carrera by email.
    Also escalates alert criticidad at 5/10/20 days and notifies the student at 10 days.
    """
    now = timezone.now()

    overdue_loans = (
        prestamo.objects.select_related(
            'id_usuario',
            'id_usuario__id_carrera',
            'id_herramienta_individual',
            'id_herramienta_individual__id_tipo_herramienta',
        ).prefetch_related(
            'herramientas',
            'herramientas__id_tipo_herramienta',
            'tipos_prestamo__tipo_herramienta',
        )
        .filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
        )
    )

    users_to_ban = {}
    for loan in overdue_loans:
        # Asegura estado VENCIDO cuando pasa la fecha.
        if loan.estado_prestamo != prestamo.EstadoPrestamo.VENCIDO:
            loan.estado_prestamo = prestamo.EstadoPrestamo.VENCIDO
            loan.save(update_fields=['estado_prestamo'])

        dias_atraso = (now - loan.fecha_devolucion_esperada).days

        # Criticidad y alertas
        criticidad = None
        if dias_atraso >= 20:
            criticidad = 'Critico'
        elif dias_atraso >= 10:
            criticidad = 'Medio'
        elif dias_atraso >= 5:
            criticidad = 'Bajo'

        if criticidad:
            alerta_obj, _ = alerta.objects.get_or_create(
                prestamo=loan,
                defaults={
                    'mensaje': 'Prestamo vencido',
                    'criticidad': criticidad,
                },
            )
            prev_criticidad = alerta_obj.criticidad
            # Actualiza criticidad si cambia
            if alerta_obj.criticidad != criticidad or alerta_obj.resuelta:
                alerta_obj.criticidad = criticidad
                alerta_obj.resuelta = False
                alerta_obj.resuelta_en = None
                alerta_obj.save(update_fields=['criticidad', 'resuelta', 'resuelta_en'])

            # Envia correo al estudiante al llegar a medio o superior (>=10 dias) solo al subir de nivel
            if (
                criticidad in ('Medio', 'Critico')
                and criticidad != prev_criticidad
                and loan.id_usuario
                and loan.id_usuario.correo
            ):
                if not loan.codigo:
                    loan.save(update_fields=['codigo'])
                codigo_texto = loan.codigo or 'N/A'
                herramientas = list(loan.herramientas.all())
                if not herramientas and getattr(loan, 'id_herramienta_individual_id', None):
                    herramientas = [loan.id_herramienta_individual]
                herramientas_codigos = ', '.join([h.codigo_barras for h in herramientas if h.codigo_barras])
                tipos_herramienta = {
                    getattr(h.id_tipo_herramienta, 'nombre', None) for h in herramientas
                }
                herramienta_nombre = ', '.join(sorted(filter(None, tipos_herramienta)))
                if not herramienta_nombre:
                    tipos = loan.tipos_prestamo.select_related('tipo_herramienta').all()
                    nombres = [t.tipo_herramienta.nombre for t in tipos if t.tipo_herramienta]
                    herramienta_nombre = ', '.join(sorted(set(nombres)))
                detalle_herramientas = f'Herramientas: {herramientas_codigos}.\n' if herramientas_codigos else ''
                subject = 'Recuerda devolver tu préstamo vencido'
                body = (
                    f'Hola {loan.id_usuario.nombres},\n\n'
                    'Tienes un préstamo vencido. Por favor devuelve la herramienta.\n'
                    f'Préstamo #{loan.id_prestamo} '
                    f'{"(" + herramienta_nombre + ") " if herramienta_nombre else ""}'
                    f'venció el {loan.fecha_devolucion_esperada.date()} '
                    f'y su código es {codigo_texto}.\n'
                    f'{detalle_herramientas}'
                    f'Lleva {dias_atraso} días de atraso.\n\n'
                    'Si llegas a 20 días serás bloqueado y se notificará al director de carrera.'
                )
                try:
                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [loan.id_usuario.correo],
                        fail_silently=True,
                    )
                except Exception:
                    pass

        # Acumula para ban si aplica 20+
        if dias_atraso >= 20:
            user = loan.id_usuario
            if user.esta_baneado and user.aviso_ban_enviado:
                continue
            users_to_ban.setdefault(user.id, {'user': user, 'loans': []})['loans'].append(loan)

    for info in users_to_ban.values():
        user = info['user']
        loans = info['loans']

        with transaction.atomic():
            update_fields = []
            if not user.esta_baneado:
                user.esta_baneado = True
                update_fields.append('esta_baneado')
            if user.baneado_en is None:
                user.baneado_en = now
                update_fields.append('baneado_en')
            user.aviso_ban_enviado = False
            update_fields.append('aviso_ban_enviado')
            user.save(update_fields=update_fields)

        director_email = None
        director_nombre = None
        if user.id_carrera_id:
            director = DirectorCarrera.objects.filter(carrera=user.id_carrera).first()
            if director:
                director_email = director.correo
                director_nombre = director.nombre

        if director_email:
            subject = '[Smartlend] Usuario bloqueado por préstamo vencido'
            prestamos_text = ', '.join(
                f'#{loan.id_prestamo} (esperada {loan.fecha_devolucion_esperada.date()})'
                for loan in loans
            )
            body = (
                f'Estimado/a {director_nombre or ""},\n\n'
                'Smartlend le informa que se ha bloqueado a un usuario por un préstamo vencido.\n\n'
                f'Usuario: {user.nombres} {user.apellidos} ({user.correo})\n'
                f'Carrera: {getattr(user.id_carrera, "nombre", "-")}\n'
                'Motivo: mantiene uno o más préstamos vencidos por más de 20 días.\n'
                f'Préstamos involucrados: {prestamos_text}.\n\n'
                'Por favor revise la situación o comuníquese con el usuario. Este mensaje fue generado automáticamente por Smartlend.'
            )
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [director_email], fail_silently=False)
                user.aviso_ban_enviado = True
                user.save(update_fields=['aviso_ban_enviado'])
            except Exception:
                # Keep user banned even if email fails; next run can retry notification.
                pass

    return {'users_banned': len(users_to_ban)}
