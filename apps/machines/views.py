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

from apps.common.channels_utils import broadcast_to_alerts_group
from apps.common.permissions import IsAdminOrManagerOrReadOnly

from .models import Machine, MachineStatus, Parameter
from .serializers import MachineSerializer, MachineStatusSerializer, ParameterSerializer

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


@extend_schema(tags=["Machines"])
class ParameterViewSet(viewsets.ModelViewSet):
    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("is_active", "category")
    search_fields = ("key", "label")
    ordering_fields = ("category", "key", "value")
