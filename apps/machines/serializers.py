from rest_framework import serializers

from .models import Machine, MachineStatus, MachineType, Parameter


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


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = (
            "id", "key", "label", "value", "unit",
            "effective_from", "is_active", "category",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "key")
