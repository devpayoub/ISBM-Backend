"""Celery tasks for alert escalation + MTTR-Pareto cron work."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Alert, AlertStatus
from .services import notify_escalation

logger = logging.getLogger(__name__)

# Escalation windows (minutes): first reminder -> critical escalation.
REMINDER_DELAY = 5
CRITICAL_DELAY = 15


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_escalations(self):
    """Periodic task scheduled by django-celery-beat (every 2 min)."""
    open_alerts = Alert.objects.filter(status=AlertStatus.OPEN).select_related("machine")
    now = timezone.now()
    dispatched = 0
    for alert in open_alerts:
        minutes = (now - alert.created_at).total_seconds() / 60
        if minutes >= CRITICAL_DELAY and alert.escalation_level < 2:
            notify_escalation(alert, level=2)
            dispatched += 1
        elif minutes >= REMINDER_DELAY and alert.escalation_level < 1:
            notify_escalation(alert, level=1)
            dispatched += 1
    logger.info("Escalade check: %d alertes ouvertes, %d escalades", open_alerts.count(), dispatched)
    return {"open": open_alerts.count(), "escalated": dispatched}


@shared_task
def cleanup_stale_in_progress_alerts():
    """Safety: alertes IN_PROGRESS sans intervention depuis plus de 24h -> repassées OPEN."""
    threshold = timezone.now() - timedelta(hours=24)
    stale = Alert.objects.filter(
        status=AlertStatus.IN_PROGRESS,
        updated_at__lt=threshold,
    )
    count = stale.update(status=AlertStatus.OPEN, updated_at=timezone.now())
    logger.info("%d alertes IN_PROGRESS repassées en OPEN.", count)
    return count
