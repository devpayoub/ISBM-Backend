from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """A curated record of meaningful actions — not every HTTP request.

    Populated via ``apps.audit.services.log_activity`` from the specific
    view methods that represent an actual task (declaring/acknowledging/
    resolving an alert, finishing an intervention, logging in/out), so an
    Admin can see what each Controller/Maintenance user actually did.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="activity_logs",
    )
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50, blank=True, default="")
    target_id = models.PositiveIntegerField(null=True, blank=True)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrée du journal d'activité"
        verbose_name_plural = "Journal d'activité"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        who = self.user.full_name if self.user_id else "Système"
        return f"{who} — {self.action} ({self.created_at:%Y-%m-%d %H:%M})"
