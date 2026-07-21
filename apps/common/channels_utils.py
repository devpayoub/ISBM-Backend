import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

ALERTS_GROUP = "alerts"


def broadcast_to_alerts_group(message: dict) -> None:
    """Send a message to the "alerts" Channels group (floor screens + dashboards).

    The message MUST include a `type` key matching a consumer method name
    (e.g. "alert.created", "alert.created" -> "alert_created"; see AlertConsumer).
    """
    layer = get_channel_layer()
    if layer is None:
        logger.warning("Channels layer is not configured; skipping broadcast.")
        return
    try:
        async_to_sync(layer.group_send)(ALERTS_GROUP, message)
    except Exception as exc:
        logger.warning("channel broadcast failed: %s", exc)
