"""Optional SMS sending via Twilio. Stays a no-op if credentials are not set."""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(to: list[str], body: str) -> None:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.info("SMS non configuré — message ignoré: %s", body)
        return

    try:
        from twilio.rest import Client
    except ImportError:
        logger.warning("twilio n'est pas installé; SMS ignoré: %s", body)
        return

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    for number in to:
        if not number:
            continue
        try:
            client.messages.create(body=body, from_=settings.TWILIO_FROM_NUMBER, to=number)
        except Exception as exc:
            logger.error("SMS Twilio échoué vers %s: %s", number, exc)
