from django.conf import settings
from django.db import models
from django.utils import timezone


class ProductionPlan(models.Model):
    date = models.DateField()
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="plans")
    product = models.CharField(max_length=120, blank=True, default="")

    target_bph = models.PositiveIntegerField(default=0)
    actual_bph = models.PositiveIntegerField(default=0)
    variance = models.IntegerField(default=0)
    variance_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan de production"
        verbose_name_plural = "Plans de production"
        unique_together = [("date", "machine", "product")]
        ordering = ["-date", "machine__code"]

    def __str__(self) -> str:
        return f"{self.date} {self.machine_id} — {self.product or '-'} cible={self.target_bph}"

    def save(self, *args, **kwargs):
        self.variance = self.actual_bph - self.target_bph
        self.variance_pct = (
            round((self.variance / self.target_bph) * 100, 2) if self.target_bph else 0
        )
        super().save(*args, **kwargs)


class PlanningOrderStatus(models.TextChoices):
    QUEUED = "QUEUED", "En file d'attente"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    DONE = "DONE", "Terminée"
    CANCELLED = "CANCELLED", "Annulée"


class PlanningOrder(models.Model):
    """A queued production order (plan.md §7) — what to produce, on which
    machine/mold, and in what sequence. Distinct from ProductionPlan (which
    tracks target-vs-actual BPH for a date/machine/product, used by the
    existing 'Écarts' page): this is the order queue that
    services.calculate_schedule() sequences and times. Estimated start/
    finish are always computed on read, never stored, so reprioritizing
    never leaves stale numbers behind."""

    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="planning_orders")
    mold = models.ForeignKey(
        "machines.Mold", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="planning_orders",
    )
    bottle = models.ForeignKey(
        "catalog.BottleCharacteristic", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="planning_orders",
    )
    product_reference = models.CharField(max_length=100, blank=True, default="")
    color = models.CharField(max_length=100, blank=True, default="")
    color_formulation = models.TextField(blank=True, default="")

    quantity = models.PositiveIntegerField()
    time_per_bottle_sec = models.DecimalField(max_digits=8, decimal_places=3)
    mold_change_min = models.PositiveIntegerField(
        default=0, help_text="Temps de changement de moule requis avant cette commande, si le moule diffère de la précédente",
    )

    # Lower = more urgent — v1 is an explicit field + reorder via plain
    # PATCH rather than a full priority-solver (plan.md §7: "should be
    # configurable business logic", not a single hard-coded rule).
    priority = models.IntegerField(default=100)
    requested_start = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PlanningOrderStatus.choices, default=PlanningOrderStatus.QUEUED)

    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="planning_orders_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Commande de planning"
        verbose_name_plural = "Commandes de planning"
        ordering = ["machine", "priority", "id"]

    def __str__(self) -> str:
        return f"{self.product_reference or 'Commande'} × {self.quantity} — {self.machine_id}"

    def save(self, *args, **kwargs):
        # Auto-numbered like Package/Ticket — the create form no longer
        # collects this by hand.
        if not self.product_reference:
            year = timezone.now().year
            count = PlanningOrder.objects.filter(product_reference__startswith=f"ORD-{year}-").count() + 1
            self.product_reference = f"ORD-{year}-{count:04d}"
        super().save(*args, **kwargs)
