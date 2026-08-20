from django.db import models


class BouchantType(models.TextChoices):
    HDPE = "HDPE", "HDPE"
    LDPE = "LDPE", "LDPE"
    COLORANT = "COLORANT", "Colorant"


class BottleCharacteristic(models.Model):
    """Per-bottle recipe (plan.md §10): how much raw material and colorant
    one bottle uses, and the same for its bouchant (cap) — plus which
    specific StockItem (quality/grade) is used, since different bottle
    categories don't all use the same colorant/matière première reference.
    `category` is the thing that makes two bottles the same or different
    recipe — e.g. "Bouteille 750ml Standard" vs. "...Premium"."""

    category = models.CharField(max_length=120)
    reference = models.CharField(max_length=60, blank=True, default="")

    # Bottle body
    raw_material = models.ForeignKey(
        "stock.StockItem", on_delete=models.PROTECT,
        limit_choices_to={"type": "RAW_MATERIAL"}, related_name="bottle_bodies",
    )
    raw_material_qty_g = models.DecimalField(max_digits=10, decimal_places=3, help_text="Matière première par bouteille (g)")
    colorant = models.ForeignKey(
        "stock.StockItem", on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={"type": "COLORANT"}, related_name="bottle_colorants",
    )
    colorant_qty_g = models.DecimalField(max_digits=10, decimal_places=3, default=0, help_text="Colorant par bouteille (g)")

    # Bouchant (cap) — same shape as the body, per plan.md's HDPE/LDPE/colorant choice.
    bouchant_type = models.CharField(max_length=20, choices=BouchantType.choices, default=BouchantType.HDPE)
    bouchant_raw_material_qty_g = models.DecimalField(max_digits=10, decimal_places=3, default=0, help_text="Matière première du bouchon (g)")
    bouchant_colorant_qty_g = models.DecimalField(max_digits=10, decimal_places=3, default=0, help_text="Colorant du bouchon (g)")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Caractéristique bouteille"
        verbose_name_plural = "Caractéristiques bouteille"
        ordering = ["category"]

    def __str__(self) -> str:
        return f"{self.category} ({self.reference or '—'})"
