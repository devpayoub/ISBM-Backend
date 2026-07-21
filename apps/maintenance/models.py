from django.conf import settings
from django.db import models
from django.utils import timezone


class Intervention(models.Model):
    alert = models.OneToOneField(
        "alerts.Alert", on_delete=models.CASCADE,
        related_name="intervention",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="interventions",
    )

    action_taken = models.TextField(blank=True, default="")
    parts_used = models.CharField(max_length=400, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_min = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Intervention {self.id} — alerte {self.alert_id}"

    def save(self, *args, **kwargs):
        if self.finished_at and self.started_at:
            delta = self.finished_at - self.started_at
            self.duration_min = max(int(delta.total_seconds() // 60), 0)
        super().save(*args, **kwargs)
