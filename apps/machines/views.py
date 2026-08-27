import logging

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity
from apps.common.channels_utils import broadcast_to_alerts_group
from apps.common.permissions import IsAdminOrManagerOrReadOnly

from .models import (
    AuxiliaryEquipment, Machine, MachineComponent, MachineParameter,
    MachineStatus, Mold, Parameter,
)
from .serializers import (
    AuxiliaryEquipmentSerializer, MachineComponentSerializer, MachineParameterSerializer,
    MachineSerializer, MachineStatusSerializer, MoldSerializer, ParameterSerializer,
)

logger = logging.getLogger(__name__)


def _to_ws_type(event: str) -> str:
    return event.replace(".", "_")


@extend_schema(tags=["Machines"])
class MachineViewSet(viewsets.ModelViewSet):
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("type", "status", "is_active")
    search_fields = ("code", "name", "location")
    ordering_fields = ("code", "name", "status")

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise ValidationError(
                "Impossible de supprimer cette machine : des alertes ou d'autres enregistrements y sont liés. "
                "Désactivez-la plutôt (is_active)."
            )

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        machine = self.get_object()
        ser = MachineStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data["status"]
        machine.status = new_status
        machine.save()

        payload = {
            "type": _to_ws_type("machine.status_changed"),
            "event": "machine.status_changed",
            "machine_id": machine.pk,
            "machine_code": machine.code,
            "machine_name": machine.name,
            "new_status": new_status,
            "ts": now().isoformat(),
        }
        transaction.on_commit(lambda: broadcast_to_alerts_group(payload))
        return Response(MachineSerializer(machine).data)

    @action(detail=True, methods=["get"])
    def parameters(self, request, pk=None):
        machine = self.get_object()
        params = Parameter.objects.filter(is_active=True).order_by("category", "key")
        return Response(ParameterSerializer(params, many=True).data)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """A supplier's own equipment list — read-only, informational (not a
        security boundary: actual ticket visibility is scoped separately by
        assigned_supplier on Ticket, not by this M2M). Permission is enforced
        in urls.py's manual `.as_view()` call, not here — this ViewSet isn't
        registered through a router, so an `@action`'s `permission_classes`
        kwarg would silently be ignored."""
        machines = request.user.assigned_machines.all()
        return Response(MachineSerializer(machines, many=True).data)


@extend_schema(tags=["Machines"])
class ParameterViewSet(viewsets.ModelViewSet):
    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("is_active", "category")
    search_fields = ("key", "label")
    ordering_fields = ("category", "key", "value")


@extend_schema(tags=["Machines"])
class MachineComponentViewSet(viewsets.ModelViewSet):
    queryset = MachineComponent.objects.select_related("machine")
    serializer_class = MachineComponentSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("machine", "is_active")
    search_fields = ("name", "reference")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "machine_component.created", "MachineComponent", obj.pk, f"{obj.name} — {obj.machine.code}")

    def perform_update(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "machine_component.updated", "MachineComponent", obj.pk, f"{obj.name} — {obj.machine.code}")

    def perform_destroy(self, instance):
        detail = f"{instance.name} — {instance.machine.code}"
        pk = instance.pk
        instance.delete()
        log_activity(self.request.user, "machine_component.deleted", "MachineComponent", pk, detail)


@extend_schema(tags=["Machines"])
class MachineParameterViewSet(viewsets.ModelViewSet):
    queryset = MachineParameter.objects.select_related("machine", "component", "updated_by")
    serializer_class = MachineParameterSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("machine", "component")
    search_fields = ("name",)

    def perform_create(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        target = obj.machine.code if obj.machine_id else obj.component.name
        log_activity(self.request.user, "machine_parameter.created", "MachineParameter", obj.pk, f"{obj.name} — {target}")

    def perform_update(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        target = obj.machine.code if obj.machine_id else obj.component.name
        log_activity(self.request.user, "machine_parameter.updated", "MachineParameter", obj.pk, f"{obj.name} — {target}")

    def perform_destroy(self, instance):
        detail = f"{instance.name} — {instance.machine.code if instance.machine_id else instance.component.name}"
        pk = instance.pk
        instance.delete()
        log_activity(self.request.user, "machine_parameter.deleted", "MachineParameter", pk, detail)


@extend_schema(tags=["Machines"])
class AuxiliaryEquipmentViewSet(viewsets.ModelViewSet):
    queryset = AuxiliaryEquipment.objects.prefetch_related("machines")
    serializer_class = AuxiliaryEquipmentSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("is_active",)
    search_fields = ("name", "reference")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "auxiliary_equipment.created", "AuxiliaryEquipment", obj.pk, obj.name)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "auxiliary_equipment.updated", "AuxiliaryEquipment", obj.pk, obj.name)

    def perform_destroy(self, instance):
        detail, pk = instance.name, instance.pk
        instance.delete()
        log_activity(self.request.user, "auxiliary_equipment.deleted", "AuxiliaryEquipment", pk, detail)


@extend_schema(tags=["Machines"])
class MoldViewSet(viewsets.ModelViewSet):
    queryset = Mold.objects.select_related("machine")
    serializer_class = MoldSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("machine", "is_active")
    search_fields = ("name", "reference")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "mold.created", "Mold", obj.pk, f"{obj.name} — {obj.machine.code}")

    def perform_update(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "mold.updated", "Mold", obj.pk, f"{obj.name} — {obj.machine.code}")

    def perform_destroy(self, instance):
        detail = f"{instance.name} — {instance.machine.code}"
        pk = instance.pk
        instance.delete()
        log_activity(self.request.user, "mold.deleted", "Mold", pk, detail)
