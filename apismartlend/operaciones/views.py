from collections import Counter

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from inventario.models import herramienta_individual, historial_herramienta, tipo_herramienta

from .models import (
    alerta,
    prestamo,
    reserva,
)
from .serializers import (
    AlertaSerializer,
    PrestamoSerializer,
    ReservaSerializer,
)


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = reserva.objects.all().prefetch_related(
        'herramientas',
        'herramientas__id_tipo_herramienta',
    )
    serializer_class = ReservaSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        return ctx


class PrestamoViewSet(viewsets.ModelViewSet):
    queryset = prestamo.objects.all().prefetch_related(
        'herramientas',
        'herramientas__id_tipo_herramienta',
        'tipos_prestamo__tipo_herramienta',
    )
    serializer_class = PrestamoSerializer

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
                if not herramienta.disponible:
                    herramienta.disponible = True
                    herramienta.save(update_fields=['disponible'])
            loan.herramientas.clear()

            for herramienta in herramientas:
                if herramienta.disponible:
                    herramienta.disponible = False
                    herramienta.save(update_fields=['disponible'])
            loan.herramientas.add(*herramientas)

            if loan.estado_prestamo == prestamo.EstadoPrestamo.PENDIENTE:
                loan.estado_prestamo = prestamo.EstadoPrestamo.ENTREGADO
                loan.save(update_fields=['estado_prestamo'])

        serializer = self.get_serializer(loan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def devolver_herramientas(self, request, pk=None):
        loan = self.get_object()
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

                if not herramienta.disponible:
                    herramienta.disponible = True
                herramienta.save(update_fields=['estado_herramienta', 'disponible'])

                historial_herramienta.objects.create(
                    herramienta=herramienta,
                    estado_herramienta=herramienta.estado_herramienta,
                    prestamo=loan,
                    usuario=loan.id_usuario,
                )

            loan.estado_prestamo = prestamo.EstadoPrestamo.FINALIZADO
            loan.fecha_devolucion_real = now
            loan.save(update_fields=['estado_prestamo', 'fecha_devolucion_real'])

        serializer = self.get_serializer(loan)
        return Response(serializer.data)


class AlertasViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertaSerializer

    def get_queryset(self):
        qs = alerta.objects.all()
        if getattr(self, 'action', None) == 'no_archivadas':
            qs = qs.filter(archivada=False)
        # Optional: filter only unresolved alerts with ?solo_pendientes=true
        if self.request.query_params.get('solo_pendientes') == 'true':
            qs = qs.filter(resuelta=False)
        return qs

    @action(detail=False, methods=['get'], url_path='no-archivadas')
    def no_archivadas(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        now = timezone.now()
        vencidos = prestamo.objects.filter(
            fecha_devolucion_real__isnull=True,
            fecha_devolucion_esperada__lt=now,
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
        ).update(resuelta=True, resuelta_en=now)

        return super().list(request, *args, **kwargs)
