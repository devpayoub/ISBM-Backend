from decimal import Decimal

from django.db import models


class OEERecord(models.Model):
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="oee_records")
    date = models.DateField()
    shift = models.CharField(max_length=20, blank=True, default="DAY")

    theoretical_production = models.PositiveIntegerField(default=0)
    actual_production = models.PositiveIntegerField(default=0)
    total_downtime_min = models.PositiveIntegerField(default=0)
    shift_duration_min = models.PositiveIntegerField(default=1440)

    availability_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    performance_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    quality_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    trs_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    reject_count = models.PositiveIntegerField(default=0)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enregistrement OEE"
        verbose_name_plural = "Enregistrements OEE"
        unique_together = [("date", "shift", "machine")]
        ordering = ["-date", "machine__code"]

    def __str__(self) -> str:
        return f"TRS {self.machine.code} {self.date} = {self.trs_pct}%"

    def compute(self) -> None:
        """Recompute OEE metrics from raw inputs. Caller must save()."""
        ts = Decimal(self.shift_duration_min or 1440)
        avail = self.availability_pct = Decimal(round(
            (ts - Decimal(self.total_downtime_min)) / ts * 100 if ts else 0, 2,
        ))
        theo = Decimal(self.theoretical_production or 0)
        perf = self.performance_pct = Decimal(
            round(Decimal(self.actual_production) / theo * 100, 2) if theo else 0
        )
        actual = Decimal(self.actual_production or 0)
        reject = Decimal(self.reject_count or 0)
        self.quality_pct = Decimal(
            round((actual - reject) / actual * 100, 2) if actual else 0
        )
        self.trs_pct = Decimal(round(avail * perf * self.quality_pct / Decimal("10000"), 2))
