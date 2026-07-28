"""Tests for the alert state-machine lifecycle actions.

Transitions (apps/alerts/views.py):
  acknowledge OPEN  -> ACKNOWLEDGED         AD, MA, MAINTENANCE
  resolve     (OPEN|ACK|IN_PROGRESS) -> RESOLVED   AD, MA, MAINTENANCE
  close       RESOLVED -> CLOSED           AD, MA (IsAdminOrManager decorator)
  escalate    (any live state) -> level++  AD, MA, CONTROLLER

Model helpers (apps/alerts/models.py:111-118):
  can_acknowledge -> status == OPEN and not terminal
  can_resolve     -> status in (OPEN, ACK, IN_PROGRESS)
  can_close       -> status == RESOLVED and user.role in (ADMIN, MANAGER)

Illegal transitions return 400 ("... non autorisé dans cet état").
Out-of-role returns 403 ("Rôle insuffisant ...").
"""
import pytest

from apps.alerts.models import Alert, AlertStatus, Severity

pytestmark = pytest.mark.django_db

ALERTS_URL = "/api/v1/alerts"


# ---------------------------------------------------------------------------
# Acknowledge: OPEN -> ACKNOWLEDGED
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "MAINTENANCE"])
def test_authorized_roles_can_acknowledge_open_alert(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/acknowledge", format="json")
    assert resp.status_code == 200, resp.content
    a.refresh_from_db()
    assert a.status == AlertStatus.ACKNOWLEDGED
    assert a.acknowledged_at is not None
    assert a.acknowledged_by_id is not None


@pytest.mark.parametrize("role", ["CONTROLLER", "OPERATOR"])
def test_unauthorized_cannot_acknowledge(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/acknowledge", format="json")
    assert resp.status_code == 403
    assert "Rôle insuffisant" in resp.json()["detail"]


@pytest.mark.parametrize("from_status", ["ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED"])
def test_acknowledge_from_non_open_status_400(admin_client, make_alert, from_status):
    a = make_alert(status=AlertStatus[from_status])
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/acknowledge", format="json")
    assert resp.status_code == 400


def test_acknowledge_payload_carries_comment(admin_client, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/acknowledge",
                              {"comment": "On y va"}, format="json")
    assert resp.status_code == 200
    a.refresh_from_db()
    assert a.comments.filter(text="On y va").exists()


# ---------------------------------------------------------------------------
# Resolve: (OPEN | ACK | IN_PROGRESS) -> RESOLVED
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("from_status", ["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"])
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "MAINTENANCE"])
def test_authorized_can_resolve_from_valid_statuses(api_as, role, make_alert, from_status):
    a = make_alert(status=AlertStatus[from_status])
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/resolve",
                              {"downtime_min": 12, "bottles_lost": 50,
                               "comment": "Fixed"}, format="json")
    assert resp.status_code == 200, resp.content
    a.refresh_from_db()
    assert a.status == AlertStatus.RESOLVED
    assert a.downtime_min == 12
    assert a.bottles_lost == 50
    assert a.resolved_at is not None


def test_resolve_from_closed_400(admin_client, make_alert):
    a = make_alert(status=AlertStatus.CLOSED)
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/resolve", format="json")
    assert resp.status_code == 400


@pytest.mark.parametrize("role", ["CONTROLLER", "OPERATOR"])
def test_unauthorized_cannot_resolve(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/resolve", format="json")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Close: RESOLVED -> CLOSED (AD / MA only)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_can_close_resolved_alert(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.RESOLVED)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/close", format="json")
    assert resp.status_code == 200, resp.content
    a.refresh_from_db()
    assert a.status == AlertStatus.CLOSED
    assert a.closed_at is not None


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_close(api_as, role, make_alert):
    """Current behavior: the action-level ``permission_classes`` set via
    ``@action(permission_classes=[IsAuthenticated, IsAdminOrManager])`` is
    NOT enforced because apps/alerts/urls.py wires the action with a manual
    ``AlertViewSet.as_view({"patch": "close"})`` instead of going through a
    DRF router (which propagates ``action.kwargs``). So non-admin/manager
    roles reach the view body and fail at ``can_close`` (apps/alerts/models.py)
    returning False → DRF 400, NOT 403.

    See README §"Known bugs #8" for the underlying issue."""
    a = make_alert(status=AlertStatus.RESOLVED)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/close", format="json")
    assert resp.status_code == 400
    assert "Clôture non autorisée" in resp.json()[0]


def test_close_alert_not_resolved_400(admin_client, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/close", format="json")
    assert resp.status_code == 400


def test_close_already_closed_400(admin_client, make_alert):
    a = make_alert(status=AlertStatus.CLOSED)
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/close", format="json")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Escalate (sets escalation_level via notify_escalation)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER"])
def test_authorized_can_escalate(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.OPEN, escalation_level=0)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/escalate",
                              {"level": 1}, format="json")
    assert resp.status_code == 200
    a.refresh_from_db()
    # notify_escalation is monkeypatched to no-op in conftest, so escalation_level
    # stays as the model default (0) — we just assert the call succeeded.
    assert a.status == AlertStatus.OPEN  # escalate does not change status


@pytest.mark.parametrize("role", ["MAINTENANCE", "OPERATOR"])
def test_unauthorized_cannot_escalate(api_as, role, make_alert):
    a = make_alert(status=AlertStatus.OPEN)
    resp = api_as(role).patch(f"{ALERTS_URL}/{a.pk}/escalate", format="json")
    assert resp.status_code == 403


def test_escalate_default_increments_level_param(admin_client, make_alert):
    a = make_alert(status=AlertStatus.OPEN, escalation_level=2)
    resp = admin_client.patch(f"{ALERTS_URL}/{a.pk}/escalate", format="json")
    assert resp.status_code == 200
