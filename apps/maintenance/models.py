from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Shift


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


# ─────────────────────── Controller "Control" page (plan.md §12) ───────────────────────
# Structure sourced from the PDF's "Maintenance préventive hebdomadaire" checklist: 3
# templates (ISBM 88/110, Injection 1580, Compresseur), each with named sections and
# checkbox rows. Seeded once via a data migration — not user-editable in v1.

class ChecklistTemplate(models.Model):
    """One per PDF table. ISBM 88/110 is a single shared template applied
    separately to both the ISBM88 and ISBM110 machines (the PDF prints them
    as two columns of the same checklist)."""
    key = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Modèle de checklist"
        verbose_name_plural = "Modèles de checklist"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ChecklistSection(models.Model):
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=160)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Section de checklist"
        verbose_name_plural = "Sections de checklist"
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.template.key} — {self.name}"


class ChecklistItem(models.Model):
    section = models.ForeignKey(ChecklistSection, on_delete=models.CASCADE, related_name="items")
    text = models.CharField(max_length=300)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Élément de checklist"
        verbose_name_plural = "Éléments de checklist"
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.text


class ControlResultStatus(models.TextChoices):
    PENDING = "PENDING", "À vérifier"
    OK = "OK", "Conforme"
    PROBLEM = "PROBLEM", "Problème"


class MaintenanceControl(models.Model):
    """One instance per date + shift + machine/equipment + template — never
    a single weekly record (plan.md §12: 'Do not use one global checklist
    record for the whole week'). Locked once confirmed_at is set, mirroring
    Ticket's append-only-after-terminal-state convention. Created only via
    MaintenanceControlViewSet.start(), which is the sole place that resolves
    the target's template and auto-populates results from its items — so
    exactly one of machine/equipment is always set by construction."""

    template = models.ForeignKey(ChecklistTemplate, on_delete=models.PROTECT, related_name="controls")
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.CASCADE,
        null=True, blank=True, related_name="maintenance_controls",
    )
    equipment = models.ForeignKey(
        "machines.AuxiliaryEquipment", on_delete=models.CASCADE,
        null=True, blank=True, related_name="maintenance_controls",
    )
    date = models.DateField()
    shift = models.CharField(max_length=20, choices=Shift.choices)

    controller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="maintenance_controls_started",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="maintenance_controls_confirmed",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrôle préventif"
        verbose_name_plural = "Contrôles préventifs"
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "shift", "template", "machine"],
                condition=Q(machine__isnull=False),
                name="uniq_control_per_machine_shift_day",
            ),
            models.UniqueConstraint(
                fields=["date", "shift", "template", "equipment"],
                condition=Q(equipment__isnull=False),
                name="uniq_control_per_equipment_shift_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target_label} — {self.date} {self.shift}"

    @property
    def target_label(self) -> str:
        if self.machine_id:
            return self.machine.name
        if self.equipment_id:
            return self.equipment.name
        return "—"

    def is_locked(self) -> bool:
        return self.confirmed_at is not None


class MaintenanceControlResult(models.Model):
    control = models.ForeignKey(MaintenanceControl, on_delete=models.CASCADE, related_name="results")
    item = models.ForeignKey(ChecklistItem, on_delete=models.PROTECT, related_name="results")
    status = models.CharField(max_length=20, choices=ControlResultStatus.choices, default=ControlResultStatus.PENDING)
    note = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Résultat de contrôle"
        verbose_name_plural = "Résultats de contrôle"
        unique_together = ("control", "item")
        ordering = ["item__section__order", "item__order", "id"]

    def __str__(self) -> str:
        return f"{self.item.text} — {self.status}"
