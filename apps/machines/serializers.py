from rest_framework import serializers

from .models import Machine, MachineStatus, MachineType, Parameter


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = (
            "id", "code", "name", "type", "status",
            "nominal_bph", "nominal_cph", "cavities",
            "product_format", "location", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


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
