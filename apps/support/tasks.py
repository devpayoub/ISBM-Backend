from celery import shared_task
from django.utils import timezone

from .models import Ticket, TicketStatus
from .services import notify_awaiting_supplier_reminder

AWAITING_SUPPLIER_REMINDER_MIN = 24 * 60  # 24h


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def remind_awaiting_supplier(self):
    """Periodic task scheduled by django-celery-beat: nudge suppliers who
    haven't responded to a ticket after 24h."""
    stuck = Ticket.objects.filter(status=TicketStatus.AWAITING_SUPPLIER).select_related("machine")
    now = timezone.now()
    for ticket in stuck:
        minutes = (now - ticket.updated_at).total_seconds() / 60
        if minutes >= AWAITING_SUPPLIER_REMINDER_MIN:
            notify_awaiting_supplier_reminder(ticket)
