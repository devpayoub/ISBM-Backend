"""Alert orchestration: notifications + WebSocket broadcasts + escalation.

This module is the single source of truth for performing alert side-effects
(notification emails, SMS, WebSocket broadcasts, escalation tracking). It is
imported from views and Celery tasks so side-effects remain consistent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.channels_utils import broadcast_to_alerts_group

from .models import Alert, AlertStatus

logger = logging.getLogger(__name__)
User = get_user_model()


# --------------------------------------------------------------------------
# Broadcast helpers
# --------------------------------------------------------------------------

def _ws_type(event: str) -> str:
    return event.replace(".", "_")


def broadcast_alert_event(alert: Alert, event: str, extra: Optional[dict] = None) -> None:
    """Broadcast a normalized alert event to the "alerts" Channels group."""
    payload = {
        "type": _ws_type(event),
        "event": event,
        "alert_id": alert.pk,
        "machine_id": alert.machine_id,
        "machine_code": alert.machine.code if alert.machine_id else None,
        "machine_name": alert.machine.name if alert.machine_id else None,
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "priority_score": alert.priority_score,
        "ts": timezone.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    broadcast_to_alerts_group(payload)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

@dataclass
class NotificationContext:
    subject: str
    recipients: list[str]
    body: str
    sms: str = ""


def _maintenance_recipients(alert: Alert) -> list[str]:
    """Maintenance users on duty (fallback to all maintenance users)."""
    ms = User.objects.filter(role="MAINTENANCE", is_active=True)
    on_duty = ms.filter(is_on_duty=True)
    users = on_duty or ms
    return [u.email for u in users if u.email]


def _manager_recipients() -> list[str]:
    return [u.email for u in User.objects.filter(role="MANAGER", is_active=True, is_on_duty=True, email__isnull=False)] or \
           [u.email for u in User.objects.filter(role="MANAGER", is_active=True, email__isnull=False)]


def build_creation_context(alert: Alert) -> NotificationContext:
    subject = f"[ALERTE {alert.severity}] {alert.title} — {alert.machine.code}"
    body = (
        f"Machine     : {alert.machine.code} — {alert.machine.name}\n"
        f"Sévérité    : {alert.severity}\n"
        f"Opérateur   : {alert.worker_name or '—'}\n"
        f"Shift       : {alert.shift or '—'}\n"
        f"Description : {alert.description or '—'}\n"
        f"Heure       : {alert.created_at:%Y-%m-%d %H:%M}\n"
        f"Référence   : alerte #{alert.pk}\n"
    )
    sms = f"ALERTE {alert.severity} | {alert.machine.code} | {alert.title}"
    return NotificationContext(subject=subject, recipients=_maintenance_recipients(alert), body=body, sms=sms)


def build_escalation_context(alert: Alert, level: int) -> NotificationContext:
    if level == 1:
        recipients = _maintenance_recipients(alert) + _manager_recipients()
        label = "RAPPEL — Alerte non acquittée"
    else:  # level 2
        recipients = _manager_recipients() + _maintenance_recipients(alert)
        label = "ESCALADE CRITIQUE — Alerte non traitée"

    subject = f"{label} {alert.severity} | {alert.machine.code} | {alert.title}"
    body = (
        f"{label}\n\n"
        f"Alerte #{alert.pk}\n"
        f"Machine    : {alert.machine.code} — {alert.machine.name}\n"
        f"Sévérité   : {alert.severity}\n"
        f"Créée le   : {alert.created_at:%Y-%m-%d %H:%M}\n"
        f"Statut     : {alert.status}\n"
        f"En attente depuis {int((timezone.now()-alert.created_at).total_seconds()/60)} min.\n"
    )
    sms = f"{label} {alert.machine.code} | {alert.title}"
    return NotificationContext(subject=subject, recipients=recipients, body=body, sms=sms)


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


def notify_alert_created(alert: Alert) -> None:
    ctx = build_creation_context(alert)
    dispatch_notification(ctx, send_sms=alert.severity == "CRITICAL")


def notify_escalation(alert: Alert, level: int) -> None:
    try:
        alert.escalation_level = level
        alert.escalated_at = timezone.now()
        alert.save(update_fields=["escalation_level", "escalated_at", "updated_at"])
    except Exception:
        logger.warning("Mise à jour escalade échouée sur alerte #%s", alert.pk)

    ctx = build_escalation_context(alert, level)
    dispatch_notification(ctx, send_sms=level >= 2)
