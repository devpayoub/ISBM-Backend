"""SAV ticket orchestration: notifications + WebSocket broadcasts.

Mirrors apps.alerts.services: single source of truth for ticket side-effects,
imported from views and Celery tasks so behavior stays consistent.
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.channels_utils import (
    broadcast_to_support_internal, broadcast_to_support_supplier,
)
from apps.common.notifications import NotificationContext, dispatch_notification

from .models import Ticket

logger = logging.getLogger(__name__)
User = get_user_model()


# --------------------------------------------------------------------------
# Recipients
# --------------------------------------------------------------------------

def _supplier_users(ticket: Ticket):
    """Whichever supplier was explicitly chosen for this ticket. No
    machine-based fallback — a ticket with no supplier assigned has no
    supplier recipient, matching the strict queryset scoping above."""
    if not ticket.assigned_supplier_id:
        return User.objects.none()
    return User.objects.filter(pk=ticket.assigned_supplier_id, is_active=True)


def _emails(users) -> list[str]:
    return [u.email for u in users if u.email]


def _supplier_recipients(ticket: Ticket) -> list[str]:
    return _emails(_supplier_users(ticket))


def _internal_users(ticket: Ticket) -> list:
    roles = ("ADMIN", "MANAGER", "MAINTENANCE")
    on_duty = list(User.objects.filter(role__in=roles, is_active=True, is_on_duty=True))
    return on_duty or list(User.objects.filter(role__in=roles, is_active=True))


def _internal_recipients(ticket: Ticket) -> list[str]:
    return _emails(_internal_users(ticket))


# --------------------------------------------------------------------------
# Broadcast helpers
# --------------------------------------------------------------------------

def _ws_type(event: str) -> str:
    return event.replace(".", "_")


def _base_payload(ticket: Ticket, event: str, extra: dict | None = None) -> dict:
    payload = {
        "type": _ws_type(event),
        "event": event,
        "ticket_id": ticket.pk,
        "ticket_number": ticket.ticket_number,
        "machine_id": ticket.machine_id,
        "machine_code": ticket.machine.code if ticket.machine_id else None,
        "criticality": ticket.criticality,
        "status": ticket.status,
        "ts": timezone.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def broadcast_ticket_event(ticket: Ticket, event: str, extra: dict | None = None) -> None:
    """Broadcast to internal staff + every supplier assigned to this ticket's machine."""
    payload = _base_payload(ticket, event, extra)
    broadcast_to_support_internal(payload)
    for supplier in _supplier_users(ticket):
        broadcast_to_support_supplier(supplier.id, payload)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

def _ticket_summary(ticket: Ticket) -> str:
    return (
        f"Ticket      : {ticket.ticket_number}\n"
        f"Machine     : {ticket.machine.code} — {ticket.machine.name}\n"
        f"Criticité   : {ticket.criticality}\n"
        f"Statut      : {ticket.status}\n"
        f"Description : {ticket.description or '—'}\n"
    )


def _ticket_ctx_kwargs(ticket: Ticket) -> dict:
    return dict(target_type="Ticket", target_id=ticket.pk, url=f"/support/{ticket.pk}")


def notify_ticket_created(ticket: Ticket) -> None:
    """Internal-only: a new ticket needs triage before it's routed to a
    supplier (see notify_ticket_assigned for the supplier-facing version)."""
    users = _internal_users(ticket)
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Nouveau ticket — {ticket.machine.code}",
        recipients=_emails(users),
        body=f"Nouveau ticket de support créé.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_ticket_assigned(ticket: Ticket) -> None:
    """Fired when a ticket moves NEW -> AWAITING_SUPPLIER: this is the
    supplier's "new ticket created" notification per the spec."""
    users = list(_supplier_users(ticket))
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Nouveau ticket assigné — {ticket.machine.code}",
        recipients=_emails(users),
        body=f"Un ticket vous a été assigné.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_diagnostic_available(ticket: Ticket) -> None:
    """Fired when the supplier starts diagnosis — spec's usine-side
    "Diagnostic disponible" notification."""
    users = _internal_users(ticket)
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Diagnostic disponible",
        recipients=_emails(users),
        body=f"Le fournisseur a démarré le diagnostic.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_new_media(ticket: Ticket, uploaded_by_supplier: bool) -> None:
    """Notify whichever side didn't upload the file — spec's "Ajout d'un
    nouveau média" notification (fournisseur side) and its usine-side
    mirror."""
    users = _internal_users(ticket) if uploaded_by_supplier else list(_supplier_users(ticket))
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Nouveau média ajouté",
        recipients=_emails(users),
        body=f"Un nouveau fichier a été ajouté au ticket.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_solution_proposed(ticket: Ticket) -> None:
    users = _internal_users(ticket)
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Solution proposée par le fournisseur",
        recipients=_emails(users),
        body=f"Le fournisseur a proposé une solution.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_validation_decision(ticket: Ticket, decision: str, reason: str = "") -> None:
    users = list(_supplier_users(ticket))
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Décision usine : {decision}",
        recipients=_emails(users),
        body=f"Décision de l'usine : {decision}\nMotif : {reason or '—'}\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_ticket_comment(ticket: Ticket) -> None:
    users = list(_supplier_users(ticket)) + _internal_users(ticket)
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Nouveau commentaire",
        recipients=_emails(users),
        body=f"Un nouveau commentaire a été ajouté.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_ticket_resolved(ticket: Ticket) -> None:
    users = list(_supplier_users(ticket)) + _internal_users(ticket)
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] Ticket résolu",
        recipients=_emails(users),
        body=f"Le ticket a été marqué résolu.\n\n{_ticket_summary(ticket)}",
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
    )
    dispatch_notification(ctx)


def notify_awaiting_supplier_reminder(ticket: Ticket) -> None:
    users = list(_supplier_users(ticket))
    ctx = NotificationContext(
        subject=f"[SAV {ticket.ticket_number}] RAPPEL — en attente du fournisseur",
        recipients=_emails(users),
        recipient_users=users, **_ticket_ctx_kwargs(ticket),
        body=(
            f"Ce ticket attend toujours une réponse du fournisseur.\n\n"
            f"{_ticket_summary(ticket)}"
        ),
    )
    dispatch_notification(ctx)
