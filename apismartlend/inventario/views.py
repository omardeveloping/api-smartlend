from io import BytesIO

from django.http import HttpResponse
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Sum,
    When,
)
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from operaciones.models import prestamo
from usuarios.permissions import EsActorSistema, EsBodeguero

from .models import (
    categoria_herramienta,
    tipo_herramienta,
    herramienta_individual,
    historial_herramienta,
)
from .serializers import (
    CategoriaHerramientaSerializer,
    TipoHerramientaSerializer,
    HerramientaIndividualSerializer,
    HistorialHerramientaSerializer,
)


def _annotate_with_prestamo_estado(queryset):
    """
    Marca cada herramienta con un flag booleano si está asociada a un préstamo
    que sigue abierto (sin fecha de devolución y no cancelado/finalizado).
    """
    prestamos_activos = _prestamos_activos_queryset()
    return queryset.annotate(
        esta_en_prestamo_activo=Exists(
            prestamos_activos.filter(
                Q(herramientas__pk=OuterRef('pk'))
                | Q(id_herramienta_individual_id=OuterRef('pk'))
            )
        )
    )


def _prestamos_activos_queryset():
    return prestamo.objects.filter(
        fecha_devolucion_real__isnull=True,
    ).exclude(
        estado_prestamo__in=[
            prestamo.EstadoPrestamo.FINALIZADO,
            prestamo.EstadoPrestamo.CANCELADO,
        ]
    )


class TipoHerramientaViewSet(viewsets.ModelViewSet):
    queryset = tipo_herramienta.objects.all()
    serializer_class = TipoHerramientaSerializer
    permission_classes = [EsActorSistema]

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy'}:
            return [EsBodeguero()]
        return super().get_permissions()

    @action(detail=False, methods=['get'], url_path='resumen')
    def resumen_herramientas(self, request):
        herramientas_annotated = _annotate_with_prestamo_estado(
            herramienta_individual.objects.all()
        )
        resumen = (
            herramientas_annotated.values('id_tipo_herramienta')
            .annotate(
                total_herramientas=Count('id_herramienta', distinct=True),
                herramientas_disponibles=Sum(
                    Case(
                        When(
                            esta_en_prestamo_activo=False,
                            disponible=True,
                            estado_herramienta__in=herramienta_individual.estados_usables(),
                            then=1,
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
        )
        totales_por_tipo = {
            item['id_tipo_herramienta']: {
                'total_herramientas': item.get('total_herramientas') or 0,
                'herramientas_disponibles': item.get('herramientas_disponibles') or 0,
            }
            for item in resumen
        }

        data = []
        for tipo in self.get_queryset().order_by('nombre'):
            cantidades = totales_por_tipo.get(tipo.id_tipo_herramienta, {})
            data.append(
                {
                    'id_tipo_herramienta': tipo.id_tipo_herramienta,
                    'nombre': tipo.nombre,
                    'descripcion': tipo.descripcion,
                    'imagen': tipo.imagen.url if tipo.imagen else None,
                    'total_herramientas': cantidades.get('total_herramientas', 0),
                    'herramientas_disponibles': cantidades.get('herramientas_disponibles', 0),
                }
            )
        return Response(data)


class CategoriaHerramientaViewSet(viewsets.ModelViewSet):
    queryset = categoria_herramienta.objects.all()
    serializer_class = CategoriaHerramientaSerializer
    permission_classes = [EsActorSistema]

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy'}:
            return [EsBodeguero()]
        return super().get_permissions()


class HerramientaIndividualViewSet(viewsets.ModelViewSet):
    serializer_class = HerramientaIndividualSerializer
    queryset = herramienta_individual.objects.all()
    permission_classes = [EsActorSistema]

    def get_permissions(self):
        if self.action in {
            'create',
            'update',
            'partial_update',
            'destroy',
            'no_usables',
            'marcar_usable',
            'top5_usadas_mes_excel',
        }:
            return [EsBodeguero()]
        return super().get_permissions()

    def _base_queryset(self):
        qs = _annotate_with_prestamo_estado(super().get_queryset())
        tipo_id = self.request.query_params.get('id_tipo_herramienta')
        if tipo_id:
            try:
                qs = qs.filter(id_tipo_herramienta_id=int(tipo_id))
            except ValueError:
                pass
        return qs

    def get_queryset(self):
        qs = self._base_queryset()
        if self.request.query_params.get('solo_disponibles') == 'true':
            qs = qs.filter(
                esta_en_prestamo_activo=False,
                disponible=True,
                estado_herramienta__in=herramienta_individual.estados_usables(),
            )
        return qs

    @action(detail=False, methods=['get'], url_path='no-usables')
    def no_usables(self, request):
        qs = self._base_queryset().filter(
            estado_herramienta__in=herramienta_individual.estados_no_usables()
        )
        estado = (request.query_params.get('estado_herramienta') or '').strip()
        if estado:
            if estado not in herramienta_individual.estados_no_usables():
                return Response(
                    {'detail': 'estado_herramienta debe ser Defectuoso o Dañado'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(estado_herramienta=estado)

        serializer = self.get_serializer(qs.order_by('id_herramienta'), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marcar-usable')
    def marcar_usable(self, request, pk=None):
        herramienta = self.get_object()
        estado = request.data.get(
            'estado_herramienta',
            herramienta_individual.EstadoHerramienta.BUENO,
        )
        estados_usables = herramienta_individual.estados_usables()
        if estado not in estados_usables:
            return Response(
                {
                    'detail': (
                        f'estado_herramienta debe ser usable: '
                        f'{", ".join(estados_usables)}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tiene_prestamo_activo = _prestamos_activos_queryset().filter(
            Q(herramientas__pk=herramienta.pk)
            | Q(id_herramienta_individual_id=herramienta.pk)
        ).exists()
        if tiene_prestamo_activo:
            return Response(
                {'detail': 'No se puede marcar usable mientras exista un préstamo activo asociado'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        herramienta.estado_herramienta = estado
        herramienta.disponible = True
        herramienta.save(update_fields=['estado_herramienta', 'disponible'])
        return Response(self.get_serializer(herramienta).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='top5-usadas-mes-excel')
    def top5_usadas_mes_excel(self, request):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError:
            return Response(
                {'detail': 'Falta la dependencia openpyxl para generar reportes Excel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        fecha_actual = timezone.localdate()
        inicio_mes = fecha_actual.replace(day=1)
        if inicio_mes.month == 12:
            inicio_mes_siguiente = inicio_mes.replace(
                year=inicio_mes.year + 1,
                month=1,
            )
        else:
            inicio_mes_siguiente = inicio_mes.replace(month=inicio_mes.month + 1)

        estados_contables = [
            prestamo.EstadoPrestamo.ENTREGADO,
            prestamo.EstadoPrestamo.FINALIZADO,
            prestamo.EstadoPrestamo.VENCIDO,
        ]
        top_herramientas = (
            herramienta_individual.objects.select_related('id_tipo_herramienta')
            .annotate(
                usos_mes=Count(
                    'prestamos_asociados',
                    filter=Q(
                        prestamos_asociados__fecha_prestamo__date__gte=inicio_mes,
                        prestamos_asociados__fecha_prestamo__date__lt=inicio_mes_siguiente,
                        prestamos_asociados__estado_prestamo__in=estados_contables,
                    ),
                    distinct=True,
                )
            )
            .filter(usos_mes__gt=0)
            .order_by('-usos_mes', '-numero_prestamos', 'codigo_barras')[:5]
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Top5 mensual'
        columns = [
            'posicion',
            'id_herramienta',
            'codigo_barras',
            'tipo_herramienta',
            'marca',
            'modelo',
            'usos_mes',
            'numero_prestamos',
        ]
        sheet.append(columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for index, herramienta in enumerate(top_herramientas, start=1):
            sheet.append(
                [
                    index,
                    herramienta.id_herramienta,
                    herramienta.codigo_barras,
                    getattr(herramienta.id_tipo_herramienta, 'nombre', ''),
                    herramienta.marca,
                    herramienta.modelo,
                    herramienta.usos_mes,
                    herramienta.numero_prestamos,
                ]
            )

        for column_cells in sheet.columns:
            length = max(len(str(cell.value or '')) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)

        buffer = BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="top5_herramientas_{inicio_mes:%Y_%m}.xlsx"'
        )
        return response


class HistorialHerramientaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HistorialHerramientaSerializer
    permission_classes = [EsBodeguero]
    queryset = historial_herramienta.objects.select_related(
        'herramienta',
        'herramienta__id_tipo_herramienta',
        'prestamo',
        'prestamo__id_usuario',
        'usuario',
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        herramienta_id = (
            self.request.query_params.get('herramienta')
            or self.request.query_params.get('id_herramienta')
        )
        codigo_barras = (self.request.query_params.get('codigo_barras') or '').strip()
        prestamo_id = self.request.query_params.get('prestamo')
        if herramienta_id:
            qs = qs.filter(herramienta_id=herramienta_id)
        if codigo_barras:
            qs = qs.filter(herramienta__codigo_barras__iexact=codigo_barras)
        if prestamo_id:
            qs = qs.filter(prestamo_id=prestamo_id)
        return qs.order_by('-registrada_en')

    @action(detail=False, methods=['get'], url_path='exportar-excel')
    def exportar_excel(self, request):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError:
            return Response(
                {'detail': 'Falta la dependencia openpyxl para generar reportes Excel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = self.get_queryset()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Trazabilidad'
        columns = [
            'id_historial',
            'codigo_barras',
            'tipo_herramienta',
            'estado_herramienta',
            'registrada_en',
            'prestamo_id',
            'prestamo_codigo',
            'usuario_prestador_nombre',
            'usuario_prestador_rut',
            'usuario_receptor_nombre',
            'usuario_receptor_rut',
        ]
        sheet.append(columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for item in queryset:
            herramienta = item.herramienta
            tipo = getattr(herramienta.id_tipo_herramienta, 'nombre', '')
            prestamo_obj = item.prestamo
            usuario_prestador = item.usuario
            usuario_receptor = getattr(prestamo_obj, 'id_usuario', None)
            prestador_nombre = ''
            prestador_rut = ''
            receptor_nombre = ''
            receptor_rut = ''
            if usuario_prestador:
                prestador_nombre = f'{usuario_prestador.nombres} {usuario_prestador.apellidos}'.strip()
                prestador_rut = usuario_prestador.rut
            if usuario_receptor:
                receptor_nombre = f'{usuario_receptor.nombres} {usuario_receptor.apellidos}'.strip()
                receptor_rut = usuario_receptor.rut

            sheet.append(
                [
                    item.id_historial,
                    herramienta.codigo_barras,
                    tipo,
                    item.estado_herramienta,
                    item.registrada_en.isoformat() if item.registrada_en else '',
                    item.prestamo_id,
                    getattr(prestamo_obj, 'codigo', ''),
                    prestador_nombre,
                    prestador_rut,
                    receptor_nombre,
                    receptor_rut,
                ]
            )

        for column_cells in sheet.columns:
            length = max(len(str(cell.value or '')) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)

        buffer = BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="trazabilidad_herramientas.xlsx"'
        return response
