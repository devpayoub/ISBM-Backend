from rest_framework import serializers

from .models import (
    AuxiliaryEquipment, Machine, MachineComponent, MachineParameter,
    MachineStatus, MachineType, Mold, Parameter,
)


class MachineSerializer(serializers.ModelSerializer):
    andon_status = serializers.SerializerMethodField()
    equipment_status = serializers.SerializerMethodField()
    component_count = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = (
            "id", "code", "name", "type", "status", "andon_status",
            "equipment_status", "component_count",
            "nominal_bph", "nominal_cph", "cavities",
            "product_format", "location", "serial_number", "manufacturer", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_andon_status(self, obj):
        return obj.get_andon_status()

    def get_equipment_status(self, obj):
        return obj.get_equipment_status()

    def get_component_count(self, obj):
        return obj.components.filter(is_active=True).count()


class MachineStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MachineStatus.choices)


class MachineComponentSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)
    status = serializers.CharField(read_only=True)
    parameter_count = serializers.SerializerMethodField()

    class Meta:
        model = MachineComponent
        fields = (
            "id", "machine", "machine_code", "name", "reference", "is_active",
            "status", "parameter_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_parameter_count(self, obj):
        return obj.parameters.count()


class MachineParameterSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True, default="")
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")
    component_name = serializers.CharField(source="component.name", read_only=True, default="")

    class Meta:
        model = MachineParameter
        fields = (
            "id", "machine", "machine_code", "component", "component_name",
            "name", "unit", "display", "current_value", "target_value",
            "warning_tolerance_pct", "status", "order",
            "updated_by", "updated_by_name", "updated_at",
        )
        read_only_fields = ("id", "status", "updated_by", "updated_by_name", "updated_at")


class AuxiliaryEquipmentSerializer(serializers.ModelSerializer):
    machines_detail = serializers.SerializerMethodField()

    class Meta:
        model = AuxiliaryEquipment
        fields = ("id", "name", "reference", "machines", "machines_detail", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_machines_detail(self, obj):
        return [{"id": m.id, "code": m.code, "name": m.name} for m in obj.machines.all()]


class MoldSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)

    class Meta:
        model = Mold
        fields = ("id", "machine", "machine_code", "name", "reference", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = (
            "id", "key", "label", "value", "text_value", "unit",
            "effective_from", "is_active", "category",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "key")
