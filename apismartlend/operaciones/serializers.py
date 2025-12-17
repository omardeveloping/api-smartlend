from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from inventario.models import herramienta_individual, tipo_herramienta
from inventario.serializers import HerramientaIndividualSerializer

from .models import (
    alerta,
    prestamo,
    PrestamoTipoHerramienta,
    reserva,
)
from .tasks import expirar_prestamo_pendiente

### Reserva todavía no está listo, no tiene ninguna logica especial más allá del CRUD básico.
class ReservaSerializer(serializers.ModelSerializer):
    herramientas = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    herramientas_detalle = HerramientaIndividualSerializer(source='herramientas', many=True, read_only=True)

    class Meta:
        model = reserva
        fields = [
            'id_reserva',
            'fecha_reserva',
            'fecha_inicio_reserva',
            'fecha_fin_reserva',
            'estado_reserva',
            'id_usuario',
            'id_tipo_herramienta',
            'herramientas',
            'herramientas_detalle',
        ]


class PrestamoSerializer(serializers.ModelSerializer):
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
        tipos_list = self._validated_tipos(tipos_raw)
        if not tipos_list:
            raise serializers.ValidationError({'tipos': 'Debes indicar al menos un tipo_herramienta con cantidad'})
        with transaction.atomic():
            self._ensure_stock(tipos_list)
            loan = super().create(validated_data)
            if tipos_list:
                self._reemplazar_tipos(loan, tipos_list)
                self._ajustar_reserva(tipos_list, signo=1)
            # Programa expiración en 30 minutos si sigue pendiente
            transaction.on_commit(lambda: expirar_prestamo_pendiente.apply_async(args=[loan.id_prestamo], countdown=30 * 60))
            # Enviar correo con detalle de tipos
            transaction.on_commit(lambda: loan.enviar_correo_codigo(tipos_list))
        return loan

### Sirve para actualizar préstamos con lógica de reasignación de herramientas
    def update(self, instance, validated_data):
        tipos_raw = validated_data.pop('tipos', None)
        previous_estado = instance.estado_prestamo
        with transaction.atomic():
            loan = super().update(instance, validated_data)
            if tipos_raw is not None:
                tipos_list = self._validated_tipos(tipos_raw)
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
