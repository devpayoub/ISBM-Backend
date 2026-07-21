from django.conf import settings
from django.db import models
from django.utils import timezone


class Shift(models.TextChoices):
    MORNING = "MORNING", "Matin (06h-14h)"
    AFTERNOON = "AFTERNOON", "Après-midi (14h-22h)"
    NIGHT = "NIGHT", "Nuit (22h-06h)"


def _shift_for_hour(hour: int) -> str:
    if 6 <= hour < 14:
        return Shift.MORNING
    if 14 <= hour < 22:
        return Shift.AFTERNOON
    return Shift.NIGHT


class ProductionEntry(models.Model):
    date = models.DateField()
    hour = models.PositiveSmallIntegerField(help_text="Créneau horaire 1-24")
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="production_entries")
    shift = models.CharField(max_length=20, choices=Shift.choices, blank=True, default="")

    bottles_produced = models.PositiveIntegerField(default=0)
    caps_produced = models.PositiveIntegerField(default=0)
    reject_count = models.PositiveIntegerField(default=0)
    reject_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    downtime_min = models.PositiveIntegerField(default=0)
    downtime_reason = models.CharField(max_length=200, blank=True, default="")

    pet_kg = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    energy_kwh = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    air_m3 = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="production_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saisie production"
        verbose_name_plural = "Saisies production"
        unique_together = [("date", "hour", "machine")]
        ordering = ["-date", "-hour", "machine__code"]
        indexes = [
            models.Index(fields=["date", "hour"]),
            models.Index(fields=["machine", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.machine.code} {self.date} H{self.hour} — {self.bottles_produced} btl"

    def save(self, *args, **kwargs):
        # Auto-fill shift if missing, auto-fill reject_pct if reject_count + bottles_provided available.
        if not self.shift:
            self.shift = _shift_for_hour(self.hour)
        produced = (self.bottles_produced or 0) + (self.caps_produced or 0)
        if produced and not self.reject_pct:
            self.reject_pct = round((self.reject_count / produced) * 100, 2)
        super().save(*args, **kwargs)
