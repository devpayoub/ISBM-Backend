from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model



class AlertConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time alerts on floor screens.

    URL: ws/alerts/?token=<JWT>
    All connected clients are added to the "alerts" group and receive every
    alert lifecycle event broadcast via `broadcast_to_alerts_group`.
    """

    GROUP = "alerts"

    async def connect(self):
        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)
            return
        self.user = user
        await self.accept()
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.send_json({"event": "socket.connected", "user": user.email})

    async def disconnect(self, code):
        if hasattr(self, "user"):
            try:
                await self.channel_layer.group_discard(self.GROUP, self.channel_name)
            except Exception:
                pass

    # --- inbound ----------------------------------------------------------
    async def receive_json(self, content, **kwargs):
        action = (content.get("action") or "").strip().lower()
        if action == "ping":
            await self.send_json({"event": "pong"})
        else:
            await self.send_json({"event": "ack", "echo": content})

    # --- group dispatchers (one per event type) ---------------------------
    async def alert_created(self, event):
        await self.send_json({
            "event": "alert.created",
            "alert_id": event.get("alert_id"),
            "machine_code": event.get("machine_code"),
            "machine_name": event.get("machine_name"),
            "title": event.get("title"),
            "severity": event.get("severity"),
            "status": event.get("status"),
            "ts": event.get("ts"),
        })

    async def alert_acknowledged(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def alert_resolved(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def alert_closed(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def alert_escalated(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def alert_commented(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def machine_status_changed(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    # --- auth -------------------------------------------------------------
    @database_sync_to_async
    def _authenticate(self):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from urllib.parse import parse_qs

        query = self.scope.get("query_string", b"").decode()
        parsed = parse_qs(query)
        token = parsed.get("token", [None])[0]

        if not token:
            token = next(
                (h.decode().split(" ", 1)[1] for h in self.scope.get("headers", [])
                 if h[0] == b"authorization" and b"Bearer" in h),
                None,
            )

        if not token:
            return None
        try:
            access = AccessToken(token)
            User = get_user_model()
            return User.objects.filter(pk=access["user_id"]).first()
        except (InvalidToken, TokenError, Exception):
            return None
