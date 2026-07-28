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
    verified = models.BooleanField(default=False)

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


class PmFrequency(models.TextChoices):
    DAILY = "DAILY", "Quotidienne"
    WEEKLY = "WEEKLY", "Hebdomadaire"
    MONTHLY = "MONTHLY", "Mensuelle"
    QUARTERLY = "QUARTERLY", "Trimestrielle"


class PmStatus(models.TextChoices):
    DUE = "DUE", "À faire"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    DONE = "DONE", "Terminée"
    OVERDUE = "OVERDUE", "En retard"


class PreventiveMaintenance(models.Model):
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.CASCADE,
        related_name="preventive_tasks",
    )
    task = models.CharField(max_length=200)
    frequency = models.CharField(max_length=20, choices=PmFrequency.choices, default=PmFrequency.MONTHLY)
    checklist = models.JSONField(default=dict, blank=True)

    last_done = models.DateField(null=True, blank=True)
    next_due = models.DateField()

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="preventive_tasks",
    )
    status = models.CharField(max_length=20, choices=PmStatus.choices, default=PmStatus.DUE)

    class Meta:
        verbose_name = "Maintenance préventive"
        verbose_name_plural = "Maintenances préventives"
        ordering = ["next_due"]

    def __str__(self) -> str:
        return f"{self.task} — {self.machine_id}"

    def save(self, *args, **kwargs):
        if self.status == PmStatus.DUE and self.next_due and self.next_due < timezone.localdate():
            self.status = PmStatus.OVERDUE
        super().save(*args, **kwargs)
