from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model


class SupportConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time SAV ticket updates.

    URL: ws/support/?token=<JWT>

    Internal staff (ADMIN/MANAGER/CONTROLLER/MAINTENANCE/OPERATOR) join one
    shared "support_internal" group, same broad-broadcast trust model as
    AlertConsumer. A SUPPLIER instead joins a personal group scoped to their
    own user id (`support_supplier_<id>`) — never the shared group — so a
    supplier's browser can never receive another supplier's ticket data over
    the socket, matching the server-side queryset scoping in TicketViewSet.
    """

    INTERNAL_GROUP = "support_internal"

    async def connect(self):
        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)
            return
        self.user = user
        self.group = (
            f"support_supplier_{user.id}" if user.role == "SUPPLIER" else self.INTERNAL_GROUP
        )
        await self.accept()
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.send_json({"event": "socket.connected", "user": user.email})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            try:
                await self.channel_layer.group_discard(self.group, self.channel_name)
            except Exception:
                pass

    async def receive_json(self, content, **kwargs):
        action = (content.get("action") or "").strip().lower()
        if action == "ping":
            await self.send_json({"event": "pong"})
        else:
            await self.send_json({"event": "ack", "echo": content})

    # --- group dispatchers (one per event type) ---------------------------
    async def ticket_created(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_assigned(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_status_changed(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_solution_proposed(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_commented(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_attachment_added(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    async def ticket_closed(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    # --- auth (identical pattern to AlertConsumer) -------------------------
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
