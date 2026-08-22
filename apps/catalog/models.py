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


class RecipeComponentType(models.TextChoices):
    BOTTLE_RAW = "BOTTLE_RAW", "Matière première bouteille"
    BOTTLE_COLORANT = "BOTTLE_COLORANT", "Colorant bouteille"
    CAP_RAW = "CAP_RAW", "Matière première bouchon"
    CAP_COLORANT = "CAP_COLORANT", "Colorant bouchon"


class RecipeComponent(models.Model):
    """Normalized breakout of BottleCharacteristic's recipe — one row per
    material a bottle actually consumes. Kept in sync with
    BottleCharacteristic's raw_material_qty_g/colorant_qty_g/bouchant_*_qty_g
    fields by apps.catalog.services.sync_recipe_components() (called on
    every create/update from the view — those denormalized fields stay the
    edit surface, this table is the read surface). This is what
    apps.stock.services.calculate_material_requirements() reads, so every
    consumer (Planning, Package, Catalog capacity, Production validation,
    Dashboard) computes requirements the same single way instead of each
    re-deriving grams-per-bottle math independently."""

    recipe = models.ForeignKey(BottleCharacteristic, on_delete=models.CASCADE, related_name="components")
    component_type = models.CharField(max_length=20, choices=RecipeComponentType.choices)
    stock_item = models.ForeignKey("stock.StockItem", on_delete=models.PROTECT, related_name="recipe_components")
    qty_per_unit_g = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        verbose_name = "Composant de recette"
        verbose_name_plural = "Composants de recette"
        unique_together = [("recipe", "component_type")]
        ordering = ["recipe", "component_type"]

    def __str__(self) -> str:
        return f"{self.recipe.category} — {self.component_type}: {self.qty_per_unit_g} g"
