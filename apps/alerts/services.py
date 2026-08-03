"""Alert orchestration: notifications + WebSocket broadcasts + escalation.

This module is the single source of truth for performing alert side-effects
(notification emails, SMS, WebSocket broadcasts, escalation tracking). It is
imported from views and Celery tasks so side-effects remain consistent.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.channels_utils import broadcast_to_alerts_group
from apps.common.notifications import NotificationContext, dispatch_notification

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
        "worker_name": alert.worker_name,
        "reported_by_name": alert.reported_by.full_name if alert.reported_by_id else None,
        "ts": timezone.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    broadcast_to_alerts_group(payload)


def sync_machine_andon_status(machine) -> None:
    """The only place allowed to change Machine.status: a machine is always
    RUNNING unless a CRITICAL alert is currently active on it, in which case
    it's BREAKDOWN. Call this after any alert create/resolve/close so the
    machine's status (and its derived Andon color) stays in lockstep with
    its alerts instead of requiring a manual admin edit."""
    from apps.machines.models import MachineStatus

    has_active_critical = machine.alerts.filter(
        severity="CRITICAL", status__in=[AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS],
    ).exists()
    target_status = MachineStatus.BREAKDOWN if has_active_critical else MachineStatus.RUNNING
    if machine.status != target_status:
        machine.status = target_status
        machine.save(update_fields=["status", "updated_at"])

    payload = {
        "type": _ws_type("machine.status_changed"),
        "event": "machine.status_changed",
        "machine_id": machine.pk,
        "machine_code": machine.code,
        "new_status": machine.status,
        "color": machine.get_andon_status(),
        "ts": timezone.now().isoformat(),
    }
    broadcast_to_alerts_group(payload)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

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
