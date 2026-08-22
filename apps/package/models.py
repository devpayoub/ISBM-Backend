from django.conf import settings
from django.db import models
from django.utils import timezone


class Package(models.Model):
    """A bag of packaged bottles (plan.md §9). Auto-numbered like Ticket/
    Reclamation. Traceability chain: Bag → production → machine → raw
    material → color → supplier → date/time → personnel.

    `raw_material`/`color` stay live FKs into Stock so the bag can be
    searched/filtered by current material records, but their reference is
    also snapshotted as plain text at creation time — plan.md §9: "Use
    immutable historical references... so changing a current employee/
    material name does not corrupt old production history." Personnel are
    stored the same way (see `personnel_snapshot`, mirrors
    apps.reclamation.Reclamation.resolved_personnel exactly) rather than a
    live M2M, for the same reason."""

    reference = models.CharField(max_length=30, unique=True, blank=True)
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="packages")

    bottle_count = models.PositiveIntegerField()

    # Optional link to the order this bag fulfills — when set, stock
    # consumption is keyed to the ORDER (source_type=PLANNING_ORDER,
    # source_id=planning_order.id) instead of this bag, so a second bag
    # against the same order — or a future Production-entry validation for
    # it — never double-consumes. SET_NULL on delete: a permanent
    # traceability record must survive its order being removed.
    planning_order = models.ForeignKey(
        "planning.PlanningOrder", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="packages",
    )

    # Which bottle recipe (plan.md §10 characteristics) this bag was made
    # from — supplies the per-bottle grams used to auto-calculate and
    # auto-deduct stock consumption below. Optional: a bag can still be
    # recorded without one, just without automatic stock deduction.
    bottle = models.ForeignKey(
        "catalog.BottleCharacteristic", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="packages",
    )

    raw_material = models.ForeignKey(
        "stock.StockItem", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="packages_as_raw_material",
    )
    raw_material_reference_snapshot = models.CharField(max_length=100, blank=True, default="")
    # Immutable — computed once at creation from bottle.raw_material_qty_g ×
    # bottle_count, kept even if the bottle recipe changes later.
    raw_material_consumed_kg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    color = models.ForeignKey(
        "stock.StockItem", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="packages_as_color",
    )
    color_reference_snapshot = models.CharField(max_length=100, blank=True, default="")
    colorant_consumed_kg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    supplier = models.CharField(max_length=150, blank=True, default="")

    # Shipping = the "sold" event for this factory: a bag leaves once, via
    # PackageViewSet.ship() (mirrors StockItemViewSet.move()'s dedicated-
    # action pattern rather than a raw PATCH, so it's a one-way transition
    # like Ticket's status moves). shipped_to is free text, matching the
    # existing `supplier` field's plain-string convention (no Customer model).
    shipped_at = models.DateTimeField(null=True, blank=True)
    shipped_to = models.CharField(max_length=150, blank=True, default="")

    production_started_at = models.DateTimeField()
    production_finished_at = models.DateTimeField(null=True, blank=True)

    # Immutable snapshot of who was working during [started_at, finished_at)
    # — computed once via services.resolve_personnel(), never a live query.
    personnel_snapshot = models.JSONField(default=list, blank=True)

    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="packages_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sac (package)"
        verbose_name_plural = "Sacs (package)"
        ordering = ["-production_started_at"]

    def __str__(self) -> str:
        return self.reference or f"Sac #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            count = Package.objects.filter(reference__startswith=f"BAG-{year}-").count() + 1
            self.reference = f"BAG-{year}-{count:04d}"
        super().save(*args, **kwargs)
