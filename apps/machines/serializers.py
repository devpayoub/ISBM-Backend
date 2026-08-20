from rest_framework import serializers

from .models import (
    AuxiliaryEquipment, Machine, MachineComponent, MachineStatus,
    MachineType, Mold, Parameter,
)


class MachineSerializer(serializers.ModelSerializer):
    andon_status = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = (
            "id", "code", "name", "type", "status", "andon_status",
            "nominal_bph", "nominal_cph", "cavities",
            "product_format", "location", "serial_number", "manufacturer", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_andon_status(self, obj):
        return obj.get_andon_status()


class MachineStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MachineStatus.choices)


class MachineComponentSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)

    class Meta:
        model = MachineComponent
        fields = ("id", "machine", "machine_code", "name", "reference", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


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
