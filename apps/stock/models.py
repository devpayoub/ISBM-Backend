from django.conf import settings
from django.db import models


class StockItemType(models.TextChoices):
    RAW_MATERIAL = "RAW_MATERIAL", "Matière première"
    COLORANT = "COLORANT", "Colorant"


class StockStatus(models.TextChoices):
    IN_STOCK = "IN_STOCK", "En stock"
    LOW = "LOW", "Stock bas"
    RUPTURE = "RUPTURE", "Rupture de stock"


class StockItem(models.Model):
    """Raw material or colorant record (plan.md §4). `quantity` is never
    written through the plain CRUD serializer — every change goes through
    StockItemViewSet.move() so a StockMovement row is always created,
    mirroring why apps.support.Ticket isn't a plain ModelViewSet for its
    status field."""

    type = models.CharField(max_length=20, choices=StockItemType.choices)
    name = models.CharField(max_length=120)
    reference = models.CharField(max_length=60, unique=True)
    supplier = models.CharField(max_length=120, blank=True, default="")
    # RAL colorimétrique — colorant only, blank for raw material.
    ral = models.CharField(max_length=20, blank=True, default="")
    unit = models.CharField(max_length=20, default="kg")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    min_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    batch = models.CharField(max_length=60, blank=True, default="")
    received_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="stock_items_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Article de stock"
        verbose_name_plural = "Articles de stock"
        ordering = ["type", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.reference})"

    def get_status(self) -> str:
        if self.quantity <= 0:
            return StockStatus.RUPTURE
        if self.quantity <= self.min_threshold:
            return StockStatus.LOW
        return StockStatus.IN_STOCK


class StockMovementType(models.TextChoices):
    RECEIPT = "RECEIPT", "Réception"
    CONSUMPTION = "CONSUMPTION", "Consommation"
    ADJUSTMENT = "ADJUSTMENT", "Ajustement"


class StockMovementSourceType(models.TextChoices):
    # Consumption tied to a PlanningOrder — whichever of Package (today) or
    # a validated Production entry (future) triggers it first, source_id is
    # always the order's id, so the second one is a guaranteed no-op.
    PLANNING_ORDER = "PLANNING_ORDER", "Commande de planning"
    # Ad-hoc bag with no linked order — source_id is the Package's own id.
    PACKAGE = "PACKAGE", "Sac (sans commande)"


class StockMovement(models.Model):
    """Append-only quantity history — copies apps.support.TicketStatusLog's
    shape/discipline (never edited or deleted, one row per change).
    source_type/source_id (optional — only set for automatic consumption,
    not for manual receipts/adjustments) is what guarantees the same
    production never consumes stock twice: the partial unique constraint
    below rejects a second CONSUMPTION row for the same
    (source_type, source_id, stock_item)."""

    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="movements")
    type = models.CharField(max_length=20, choices=StockMovementType.choices)
    delta = models.DecimalField(max_digits=12, decimal_places=3, help_text="Positif = ajout, négatif = retrait")
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=300, blank=True, default="")
    source_type = models.CharField(max_length=20, choices=StockMovementSourceType.choices, blank=True, default="")
    source_id = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "stock_item", "type"],
                condition=models.Q(source_type__gt="") & models.Q(source_id__isnull=False),
                name="unique_stock_movement_per_source",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.delta} — {self.stock_item.reference}"


class StockReservation(models.Model):
    """Stock spoken-for by a queued PlanningOrder but not yet physically
    consumed — Planning reserves, it never deducts physical stock (that only
    happens once production against the order is validated). One row per
    (order, stock_item, component_type); wholesale recomputed by
    apps.stock.services.sync_reservations_for_order() on every order
    create/update — never hand-edited, matching this app's "always
    recomputed, never stored by hand" convention used elsewhere (Planning
    schedule, Catalog capacity)."""

    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="reservations")
    planning_order = models.ForeignKey("planning.PlanningOrder", on_delete=models.CASCADE, related_name="reservations")
    component_type = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réservation de stock"
        verbose_name_plural = "Réservations de stock"
        unique_together = [("planning_order", "stock_item", "component_type")]
        ordering = ["stock_item", "planning_order"]

    def __str__(self) -> str:
        return f"{self.stock_item.reference} × {self.quantity} — commande #{self.planning_order_id}"
