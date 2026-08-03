from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ProductionEntry
from .serializers import ProductionBulkSerializer, ProductionEntrySerializer

# The Saisie page is specifically for floor operators to log hourly
# production; controllers can also log on behalf of their assigned machine.
# Kept in sync with frontend/src/lib/auth/rbac.ts's declare/save checks for
# this page.
WRITER_ROLES = ("ADMIN", "MANAGER", "CONTROLLER", "OPERATOR")


@extend_schema(tags=["Production"])
class ProductionEntryViewSet(viewsets.ModelViewSet):
    queryset = ProductionEntry.objects.select_related("machine", "recorded_by")
    serializer_class = ProductionEntrySerializer
    # Read is open to any authenticated role (matches every other
    # dashboard-data endpoint); writes are role-checked explicitly below
    # rather than via the ADMIN/MANAGER-only IsAdminOrManagerOrReadOnly
    # class, since operators/controllers are exactly who needs to write here.
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("date", "machine", "shift")
    search_fields = ("downtime_reason",)
    ordering_fields = ("date", "hour", "bottles_produced")
    ordering = ["-date", "-hour"]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in WRITER_ROLES:
            raise ValidationError("Rôle insuffisant pour saisir la production.")
        try:
            serializer.save(recorded_by=user)
        except Exception as exc:
            raise ValidationError(f"Saisie invalide: {exc}")

    def perform_update(self, serializer):
        if self.request.user.role not in WRITER_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier la saisie.")
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.role not in WRITER_ROLES:
            raise PermissionDenied("Rôle insuffisant pour supprimer la saisie.")
        instance.delete()

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        if request.user.role not in WRITER_ROLES:
            raise PermissionDenied("Rôle insuffisant pour saisir la production.")
        ser = ProductionBulkSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        created = ser.save()
        return Response(
            ProductionEntrySerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def daily_summary(self, request):
        date = request.query_params.get("date") or timezone.now().date()
        qs = self.queryset.filter(date=date)
        agg = qs.aggregate(
            bottles=Sum("bottles_produced"),
            caps=Sum("caps_produced"),
            rejects=Sum("reject_count"),
            downtime=Sum("downtime_min"),
            pet=Sum("pet_kg"), energy=Sum("energy_kwh"), air=Sum("air_m3"),
        )
        per_machine = defaultdict(int)
        for row in qs.values("machine__code", "bottles_produced", "caps_produced"):
            per_machine[row["machine__code"]] += (row["bottles_produced"] + row["caps_produced"])
        return Response({
            "date": str(date),
            "totals": agg,
            "per_machine": per_machine,
        })

    @action(detail=False, methods=["get"])
    def shift_summary(self, request):
        date = request.query_params.get("date") or timezone.now().date()
        qs = self.queryset.filter(date=date)
        shifts = {}
        for shift in ("MORNING", "AFTERNOON", "NIGHT"):
            row = qs.filter(shift=shift).aggregate(
                bottles=Sum("bottles_produced"), caps=Sum("caps_produced"),
                rejects=Sum("reject_count"), downtime=Sum("downtime_min"),
                pet=Sum("pet_kg"), energy=Sum("energy_kwh"), air=Sum("air_m3"),
            )
            shifts[shift] = row
        return Response({"date": str(date), "shifts": shifts})
