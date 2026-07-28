from __future__ import annotations

from .models import ActivityLog


def log_activity(user, action: str, target_type: str = "", target_id: int | None = None, detail: str = "") -> None:
    """Record a single business-meaningful event. Never raises — a logging
    failure must not break the action it's recording."""
    try:
        ActivityLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    except Exception:
        pass
