from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity
from apps.machines.models import Machine

from .models import Reclamation, ReclamationAttachment, ReclamationStatus
from .serializers import (
    ReclamationAttachmentSerializer, ReclamationCloseSerializer, ReclamationSerializer,
)
from .services import resolve_personnel

# plan.md §2: Reclamation management is an Admin capability — not
# something Controller/Maintenance/Operator do themselves.
MANAGE_ROLES = ("ADMIN", "MANAGER")


@extend_schema(tags=["Reclamation"])
class ReclamationViewSet(viewsets.ModelViewSet):
    queryset = Reclamation.objects.select_related(
        "stock_item", "machine", "created_by", "closed_by",
    ).prefetch_related("attachments")
    serializer_class = ReclamationSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("status", "severity", "machine", "stock_item")
    search_fields = ("reference", "client", "description", "product_reference")
    ordering = ["-reported_at"]

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer une réclamation.")
        package = serializer.validated_data.get("package")
        machine = package.machine if package else None
        production_at = package.production_started_at if package else None
        snapshot = resolve_personnel(machine, production_at) if machine and production_at else {}
        obj = serializer.save(
            created_by=self.request.user, machine=machine, production_at=production_at,
            resolved_personnel=snapshot,
        )
        log_activity(self.request.user, "reclamation.created", "Reclamation", obj.pk, obj.reference)

    def perform_update(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier une réclamation.")
        instance = self.get_object()
        # Only re-derive machine/production_at/personnel when the package
        # link actually changed, so an unrelated edit (severity,
        # description...) doesn't silently overwrite the historical
        # personnel snapshot.
        package_changed = (
            "package" in serializer.validated_data
            and serializer.validated_data["package"] != instance.package
        )
        if package_changed:
            new_package = serializer.validated_data["package"]
            machine = new_package.machine if new_package else None
            production_at = new_package.production_started_at if new_package else None
            snapshot = resolve_personnel(machine, production_at) if machine and production_at else {}
            obj = serializer.save(machine=machine, production_at=production_at, resolved_personnel=snapshot)
        else:
            obj = serializer.save()
        log_activity(self.request.user, "reclamation.updated", "Reclamation", obj.pk, obj.reference)

    def perform_destroy(self, instance):
        raise PermissionDenied("Suppression interdite — clôturez la réclamation à la place.")

    @action(detail=True, methods=["patch"])
    def close(self, request, pk=None):
        if request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour clôturer une réclamation.")
        rec = self.get_object()
        if rec.status == ReclamationStatus.CLOSED:
            raise ValidationError("Réclamation déjà clôturée.")
        ser = ReclamationCloseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rec.resolution = ser.validated_data["resolution"]
        rec.status = ReclamationStatus.CLOSED
        rec.closed_by = request.user
        rec.closed_at = timezone.now()
        rec.save()
        log_activity(request.user, "reclamation.closed", "Reclamation", rec.pk, rec.reference)
        return Response(ReclamationSerializer(rec).data)

    @action(detail=False, methods=["get"], url_path="resolve-personnel")
    def resolve_personnel_preview(self, request):
        """Live preview for the creation form (plan.md §6: 'When the
        affected date/time and stock/material reference are entered, the
        application should identify the personnel'). Nothing is persisted
        here — the stored snapshot is computed at actual save time.

        Preferred usage is `?package=<id>` — the bag already carries its
        own machine/production_started_at, so no manual machine/date input
        is needed. `machine`+`when` remain supported directly for callers
        that don't have a package yet."""
        package_id = request.query_params.get("package")
        if package_id:
            from apps.package.models import Package
            package = Package.objects.select_related("machine").filter(pk=package_id).first()
            if package is None:
                raise ValidationError("Sac introuvable.")
            return Response(resolve_personnel(package.machine, package.production_started_at))

        machine_id = request.query_params.get("machine")
        when_raw = request.query_params.get("when")
        if not when_raw:
            raise ValidationError("Paramètre 'package', ou 'when', requis.")
        when = parse_datetime(when_raw)
        if when is None:
            raise ValidationError("Format de date invalide pour 'when' (attendu ISO 8601).")
        machine = Machine.objects.filter(pk=machine_id).first() if machine_id else None
        return Response(resolve_personnel(machine, when))

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def add_attachment(self, request, pk=None):
        rec = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            raise ValidationError("Aucun fichier fourni.")
        attachment = ReclamationAttachment.objects.create(reclamation=rec, file=file_obj, uploaded_by=request.user)
        return Response(ReclamationAttachmentSerializer(attachment).data, status=201)
