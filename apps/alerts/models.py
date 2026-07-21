from django.conf import settings
from django.db import models
from django.utils import timezone


class Severity(models.TextChoices):
    CRITICAL = "CRITICAL", "Critique"
    MAJOR = "MAJOR", "Majeure"
    MINOR = "MINOR", "Mineure"
    INFO = "INFO", "Information"


class AlertStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acquittée"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    RESOLVED = "RESOLVED", "Résolue"
    CLOSED = "CLOSED", "Clôturée"


class AlertCategory(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, unique=True)
    severity_default = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.MAJOR,
    )
    color = models.CharField(max_length=20, blank=True, default="#f59e0b")
    requires_maintenance = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Catégorie d'alerte"
        verbose_name_plural = "Catégories d'alertes"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


def _upload_to(instance, filename):
    return f"alert_photos/{timezone.now():%Y/%m/%d}/{filename}"


class Alert(models.Model):
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.PROTECT,
        related_name="alerts",
    )
    category = models.ForeignKey(
        AlertCategory, on_delete=models.PROTECT,
        related_name="alerts", null=True, blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MAJOR)
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.OPEN)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alerts_reported",
    )
    worker_name = models.CharField(max_length=200, blank=True, default="")
    shift = models.CharField(max_length=20, blank=True, default="")

    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alerts_acknowledged",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alerts_resolved",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    escalation_level = models.PositiveIntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)

    downtime_min = models.PositiveIntegerField(default=0)
    bottles_lost = models.PositiveIntegerField(default=0)
    photo = models.ImageField(upload_to=_upload_to, null=True, blank=True)
    priority_score = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["machine", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.title} — {self.machine.code} ({self.created_at:%Y-%m-%d %H:%M})"

    def save(self, *args, **kwargs):
        # Auto-compute priority: critical > major > minor > info; resolved/closed downweight.
        sev_weight = {"CRITICAL": 1000, "MAJOR": 500, "MINOR": 200, "INFO": 50}.get(self.severity, 0)
        open_bonus = 1000 if self.status in ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS") else 0
        esc_bonus = self.escalation_level * 250
        self.priority_score = sev_weight + open_bonus + esc_bonus
        super().save(*args, **kwargs)

    # state-machine helpers — return False when the transition is not allowed.
    def can_acknowledge(self, user) -> bool:
        return self.status in (AlertStatus.OPEN,) and not self.is_terminal()

    def can_resolve(self, user) -> bool:
        return self.status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS)

    def can_close(self, user) -> bool:
        return self.status == AlertStatus.RESOLVED and user.role in ("ADMIN", "MANAGER")

    def is_terminal(self) -> bool:
        return self.status == AlertStatus.CLOSED


class AlertComment(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commentaire d'alerte"
        verbose_name_plural = "Commentaires d'alertes"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment@{self.created_at:%Y-%m-%d %H:%M}"
