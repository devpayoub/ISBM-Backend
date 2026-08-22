from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity
from apps.machines.models import Machine
from apps.stock.models import StockMovementSourceType, StockMovementType
from apps.stock.services import apply_movement_idempotent, raw_and_colorant_requirement

from .models import Package
from .serializers import PackageSerializer
from .services import resolve_personnel

# plan.md §2: Package/Bag traceability is an Admin capability.
MANAGE_ROLES = ("ADMIN", "MANAGER")


def _snapshot_reference(stock_item):
    # `stock_item` is already a resolved StockItem instance here (DRF's
    # ModelSerializer turns a PrimaryKeyRelatedField's validated_data
    # straight into the model instance, not the raw pk).
    return stock_item.reference if stock_item else ""


@extend_schema(tags=["Package"])
class PackageViewSet(viewsets.ModelViewSet):
    queryset = Package.objects.select_related("machine", "raw_material", "color", "created_by")
    serializer_class = PackageSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("machine", "raw_material", "color", "supplier")
    search_fields = ("reference", "raw_material_reference_snapshot", "color_reference_snapshot", "supplier")
    ordering = ["-production_started_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        date_str = self.request.query_params.get("date")
        if date_str:
            date_val = parse_date(date_str)
            if date_val is None:
                raise ValidationError("Format de date invalide pour 'date' (attendu YYYY-MM-DD).")
            qs = qs.filter(production_started_at__date=date_val)
        return qs

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer un sac.")
        vd = serializer.validated_data
        machine = vd["machine"]
        started = vd["production_started_at"]
        finished = vd.get("production_finished_at")
        bottle = vd.get("bottle")
        raw_material = vd.get("raw_material")
        color = vd.get("color")
        bottle_count = vd["bottle_count"]
        planning_order = vd.get("planning_order")

        # Auto-consume stock (the "how much do I still need" calculation the
        # user asked for): if a bottle recipe is linked, deduct exactly what
        # this bag used from the chosen raw material/colorant. Wrapped in one
        # transaction with the Package insert — if either deduction would go
        # negative, apply_movement raises and the whole bag creation rolls
        # back, so a bag is never recorded without the stock to back it.
        #
        # Idempotency key: when this bag fulfills an order, consumption is
        # keyed to that ORDER (source_id=planning_order.id) rather than the
        # bag itself — so a second bag against the same order, or a future
        # validated Production entry for it (once that exists), can never
        # double-consume; whichever happens first "wins" and the rest are
        # no-ops. Unlinked bags keep today's behavior, keyed to themselves.
        with transaction.atomic():
            obj = serializer.save(
                created_by=self.request.user,
                raw_material_reference_snapshot=_snapshot_reference(raw_material),
                color_reference_snapshot=_snapshot_reference(color),
                personnel_snapshot=resolve_personnel(machine, started, finished),
            )
            if bottle:
                raw_item, raw_kg, colorant_item, colorant_kg = raw_and_colorant_requirement(bottle, bottle_count)
                if planning_order:
                    source_type, source_id = StockMovementSourceType.PLANNING_ORDER, planning_order.id
                else:
                    source_type, source_id = StockMovementSourceType.PACKAGE, obj.id

                update_fields = []
                if raw_material and raw_item and raw_kg:
                    _, created = apply_movement_idempotent(
                        raw_material, StockMovementType.CONSUMPTION, -raw_kg, f"Sac {obj.reference}",
                        self.request.user, source_type=source_type, source_id=source_id,
                    )
                    if created:
                        obj.raw_material_consumed_kg = raw_kg
                        update_fields.append("raw_material_consumed_kg")
                if color and colorant_item and colorant_kg:
                    _, created = apply_movement_idempotent(
                        color, StockMovementType.CONSUMPTION, -colorant_kg, f"Sac {obj.reference}",
                        self.request.user, source_type=source_type, source_id=source_id,
                    )
                    if created:
                        obj.colorant_consumed_kg = colorant_kg
                        update_fields.append("colorant_consumed_kg")
                if update_fields:
                    obj.save(update_fields=update_fields)
        log_activity(self.request.user, "package.created", "Package", obj.pk, obj.reference)

    def perform_update(self, serializer):
        # Stock consumption is only ever auto-applied at creation — editing
        # a bag afterward (e.g. fixing a typo in notes) never re-triggers a
        # second deduction. A genuine correction goes through a manual Stock
        # Adjustment movement instead, same as any other historical record.
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier un sac.")
        instance = self.get_object()
        vd = serializer.validated_data
        machine = vd.get("machine", instance.machine)
        started = vd.get("production_started_at", instance.production_started_at)
        finished = vd.get("production_finished_at", instance.production_finished_at)
        recompute = any(f in vd and vd[f] != getattr(instance, f) for f in ("machine", "production_started_at", "production_finished_at"))
        extra = {}
        if recompute:
            extra["personnel_snapshot"] = resolve_personnel(machine, started, finished)
        if "raw_material" in vd and vd["raw_material"] != instance.raw_material:
            extra["raw_material_reference_snapshot"] = _snapshot_reference(vd["raw_material"])
        if "color" in vd and vd["color"] != instance.color:
            extra["color_reference_snapshot"] = _snapshot_reference(vd["color"])
        obj = serializer.save(**extra)
        log_activity(self.request.user, "package.updated", "Package", obj.pk, obj.reference)

    def perform_destroy(self, instance):
        # Never — plan.md §15: bag traceability records are permanent.
        raise PermissionDenied("Suppression interdite — un sac est un enregistrement de traçabilité permanent.")

    @action(detail=False, methods=["get"], url_path="resolve-personnel")
    def resolve_personnel_preview(self, request):
        """Live preview for the creation form, mirroring
        apps.reclamation's resolve-personnel action."""
        machine_id = request.query_params.get("machine")
        start_raw = request.query_params.get("start")
        end_raw = request.query_params.get("end")
        if not machine_id or not start_raw:
            raise ValidationError("Paramètres 'machine' et 'start' requis.")
        machine = Machine.objects.filter(pk=machine_id).first()
        if not machine:
            raise ValidationError("Machine introuvable.")
        start = parse_datetime(start_raw)
        if start is None:
            raise ValidationError("Format de date invalide pour 'start' (attendu ISO 8601).")
        end = parse_datetime(end_raw) if end_raw else None
        if end_raw and end is None:
            raise ValidationError("Format de date invalide pour 'end' (attendu ISO 8601).")
        return Response(resolve_personnel(machine, start, end))

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        """The "sold" event (no separate sales/customer model — plan.md's
        own convention for Package is plain free-text fields, e.g.
        `supplier`). One-way: a bag ships once, mirroring StockItemViewSet.
        move() and Ticket's status transitions rather than a raw PATCH."""
        if request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour expédier un sac.")
        pkg = self.get_object()
        if pkg.shipped_at:
            raise ValidationError(f"Ce sac a déjà été expédié le {pkg.shipped_at:%Y-%m-%d %H:%M}.")
        shipped_to = (request.data.get("shipped_to") or "").strip()
        pkg.shipped_at = timezone.now()
        pkg.shipped_to = shipped_to
        pkg.save(update_fields=["shipped_at", "shipped_to"])
        log_activity(request.user, "package.shipped", "Package", pkg.pk, f"{pkg.reference} → {shipped_to or 'destinataire non précisé'}")
        return Response(PackageSerializer(pkg).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Ties Package to the "how much do we have / make / sell" question:
        bottles bagged (made), bottles shipped (sold), and the gap between
        them still sitting in the factory (on hand) — over the current
        get_queryset() filters (machine/date/search all still apply)."""
        qs = self.get_queryset()
        shipped_qs = qs.filter(shipped_at__isnull=False)
        bottles_made = qs.aggregate(total=Sum("bottle_count"))["total"] or 0
        bottles_shipped = shipped_qs.aggregate(total=Sum("bottle_count"))["total"] or 0
        return Response({
            "bags_total": qs.aggregate(total=Count("id"))["total"] or 0,
            "bags_shipped": shipped_qs.aggregate(total=Count("id"))["total"] or 0,
            "bottles_made": bottles_made,
            "bottles_shipped": bottles_shipped,
            "bottles_on_hand": bottles_made - bottles_shipped,
        })
