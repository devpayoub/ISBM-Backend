import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from apps.alerts.routing import websocket_urlpatterns as alerts_websocket_urlpatterns
from apps.support.routing import websocket_urlpatterns as support_websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(URLRouter(
        alerts_websocket_urlpatterns + support_websocket_urlpatterns
    )),
})
