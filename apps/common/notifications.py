"""Shared email/SMS notification dispatch, used by any app that needs to
notify users (alerts, SAV/support tickets, ...). Extracted from
apps.alerts.services so it isn't duplicated per app.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NotificationContext:
    subject: str
    recipients: list[str]
    body: str
    sms: str = ""
    # Populated alongside `recipients` (email strings) wherever the caller
    # still has the actual User objects on hand, so dispatch_notification
    # can create an in-app Notification row per recipient — one chokepoint
    # covers every notify_* call site in alerts/support without touching
    # each one's email-sending logic.
    recipient_users: list[Any] = field(default_factory=list)
    target_type: str = ""
    target_id: int | None = None
    url: str = ""


def dispatch_notification(ctx: NotificationContext, send_sms: bool = False) -> None:
    """In-app + email + optional SMS dispatch. Failures are logged but never raise."""
    if ctx.recipient_users:
        try:
            from apps.notifications.models import Notification
            Notification.objects.bulk_create([
                Notification(
                    recipient=u, verb=ctx.subject, body=ctx.body,
                    target_type=ctx.target_type, target_id=ctx.target_id, url=ctx.url,
                )
                for u in ctx.recipient_users
            ])
        except Exception as exc:
            logger.error("Création de notification in-app échouée: %s", exc)

    if not ctx.recipients:
        logger.warning("Aucun destinataire pour la notification: %s", ctx.subject)
        return

    from django.core.mail import send_mail
    try:
        send_mail(ctx.subject, ctx.body, None, ctx.recipients, fail_silently=False)
    except Exception as exc:
        logger.error("Envoi e-mail échoué: %s", exc)

    if send_sms:
        try:
            from apps.alerts.sms import send_sms as send_sms_fn
            send_sms_fn(ctx.recipients, ctx.sms)
        except Exception as exc:
            logger.error("Envoi SMS échoué: %s", exc)
