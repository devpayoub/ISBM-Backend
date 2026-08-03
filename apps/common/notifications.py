"""Shared email/SMS notification dispatch, used by any app that needs to
notify users (alerts, SAV/support tickets, ...). Extracted from
apps.alerts.services so it isn't duplicated per app.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NotificationContext:
    subject: str
    recipients: list[str]
    body: str
    sms: str = ""


def dispatch_notification(ctx: NotificationContext, send_sms: bool = False) -> None:
    """Email + optional SMS dispatch. Failures are logged but never raise."""
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
