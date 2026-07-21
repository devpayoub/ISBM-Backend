import logging
import time

logger = logging.getLogger("audit")


class AuditMiddleware:
    """Log authenticated requests for audit-trail purposes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = round((time.time() - start) * 1000, 2)

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            logger.info(
                "AUDIT user=%s method=%s path=%s status=%s duration=%sms",
                user.pk, request.method, request.path, response.status_code, duration,
            )
        return response
