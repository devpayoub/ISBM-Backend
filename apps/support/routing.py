from django.urls import re_path

from .consumers import SupportConsumer

websocket_urlpatterns = [
    re_path(r"^ws/support/$", SupportConsumer.as_asgi()),
]
