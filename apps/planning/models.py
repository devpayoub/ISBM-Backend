from django.db import models


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
