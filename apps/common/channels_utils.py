import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

ALERTS_GROUP = "alerts"
SUPPORT_INTERNAL_GROUP = "support_internal"


def _group_send(group: str, message: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        logger.warning("Channels layer is not configured; skipping broadcast.")
        return
    try:
        async_to_sync(layer.group_send)(group, message)
    except Exception as exc:
        logger.warning("channel broadcast failed: %s", exc)


def broadcast_to_alerts_group(message: dict) -> None:
    """Send a message to the "alerts" Channels group (floor screens + dashboards).

    The message MUST include a `type` key matching a consumer method name
    (e.g. "alert.created", "alert.created" -> "alert_created"; see AlertConsumer).
    """
    _group_send(ALERTS_GROUP, message)


def broadcast_to_support_internal(message: dict) -> None:
    """Broadcast a SAV ticket event to all internal staff (one shared group,
    same trust model as ALERTS_GROUP — everyone in it is an employee)."""
    _group_send(SUPPORT_INTERNAL_GROUP, message)


def broadcast_to_support_supplier(user_id: int, message: dict) -> None:
    """Send a SAV ticket event to a *single* supplier's personal group.

    Unlike the alerts/internal groups, supplier events are never broadcast to
    a shared group: a supplier account must never receive another supplier's
    ticket data, even over the socket, so each supplier gets its own group
    and the caller resolves exactly which supplier(s) should be notified.
    """
    _group_send(f"support_supplier_{user_id}", message)
