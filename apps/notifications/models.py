from django.conf import settings
from django.db import models


class Notification(models.Model):
    """One row per user per notification event — created alongside the
    existing email/SMS dispatch in apps.common.notifications.dispatch_notification,
    so every notify_* call across alerts/support gets an in-app inbox entry
    for free instead of needing to be touched individually."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications",
    )
    verb = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    target_type = models.CharField(max_length=50, blank=True, default="")
    target_id = models.PositiveIntegerField(null=True, blank=True)
    url = models.CharField(max_length=200, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.verb} → {self.recipient_id} ({self.created_at:%Y-%m-%d %H:%M})"
