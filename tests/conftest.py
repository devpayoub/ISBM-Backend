"""Shared pytest fixtures for the ISBM test suite.

Conventions:
- Every test that touches the DB must use ``pytestmark = pytest.mark.django_db``
  (or ``@pytest.mark.django_db``) — pytest-django refuses DB access otherwise.
- Side effects (email/SMS/WebSocket broadcast) are silenced by the autouse
  ``no_external_calls`` fixture so tests never dial out SMTP/Twilio/Redis.
- Tests should NOT depend on ``seed_test`` having run; each fixture builds its
  own minimal state via the helpers in ``factories.py``.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CustomUser, Role
from tests.factories import (  # exposed as fixtures below
    make_alert as _make_alert,
    make_category as _make_category,
    make_machine as _make_machine,
    make_parameter as _make_parameter,
)

PASSWORD = "Test12345!"
ROLES = [Role.ADMIN, Role.MANAGER, Role.CONTROLLER, Role.MAINTENANCE, Role.OPERATOR]


# ---------------------------------------------------------------------------
# Autouse: silence every outbound side-effect (no SMTP / no Twilio / no
# Channels broadcast).
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch, settings):
    # Email lands in an in-memory list instead of dialing SMTP.
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    # Twilio module-level no-op (apps/alerts/sms.py:send_sms is the only call site).
    import apps.alerts.sms as sms_mod
    monkeypatch.setattr(sms_mod, "send_sms", lambda *a, **k: None, raising=False)

    # Service-level notifications (imported by apps/alerts/views.py).
    import apps.alerts.services as svc
    for fn_name in ("broadcast_alert_event", "notify_alert_created", "notify_escalation"):
        monkeypatch.setattr(svc, fn_name, lambda *a, **k: None, raising=False)

    # Channels broadcast helper used by apps/machines/views.py:49 — no Redis conn.
    import apps.common.channels_utils as chans
    monkeypatch.setattr(chans, "broadcast_to_alerts_group", lambda *a, **k: None, raising=False)

    # ``transaction.on_commit`` callbacks (machines broadcast) — run them now
    # so the (mocked) broadcast doesn't queue until transaction end.
    from django.db import transaction
    original_on_commit = transaction.on_commit

    def _immediate(func, *args, **kwargs):
        if callable(func):
            try:
                func(*args, **kwargs)
            except Exception:
                pass
        return None

    monkeypatch.setattr(transaction, "on_commit", _immediate, raising=False)


# ---------------------------------------------------------------------------
# User fixtures — one per role, always on-duty unless explicit off-duty.
# ---------------------------------------------------------------------------
def _make_user(role, on_duty=True, email=None, first_name=None):
    role_value = role if isinstance(role, str) else role.value
    email = email or f"{role_value.lower()}.test@isbm.local"
    user, _ = CustomUser.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name or role_value.title(),
            "last_name": "Test",
            "role": role_value,
            "is_on_duty": on_duty,
            "shift": "MORNING",
        },
    )
    # Refresh to be idempotent with whatever the test did before.
    user.role = role_value
    user.is_on_duty = on_duty
    user.set_password(PASSWORD)
    user.save()
    return user


@pytest.fixture
def make_user(db):
    """Factory: ``make_user(Role.ADMIN)`` or ``make_user("OPERATOR")``."""
    return _make_user


@pytest.fixture
def admin_user(db):      return _make_user(Role.ADMIN)
@pytest.fixture
def manager_user(db):     return _make_user(Role.MANAGER)
@pytest.fixture
def controller_user(db):  return _make_user(Role.CONTROLLER)
@pytest.fixture
def maintenance_user(db): return _make_user(Role.MAINTENANCE)
@pytest.fixture
def operator_user(db):    return _make_user(Role.OPERATOR)
@pytest.fixture
def offduty_controller(db):
    return _make_user(
        Role.CONTROLLER,
        on_duty=False,
        email="controller.offduty@isbm.local",
        first_name="Offduty",
    )


# ---------------------------------------------------------------------------
# Authenticated API client factory: ``api_as("ADMIN").get("/api/v1/...")``
# ---------------------------------------------------------------------------
def _bearer(user) -> str:
    return str(RefreshToken.for_user(user).access_token)


@pytest.fixture
def api():
    """Unauthenticated DRF client."""
    return APIClient()


@pytest.fixture
def api_as(db):
    """Return a callable ``api_as(role)`` producing an authenticated APRIClient.

    Accepts a Role enum or a role string ("ADMIN", "MANAGER", ...).
    """
    def _make(role):
        role_value = role if isinstance(role, str) else role.value
        user = _make_user(role_value)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {_bearer(user)}")
        client.user = user  # convenience for tests that need the actor
        return client
    return _make


@pytest.fixture
def admin_client(api_as):       return api_as(Role.ADMIN)
@pytest.fixture
def manager_client(api_as):     return api_as(Role.MANAGER)
@pytest.fixture
def controller_client(api_as):  return api_as(Role.CONTROLLER)
@pytest.fixture
def maintenance_client(api_as): return api_as(Role.MAINTENANCE)
@pytest.fixture
def operator_client(api_as):    return api_as(Role.OPERATOR)


# ---------------------------------------------------------------------------
# Settings helper — fast password hasher in tests.
# ---------------------------------------------------------------------------
@pytest.fixture
def fast_password_hasher(settings):
    """Use the MD5 password hasher to keep ``set_password`` cheap in tests."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# ---------------------------------------------------------------------------
# Factory fixtures — each test file uses ``make_machine``, ``make_category``,
# ``make_alert``, ``make_parameter`` as injected fixtures that build isolated
# DB rows via the helpers in tests/factories.py.
# ---------------------------------------------------------------------------
@pytest.fixture
def make_machine(db):
    return _make_machine


@pytest.fixture
def make_category(db):
    return _make_category


@pytest.fixture
def make_alert(db):
    return _make_alert


@pytest.fixture
def make_parameter(db):
    return _make_parameter
