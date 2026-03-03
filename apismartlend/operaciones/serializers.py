from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from inventario.models import herramienta_individual, tipo_herramienta
from inventario.serializers import HerramientaIndividualSerializer

from .models import (
    alerta,
    prestamo,
    PrestamoTipoHerramienta,
)
from .tasks import expirar_prestamo_pendiente

class PrestamoSerializer(serializers.ModelSerializer):
    fecha_prestamo = serializers.DateTimeField(required=False)
    fecha_devolucion_esperada = serializers.DateTimeField(required=False)
    fecha_inicio_reserva = serializers.DateTimeField(write_only=True, required=False)
    esta_vencido = serializers.SerializerMethodField()
    # JSONField renders as a textarea in the browsable API, easier to test.
    tipos = serializers.JSONField(write_only=True, required=False)
    tipos_detalle = serializers.SerializerMethodField()
    herramientas = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    herramientas_detalle = HerramientaIndividualSerializer(source='herramientas', many=True, read_only=True)

    class Meta:
        model = prestamo
        fields = [
            'id_prestamo',
            'fecha_prestamo',
            'fecha_devolucion_esperada',
            'fecha_inicio_reserva',
            'fecha_devolucion_real',
            'estado_prestamo',
            'estado_devolucion',
            'observaciones',
            'codigo',
            'id_usuario',
            'herramientas',
            'herramientas_detalle',
            'tipos',
            'tipos_detalle',
            'esta_vencido',
        ]

    @staticmethod
    def _is_docente(usuario):
        return bool(
            usuario
            and getattr(usuario, 'id_rol', None)
            and getattr(usuario.id_rol, 'nombre', '').strip().lower() == 'docente'
        )

    def _validate_item_limit(self, usuario, tipos_list):
        if self._is_docente(usuario):
            return

        max_items = getattr(settings, 'SMARTLEND_MAX_ITEMS_PER_LOAN', None)
        if max_items in (None, ''):
            return

        total_items = sum(entry['cantidad'] for entry in tipos_list)
        if total_items > int(max_items):
            raise serializers.ValidationError(
                {'tipos': f'No puedes solicitar más de {max_items} ítems por préstamo'}
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        require_reserva_docente = self.context.get('require_reserva_docente', False)

        if self.instance is not None:
            return attrs

        usuario = attrs.get('id_usuario')
        fecha_prestamo = attrs.get('fecha_prestamo')
        fecha_inicio_reserva = attrs.get('fecha_inicio_reserva')
        fecha_devolucion_esperada = attrs.get('fecha_devolucion_esperada')
        today = timezone.localdate()

        if require_reserva_docente and not self._is_docente(usuario):
            raise serializers.ValidationError(
                {'id_usuario': 'El endpoint de reserva docente solo acepta usuarios con rol Docente'}
            )
        if require_reserva_docente and fecha_inicio_reserva is None:
            raise serializers.ValidationError(
                {'fecha_inicio_reserva': 'Este campo es obligatorio para crear una reserva docente'}
            )

        if fecha_inicio_reserva is not None:
            if not self._is_docente(usuario):
                raise serializers.ValidationError(
                    {'fecha_inicio_reserva': 'Solo los usuarios con rol Docente pueden reservar para mañana'}
                )

            if timezone.localdate(fecha_inicio_reserva) != today + timedelta(days=1):
                raise serializers.ValidationError(
                    {'fecha_inicio_reserva': 'La fecha de inicio de reserva debe corresponder al día de mañana'}
                )

            attrs['fecha_prestamo'] = fecha_inicio_reserva
            fecha_prestamo = fecha_inicio_reserva
            if fecha_devolucion_esperada is None:
                attrs['fecha_devolucion_esperada'] = fecha_inicio_reserva + timedelta(days=1)
                fecha_devolucion_esperada = attrs['fecha_devolucion_esperada']
        elif fecha_prestamo is not None and timezone.localdate(fecha_prestamo) > today:
            if not self._is_docente(usuario):
                raise serializers.ValidationError(
                    {'fecha_prestamo': 'Solo los usuarios con rol Docente pueden crear préstamos con inicio futuro'}
                )
            if timezone.localdate(fecha_prestamo) != today + timedelta(days=1):
                raise serializers.ValidationError(
                    {'fecha_prestamo': 'Los préstamos futuros solo se permiten para el día de mañana'}
                )

        if fecha_prestamo is None:
            raise serializers.ValidationError({'fecha_prestamo': 'Este campo es obligatorio'})
        if fecha_devolucion_esperada is None:
            raise serializers.ValidationError({'fecha_devolucion_esperada': 'Este campo es obligatorio'})
        if fecha_devolucion_esperada <= fecha_prestamo:
            raise serializers.ValidationError(
                {'fecha_devolucion_esperada': 'Debe ser posterior a la fecha de inicio del préstamo'}
            )

        return attrs

    def get_esta_vencido(self, obj):
        return (
            obj.fecha_devolucion_real is None
            and obj.fecha_devolucion_esperada
            and obj.fecha_devolucion_esperada < timezone.now()
        )

    def get_tipos_detalle(self, obj):
        tipos = obj.tipos_prestamo.select_related('tipo_herramienta').all()
        return [
            {
                'tipo_herramienta': t.tipo_herramienta_id,
                'tipo_herramienta_nombre': t.tipo_herramienta.nombre if t.tipo_herramienta else None,
                'cantidad': t.cantidad,
            }
            for t in tipos
        ]

    def _validated_tipos(self, raw_list):
        if raw_list is None:
            return []
        if not isinstance(raw_list, list):
            raise serializers.ValidationError({'tipos': 'Debe ser una lista de objetos tipo/cantidad'})
        cleaned = []
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                raise serializers.ValidationError({'tipos': f'Elemento #{idx+1} debe ser un objeto con tipo_herramienta y cantidad'})
            tipo_id = item.get('tipo_herramienta') or item.get('id_tipo_herramienta')
            cantidad = item.get('cantidad', 1)
            try:
                cantidad = int(cantidad)
            except (TypeError, ValueError):
                raise serializers.ValidationError({'tipos': f'Cantidad inválida en elemento #{idx+1}'})
            if cantidad <= 0:
                raise serializers.ValidationError({'tipos': f'Cantidad debe ser > 0 en elemento #{idx+1}'})
            try:
                tipo_obj = tipo_herramienta.objects.get(pk=tipo_id)
            except (tipo_herramienta.DoesNotExist, ValueError, TypeError):
                raise serializers.ValidationError({'tipos': f'tipo_herramienta inválido en elemento #{idx+1}'})
            cleaned.append({'tipo': tipo_obj, 'cantidad': cantidad})
        return cleaned

    def _ensure_stock(self, tipos_list):
        shortages = []
        for entry in tipos_list:
            tipo_obj = entry['tipo']
            required = entry['cantidad']
            disponibles = herramienta_individual.objects.filter(
                id_tipo_herramienta=tipo_obj,
                disponible=True,
            ).count()
            reservado = getattr(tipo_obj, 'reservado', 0) or 0
            libres = max(disponibles - reservado, 0)
            if libres < required:
                nombre = getattr(tipo_obj, 'nombre', str(tipo_obj.pk))
                shortages.append(f'{nombre}: disponibles {libres}, requeridos {required}')
        if shortages:
            raise serializers.ValidationError({'tipos': f'Sin stock suficiente ({"; ".join(shortages)})'})

    def _ajustar_reserva(self, tipos_list, signo):
        # tipos_list: list of {'tipo': tipo_obj, 'cantidad': int}
        for entry in tipos_list:
            tipo_obj = entry['tipo']
            delta = signo * entry['cantidad']
            try:
                tipo_obj.ajustar_reserva(delta)
            except ValueError as exc:
                raise serializers.ValidationError({'tipos': str(exc)}) from exc

    def _reemplazar_tipos(self, loan, tipos_list):
        loan.tipos_prestamo.all().delete()
        for entry in tipos_list:
            PrestamoTipoHerramienta.objects.create(
                prestamo=loan,
                tipo_herramienta=entry['tipo'],
                cantidad=entry['cantidad'],
            )

### Sirve para crear y actualizar préstamos con lógica de asignación de herramientas
    def create(self, validated_data):
        tipos_raw = validated_data.pop('tipos', [])
        validated_data.pop('fecha_inicio_reserva', None)
        tipos_list = self._validated_tipos(tipos_raw)
        if not tipos_list:
            raise serializers.ValidationError({'tipos': 'Debes indicar al menos un tipo_herramienta con cantidad'})
        self._validate_item_limit(validated_data.get('id_usuario'), tipos_list)
        with transaction.atomic():
            self._ensure_stock(tipos_list)
            loan = super().create(validated_data)
            if tipos_list:
                self._reemplazar_tipos(loan, tipos_list)
                self._ajustar_reserva(tipos_list, signo=1)
            # Programa expiración en 30 minutos si sigue pendiente
            now = timezone.now()
            segundos_hasta_inicio = max(int((loan.fecha_prestamo - now).total_seconds()), 0)
            countdown = segundos_hasta_inicio + (30 * 60)
            transaction.on_commit(
                lambda: expirar_prestamo_pendiente.apply_async(args=[loan.id_prestamo], countdown=countdown)
            )
            # Enviar correo con detalle de tipos
            transaction.on_commit(lambda: loan.enviar_correo_codigo(tipos_list))
        return loan

### Sirve para actualizar préstamos con lógica de reasignación de herramientas
    def update(self, instance, validated_data):
        tipos_raw = validated_data.pop('tipos', None)
        validated_data.pop('fecha_inicio_reserva', None)
        previous_estado = instance.estado_prestamo
        with transaction.atomic():
            loan = super().update(instance, validated_data)
            if tipos_raw is not None:
                tipos_list = self._validated_tipos(tipos_raw)
                self._validate_item_limit(loan.id_usuario, tipos_list)
                if loan.herramientas.exists():
                    raise serializers.ValidationError({'tipos': 'No puedes modificar tipos cuando ya hay herramientas asignadas'})
                # liberar reserva previa
                prev_tipos = [
                    {'tipo': tp.tipo_herramienta, 'cantidad': tp.cantidad}
                    for tp in loan.tipos_prestamo.select_related('tipo_herramienta')
                ]
                self._ajustar_reserva(prev_tipos, signo=-1)

                self._ensure_stock(tipos_list)
                loan.tipos_prestamo.all().delete()
                if tipos_list:
                    self._reemplazar_tipos(loan, tipos_list)
                    self._ajustar_reserva(tipos_list, signo=1)

            if (
                previous_estado != prestamo.EstadoPrestamo.FINALIZADO
                and loan.estado_prestamo == prestamo.EstadoPrestamo.FINALIZADO
            ):
                for herramienta in loan.herramientas.all():
                    if not herramienta.disponible:
                        herramienta.disponible = True
                        herramienta.save(update_fields=['disponible'])
        return loan


class PrestamoTurnoPublicoSerializer(serializers.ModelSerializer):
    codigo_publico = serializers.SerializerMethodField()

    class Meta:
        model = prestamo
        fields = [
            'codigo_publico',
            'estado_prestamo',
        ]

    def get_codigo_publico(self, obj):
        codigo = (obj.codigo or '').strip()
        if not codigo:
            return ''
        if len(codigo) <= 6:
            return codigo
        return f'{codigo[:6]}...'


class PrestamoTurnoGestionSerializer(PrestamoTurnoPublicoSerializer):
    class Meta(PrestamoTurnoPublicoSerializer.Meta):
        fields = [
            'id_prestamo',
            'codigo_publico',
            'estado_prestamo',
            'estado_turno_pantalla',
            'fecha_prestamo',
            'turno_mostrado_en',
            'turno_veces_mostrado',
        ]


class AlertaSerializer(serializers.ModelSerializer):
    prestamo_detalle = PrestamoSerializer(source='prestamo', read_only=True)

    class Meta:
        model = alerta
        fields = [
            'id_alerta',
            'prestamo',
            'prestamo_detalle',
            'mensaje',
            'criticidad',
            'creada_en',
            'resuelta',
            'resuelta_en',
            'archivada',
        ]
        read_only_fields = [
            'id_alerta',
            'prestamo',
            'prestamo_detalle',
            'mensaje',
            'criticidad',
            'creada_en',
            'resuelta',
            'resuelta_en',
        ]
