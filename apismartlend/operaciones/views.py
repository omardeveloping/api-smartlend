from collections import Counter
from io import BytesIO

from django.http import HttpResponse
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from inventario.models import herramienta_individual, historial_herramienta, tipo_herramienta

from .models import (
    alerta,
    prestamo,
)
from .serializers import (
    AlertaSerializer,
    PrestamoSerializer,
    PrestamoTurnoGestionSerializer,
    PrestamoTurnoPublicoSerializer,
)


def _turnos_listos_queryset(now=None, for_update=False):
    now = now or timezone.now()
    queryset = prestamo.objects.filter(
        estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
        fecha_prestamo__lte=now,
    )
    if for_update:
        queryset = queryset.select_for_update()
    return queryset


def _normalizar_turnero(now=None):
    now = now or timezone.now()
    prestamo.objects.exclude(
        estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
    ).exclude(
        estado_turno_pantalla=prestamo.EstadoTurnoPantalla.FUERA_DE_COLA,
    ).update(estado_turno_pantalla=prestamo.EstadoTurnoPantalla.FUERA_DE_COLA)
    prestamo.objects.filter(
        estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
        fecha_prestamo__gt=now,
        estado_turno_pantalla=prestamo.EstadoTurnoPantalla.MOSTRADO,
    ).update(estado_turno_pantalla=prestamo.EstadoTurnoPantalla.EN_COLA)


def _marcar_turno_mostrado(loan, now=None):
    if loan is None:
        return None

    now = now or timezone.now()
    loan.estado_turno_pantalla = prestamo.EstadoTurnoPantalla.MOSTRADO
    loan.turno_mostrado_en = now
    loan.turno_veces_mostrado = (loan.turno_veces_mostrado or 0) + 1
    loan.save(
        update_fields=[
            'estado_turno_pantalla',
            'turno_mostrado_en',
            'turno_veces_mostrado',
        ]
    )
    return loan


def _obtener_turno_actual():
    now = timezone.now()
    with transaction.atomic():
        _normalizar_turnero(now)
        mostrados = list(
            _turnos_listos_queryset(now=now, for_update=True).filter(
                estado_turno_pantalla=prestamo.EstadoTurnoPantalla.MOSTRADO,
            ).order_by('turno_mostrado_en', 'fecha_prestamo', 'id_prestamo')
        )
        if mostrados:
            actual = mostrados[0]
            for extra in mostrados[1:]:
                extra.estado_turno_pantalla = prestamo.EstadoTurnoPantalla.SALTADO
                extra.save(update_fields=['estado_turno_pantalla'])
            return actual

        siguiente = _turnos_listos_queryset(now=now, for_update=True).filter(
            estado_turno_pantalla=prestamo.EstadoTurnoPantalla.EN_COLA,
        ).order_by('fecha_prestamo', 'id_prestamo').first()
        return _marcar_turno_mostrado(siguiente, now=now)


def _payload_turno_publico():
    now = timezone.now()
    actual = _obtener_turno_actual()
    pendientes_listos = _turnos_listos_queryset(now=now).count()
    return {
        'hay_turno': actual is not None,
        'turno': PrestamoTurnoPublicoSerializer(actual).data if actual else None,
        'pendientes_listos': pendientes_listos,
    }


class TurneroViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def actual(self, request):
        return Response(_payload_turno_publico(), status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def cola(self, request):
        now = timezone.now()
        _normalizar_turnero(now)
        queue = _turnos_listos_queryset(now=now).filter(
            estado_turno_pantalla__in=[
                prestamo.EstadoTurnoPantalla.EN_COLA,
                prestamo.EstadoTurnoPantalla.MOSTRADO,
                prestamo.EstadoTurnoPantalla.SALTADO,
            ]
        ).order_by('fecha_prestamo', 'id_prestamo')
        data = PrestamoTurnoGestionSerializer(queue, many=True).data
        return Response(
            {
                'total': len(data),
                'pendientes': data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'])
    def siguiente(self, request):
        now = timezone.now()
        with transaction.atomic():
            _normalizar_turnero(now)
            actual = _turnos_listos_queryset(now=now, for_update=True).filter(
                estado_turno_pantalla=prestamo.EstadoTurnoPantalla.MOSTRADO,
            ).order_by('turno_mostrado_en', 'fecha_prestamo', 'id_prestamo').first()
            if actual is not None:
                actual.estado_turno_pantalla = prestamo.EstadoTurnoPantalla.SALTADO
                actual.save(update_fields=['estado_turno_pantalla'])

            siguiente = _turnos_listos_queryset(now=now, for_update=True).filter(
                estado_turno_pantalla=prestamo.EstadoTurnoPantalla.EN_COLA,
            ).order_by('fecha_prestamo', 'id_prestamo').first()
            siguiente = _marcar_turno_mostrado(siguiente, now=now)

        return Response(
            {
                'anterior': PrestamoTurnoGestionSerializer(actual).data if actual else None,
                'actual': PrestamoTurnoGestionSerializer(siguiente).data if siguiente else None,
                'pendientes_listos': _turnos_listos_queryset(now=timezone.now()).count(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'])
    def rellamar(self, request):
        prestamo_id = request.data.get('prestamo_id')
        if not prestamo_id:
            return Response({'detail': 'prestamo_id es obligatorio'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            prestamo_id = int(prestamo_id)
        except (TypeError, ValueError):
            return Response({'detail': 'prestamo_id debe ser un entero válido'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        with transaction.atomic():
            _normalizar_turnero(now)
            target = prestamo.objects.select_for_update().filter(pk=prestamo_id).first()
            if target is None:
                return Response({'detail': 'No se encontró el préstamo indicado'}, status=status.HTTP_404_NOT_FOUND)
            if not target.esta_listo_para_turnero(now=now):
                return Response(
                    {'detail': 'Solo puedes rellamar préstamos pendientes cuya fecha de retiro ya comenzó'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            actual = _turnos_listos_queryset(now=now, for_update=True).filter(
                estado_turno_pantalla=prestamo.EstadoTurnoPantalla.MOSTRADO,
            ).order_by('turno_mostrado_en', 'fecha_prestamo', 'id_prestamo').first()
            if actual is not None and actual.id_prestamo != target.id_prestamo:
                actual.estado_turno_pantalla = prestamo.EstadoTurnoPantalla.SALTADO
                actual.save(update_fields=['estado_turno_pantalla'])

            target = _marcar_turno_mostrado(target, now=now)

        return Response(
            {
                'actual': PrestamoTurnoGestionSerializer(target).data,
                'pendientes_listos': _turnos_listos_queryset(now=timezone.now()).count(),
            },
            status=status.HTTP_200_OK,
        )


class PrestamoViewSet(viewsets.ModelViewSet):
    queryset = prestamo.objects.all().prefetch_related(
        'herramientas',
        'herramientas__id_tipo_herramienta',
        'tipos_prestamo__tipo_herramienta',
    )
    serializer_class = PrestamoSerializer

    @action(detail=False, methods=['post'], url_path='reserva-docente')
    def reserva_docente(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                'require_reserva_docente': True,
            },
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        now = timezone.now()
        vencidos = self.get_queryset().filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
        )
        serializer = self.get_serializer(vencidos, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        pendientes = self.get_queryset().filter(
            estado_prestamo=prestamo.EstadoPrestamo.PENDIENTE,
        )
        serializer = self.get_serializer(pendientes, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['get'],
        url_path='pantalla-turnos',
        permission_classes=[AllowAny],
    )
    def pantalla_turnos(self, request):
        return Response(_payload_turno_publico(), status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        codigo = request.query_params.get('codigo', '').strip()
        if not codigo:
            return Response(
                {'detail': 'Falta el parámetro codigo'},
                status=400,
            )

        prestamos = self.get_queryset().filter(
            codigo__iexact=codigo,
            estado_prestamo__in=[
                prestamo.EstadoPrestamo.PENDIENTE,
                prestamo.EstadoPrestamo.ENTREGADO,
            ],
        )
        serializer = self.get_serializer(prestamos, many=True)
        return Response(serializer.data)

    ### Le asigna herramientas a un préstamo
    @action(detail=True, methods=['post'])
    def asignar_herramientas(self, request, pk=None):
        loan = self.get_object()
        prestamo_cambiara_a_entregado = (
            loan.estado_prestamo == prestamo.EstadoPrestamo.PENDIENTE
        )
        codigos = request.data.get('codigos')
        if not isinstance(codigos, list):
            return Response({'detail': 'codigos debe ser una lista'}, status=400)
        codigos = [str(c).strip() for c in codigos if str(c).strip()]
        if not codigos:
            return Response({'detail': 'codigos no puede estar vacío'}, status=400)
        duplicados = [c for c, count in Counter(codigos).items() if count > 1]
        if duplicados:
            return Response({'detail': f'codigos repetidos: {", ".join(duplicados)}'}, status=400)

        tipos = list(loan.tipos_prestamo.select_related('tipo_herramienta'))
        if not tipos:
            return Response({'detail': 'El préstamo no tiene tipos de herramienta definidos'}, status=400)
        requeridos = {}
        nombres_tipo = {}
        for t in tipos:
            if t.tipo_herramienta_id is None:
                continue
            requeridos[t.tipo_herramienta_id] = requeridos.get(t.tipo_herramienta_id, 0) + t.cantidad
            nombres_tipo[t.tipo_herramienta_id] = getattr(t.tipo_herramienta, 'nombre', str(t.tipo_herramienta_id))

        with transaction.atomic():
            estados_no_usables = set(herramienta_individual.estados_no_usables())
            herramientas = list(
                herramienta_individual.objects.select_for_update().filter(codigo_barras__in=codigos)
            )
            encontrados = {h.codigo_barras for h in herramientas}
            faltantes = [c for c in codigos if c not in encontrados]
            if faltantes:
                return Response({'detail': f'No se encontraron códigos: {", ".join(faltantes)}'}, status=400)

            no_disponibles = [h.codigo_barras for h in herramientas if not h.disponible]
            if no_disponibles:
                return Response({'detail': f'Herramientas no disponibles: {", ".join(no_disponibles)}'}, status=400)
            no_usables = [
                h.codigo_barras
                for h in herramientas
                if h.estado_herramienta in estados_no_usables
            ]
            if no_usables:
                return Response({'detail': f'Herramientas no usables: {", ".join(no_usables)}'}, status=400)

            conteo_por_tipo = Counter([h.id_tipo_herramienta_id for h in herramientas])
            extras = [tid for tid in conteo_por_tipo if tid not in requeridos]
            if extras:
                extras_nombres = []
                for tid in extras:
                    nombre = nombres_tipo.get(tid)
                    if not nombre:
                        # Busca en las herramientas escaneadas
                        nombre = next(
                            (getattr(h.id_tipo_herramienta, 'nombre', str(tid)) for h in herramientas if h.id_tipo_herramienta_id == tid),
                            str(tid),
                        )
                    extras_nombres.append(str(nombre))
                return Response({'detail': f'Tipos no solicitados: {", ".join(extras_nombres)}'}, status=400)

            faltantes_tipo = []
            sobrantes_tipo = []
            for tid, requerido in requeridos.items():
                obtenido = conteo_por_tipo.get(tid, 0)
                if obtenido < requerido:
                    faltantes_tipo.append(f"{nombres_tipo.get(tid, tid)}: requerido {requerido}, recibido {obtenido}")
                elif obtenido > requerido:
                    sobrantes_tipo.append(f"{nombres_tipo.get(tid, tid)}: requerido {requerido}, recibido {obtenido}")
            if faltantes_tipo or sobrantes_tipo:
                mensajes = []
                if faltantes_tipo:
                    mensajes.append(f"Faltan herramientas: {', '.join(faltantes_tipo)}")
                if sobrantes_tipo:
                    mensajes.append(f"Sobran herramientas: {', '.join(sobrantes_tipo)}")
                return Response({'detail': ' | '.join(mensajes)}, status=400)

            # liberar reserva virtual al pasar a entregado
            try:
                for t in tipos:
                    if t.tipo_herramienta:
                        t.tipo_herramienta.ajustar_reserva(-t.cantidad)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=400)

            actuales = list(loan.herramientas.select_for_update().all())
            for herramienta in actuales:
                disponible_anterior = herramienta.disponible
                herramienta.disponible = (
                    herramienta.estado_herramienta not in estados_no_usables
                )
                if herramienta.disponible != disponible_anterior:
                    herramienta.save(update_fields=['disponible'])
            loan.herramientas.clear()

            for herramienta in herramientas:
                if herramienta.disponible:
                    herramienta.disponible = False
                    herramienta.save(update_fields=['disponible'])
            loan.herramientas.add(*herramientas)

            if prestamo_cambiara_a_entregado:
                herramienta_ids = [herramienta.pk for herramienta in herramientas]
                herramienta_individual.objects.filter(
                    pk__in=herramienta_ids,
                ).update(numero_prestamos=F('numero_prestamos') + 1)
                loan.estado_prestamo = prestamo.EstadoPrestamo.ENTREGADO
                loan.save(update_fields=['estado_prestamo'])

        serializer = self.get_serializer(loan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def devolver_herramientas(self, request, pk=None):
        loan = self.get_object()
        usuario_prestador = request.user if getattr(request.user, 'is_authenticated', False) else None
        codigos = request.data.get('codigos')
        if not isinstance(codigos, list):
            return Response({'detail': 'codigos debe ser una lista'}, status=400)
        codigos = [str(c).strip() for c in codigos if str(c).strip()]
        if not codigos:
            return Response({'detail': 'codigos no puede estar vacío'}, status=400)
        duplicados = [c for c, count in Counter(codigos).items() if count > 1]
        if duplicados:
            return Response({'detail': f'codigos repetidos: {", ".join(duplicados)}'}, status=400)

        estados = request.data.get('estados', {})
        if estados and not isinstance(estados, dict):
            return Response({'detail': 'estados debe ser un objeto {codigo: estado_herramienta}'}, status=400)

        with transaction.atomic():
            estados_no_usables = set(herramienta_individual.estados_no_usables())
            herramientas = list(
                loan.herramientas.select_for_update().filter(codigo_barras__in=codigos)
            )
            encontrados = {h.codigo_barras for h in herramientas}
            faltantes = [c for c in codigos if c not in encontrados]
            if faltantes:
                return Response({'detail': f'Los códigos no pertenecen al préstamo: {", ".join(faltantes)}'}, status=400)

            if len(herramientas) != loan.herramientas.count():
                return Response({'detail': 'Debes devolver todas las herramientas del préstamo'}, status=400)

            now = timezone.now()
            for herramienta in herramientas:
                nuevo_estado = estados.get(herramienta.codigo_barras) if estados else None
                if nuevo_estado:
                    if nuevo_estado not in dict(herramienta_individual.EstadoHerramienta.choices):
                        return Response({'detail': f'Estado inválido para {herramienta.codigo_barras}'}, status=400)
                    herramienta.estado_herramienta = nuevo_estado

                herramienta.disponible = (
                    herramienta.estado_herramienta not in estados_no_usables
                )
                herramienta.save(update_fields=['estado_herramienta', 'disponible'])

                historial_herramienta.objects.create(
                    herramienta=herramienta,
                    estado_herramienta=herramienta.estado_herramienta,
                    prestamo=loan,
                    usuario=usuario_prestador,
                )

            loan.estado_prestamo = prestamo.EstadoPrestamo.FINALIZADO
            loan.fecha_devolucion_real = now
            loan.save(update_fields=['estado_prestamo', 'fecha_devolucion_real'])

        serializer = self.get_serializer(loan)
        return Response(serializer.data)


class AlertasViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertaSerializer

    def get_queryset(self):
        qs = alerta.objects.all()
        action = getattr(self, 'action', None)
        if action == 'no_archivadas':
            qs = qs.filter(archivada=False)
        # Optional: filter only unresolved alerts with ?solo_pendientes=true
        if action in ('list', 'no_archivadas') and self.request.query_params.get('solo_pendientes') == 'true':
            qs = qs.filter(resuelta=False)
        return qs

    @action(detail=False, methods=['get'], url_path='no-archivadas')
    def no_archivadas(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        now = timezone.now()
        estados_alertables = [
            prestamo.EstadoPrestamo.ENTREGADO,
            prestamo.EstadoPrestamo.VENCIDO,
        ]
        vencidos = prestamo.objects.filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
            estado_prestamo__in=estados_alertables,
        )

        for loan in vencidos:
            alert, created = alerta.objects.get_or_create(
                prestamo=loan,
                defaults={'mensaje': 'Prestamo vencido'},
            )
            if alert.resuelta:
                alert.resuelta = False
                alert.resuelta_en = None
                alert.save(update_fields=['resuelta', 'resuelta_en'])

        alerta.objects.filter(
            resuelta=False,
        ).exclude(
            prestamo__fecha_devolucion_real__isnull=True,
            prestamo__fecha_devolucion_esperada__lt=now,
            prestamo__estado_prestamo__in=estados_alertables,
        ).update(resuelta=True, resuelta_en=now)

        return super().list(request, *args, **kwargs)


class ReportesViewSet(viewsets.ViewSet):
    def _get_formato(self, request):
        formato = request.query_params.get('formato', 'json').strip().lower()
        if formato not in {'json', 'pdf', 'excel'}:
            return None, Response(
                {'detail': 'formato debe ser uno de: json, pdf, excel'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return formato, None

    def _fecha_param(self, request, param_name):
        raw = request.query_params.get(param_name)
        if not raw:
            return None, None
        parsed = parse_date(raw)
        if parsed is None:
            return None, Response(
                {'detail': f'{param_name} debe tener formato YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return parsed, None

    def _json_or_file(self, request, title, columns, rows, filename_base, extra=None):
        formato, error_response = self._get_formato(request)
        if error_response is not None:
            return error_response

        payload = {
            'reporte': filename_base,
            'columnas': columns,
            'total': len(rows),
            'resultados': rows,
        }
        if extra:
            payload.update(extra)

        if formato == 'json':
            return Response(payload, status=status.HTTP_200_OK)
        if formato == 'pdf':
            return self._build_pdf_response(title, columns, rows, filename_base)
        return self._build_excel_response(title, columns, rows, filename_base)

    def _build_pdf_response(self, title, columns, rows, filename_base):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph(title, styles['Title']),
            Spacer(1, 6 * mm),
        ]
        headers = [Paragraph(str(column), styles['Heading5']) for column in columns]
        table_rows = [headers]
        for row in rows:
            table_rows.append([Paragraph(str(row.get(column, '')), styles['BodyText']) for column in columns])

        if len(columns) <= 3:
            col_width = 85 * mm
        elif len(columns) <= 5:
            col_width = 55 * mm
        else:
            col_width = 38 * mm
        table = Table(table_rows, colWidths=[col_width] * len(columns), repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'
        return response

    def _build_excel_response(self, title, columns, rows, filename_base):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError:
            return Response(
                {'detail': 'Falta la dependencia openpyxl para generar reportes Excel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = title[:31]
        sheet.append(columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([row.get(column, '') for column in columns])
        for column_cells in sheet.columns:
            length = max(len(str(cell.value or '')) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)

        buffer = BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
        return response

    @action(detail=False, methods=['get'])
    def inventario(self, request):
        tipos = tipo_herramienta.objects.order_by('nombre')
        estados_no_usables = herramienta_individual.estados_no_usables()
        rows = []
        for tipo in tipos:
            total = herramienta_individual.objects.filter(id_tipo_herramienta=tipo).count()
            disponibles = herramienta_individual.objects.filter(
                id_tipo_herramienta=tipo,
                disponible=True,
            ).exclude(
                estado_herramienta__in=estados_no_usables,
            ).count()
            rows.append(
                {
                    'id_tipo_herramienta': tipo.id_tipo_herramienta,
                    'nombre': tipo.nombre,
                    'categoria': getattr(tipo.id_categoria, 'nombre', ''),
                    'total_herramientas': total,
                    'herramientas_disponibles': disponibles,
                    'reservado': tipo.reservado,
                    'stock': tipo.stock,
                }
            )
        columns = [
            'id_tipo_herramienta',
            'nombre',
            'categoria',
            'total_herramientas',
            'herramientas_disponibles',
            'reservado',
            'stock',
        ]
        return self._json_or_file(
            request,
            'Reporte de Inventario',
            columns,
            rows,
            'reporte_inventario',
        )

    @action(detail=False, methods=['get'])
    def prestamos(self, request):
        fecha_desde, error_response = self._fecha_param(request, 'fecha_desde')
        if error_response is not None:
            return error_response
        fecha_hasta, error_response = self._fecha_param(request, 'fecha_hasta')
        if error_response is not None:
            return error_response
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            return Response(
                {'detail': 'fecha_desde no puede ser mayor que fecha_hasta'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = prestamo.objects.select_related(
            'id_usuario',
            'id_usuario__id_rol',
        ).order_by('-fecha_prestamo')
        if fecha_desde:
            queryset = queryset.filter(fecha_prestamo__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_prestamo__date__lte=fecha_hasta)

        rows = []
        for loan in queryset:
            rows.append(
                {
                    'id_prestamo': loan.id_prestamo,
                    'codigo': loan.codigo or '',
                    'usuario_id': loan.id_usuario_id,
                    'usuario': f'{loan.id_usuario.nombres} {loan.id_usuario.apellidos}'.strip(),
                    'correo': loan.id_usuario.correo,
                    'estado_prestamo': loan.estado_prestamo,
                    'fecha_prestamo': timezone.localtime(loan.fecha_prestamo).isoformat() if loan.fecha_prestamo else '',
                    'fecha_devolucion_esperada': timezone.localtime(loan.fecha_devolucion_esperada).isoformat() if loan.fecha_devolucion_esperada else '',
                    'fecha_devolucion_real': timezone.localtime(loan.fecha_devolucion_real).isoformat() if loan.fecha_devolucion_real else '',
                }
            )
        columns = [
            'id_prestamo',
            'codigo',
            'usuario_id',
            'usuario',
            'correo',
            'estado_prestamo',
            'fecha_prestamo',
            'fecha_devolucion_esperada',
            'fecha_devolucion_real',
        ]
        extra = {
            'filtros': {
                'fecha_desde': fecha_desde.isoformat() if fecha_desde else None,
                'fecha_hasta': fecha_hasta.isoformat() if fecha_hasta else None,
            }
        }
        return self._json_or_file(
            request,
            'Reporte de Prestamos',
            columns,
            rows,
            'reporte_prestamos',
            extra=extra,
        )

    @action(detail=False, methods=['get'])
    def morosos(self, request):
        now = timezone.now()
        queryset = prestamo.objects.select_related(
            'id_usuario',
            'id_usuario__id_rol',
            'id_usuario__id_carrera',
        ).filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
        ).order_by('fecha_devolucion_esperada')

        rows = []
        for loan in queryset:
            rows.append(
                {
                    'id_prestamo': loan.id_prestamo,
                    'codigo': loan.codigo or '',
                    'usuario_id': loan.id_usuario_id,
                    'usuario': f'{loan.id_usuario.nombres} {loan.id_usuario.apellidos}'.strip(),
                    'correo': loan.id_usuario.correo,
                    'rol': loan.id_usuario.id_rol.nombre if loan.id_usuario.id_rol else '',
                    'carrera': getattr(loan.id_usuario.id_carrera, 'nombre', ''),
                    'esta_baneado': loan.id_usuario.esta_baneado,
                    'estado_prestamo': loan.estado_prestamo,
                    'fecha_devolucion_esperada': timezone.localtime(loan.fecha_devolucion_esperada).isoformat(),
                    'dias_atraso': max((now - loan.fecha_devolucion_esperada).days, 0),
                }
            )
        columns = [
            'id_prestamo',
            'codigo',
            'usuario_id',
            'usuario',
            'correo',
            'rol',
            'carrera',
            'esta_baneado',
            'estado_prestamo',
            'fecha_devolucion_esperada',
            'dias_atraso',
        ]
        return self._json_or_file(
            request,
            'Reporte de Usuarios Morosos',
            columns,
            rows,
            'reporte_morosos',
        )
