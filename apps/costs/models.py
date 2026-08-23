from datetime import date

from django.db import models
from django.utils import timezone


class CostParameter(models.Model):
    name = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=200, blank=True, default="")
    value = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    unit = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre de coût"
        verbose_name_plural = "Paramètres de coûts"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.label or self.name} = {self.value} {self.unit}".strip()


class CostRecord(models.Model):
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="cost_records")
    date = models.DateField()
    shift = models.CharField(max_length=20, blank=True, default="")

    labor_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    production_count = models.PositiveIntegerField(default=0)
    cost_per_bottle = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enregistrement de coût"
        verbose_name_plural = "Enregistrements de coûts"
        unique_together = [("date", "shift", "machine")]
        ordering = ["-date", "machine__code"]

    def __str__(self) -> str:
        return f"Coût {self.machine.code} {self.date} = {self.total_cost} (/{self.cost_per_bottle}/btl)"

    def compute_totals(self) -> None:
        self.total_cost = self.labor_cost
        if self.production_count:
            self.cost_per_bottle = round(self.total_cost / self.production_count, 6)
