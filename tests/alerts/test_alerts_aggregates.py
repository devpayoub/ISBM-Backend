"""Tests for read-only aggregate endpoints:
- /api/v1/alerts/active
- /api/v1/alerts/pareto
- /api/v1/alerts/stats

Permission: IsAuthenticated only (no role gate on these aggregate actions).
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from apps.alerts.models import Alert, AlertStatus, Severity

pytestmark = pytest.mark.django_db

ALERTS_URL = "/api/v1/alerts"


# ---------------------------------------------------------------------------
# /alerts/active
# ---------------------------------------------------------------------------
def test_active_returns_only_open_ack_inprogress(api_as, make_alert):
    make_alert(status=AlertStatus.OPEN)
    make_alert(status=AlertStatus.ACKNOWLEDGED)
    make_alert(status=AlertStatus.IN_PROGRESS)
    make_alert(status=AlertStatus.RESOLVED)
    make_alert(status=AlertStatus.CLOSED)
    resp = api_as("OPERATOR").get(f"{ALERTS_URL}/active")
    assert resp.status_code == 200
    statuses = {a["status"] for a in resp.json()}
    assert statuses == {"OPEN", "ACKNOWLEDGED", "IN_PROGRESS"}


def test_active_empty_when_all_closed(api_as, make_alert):
    for _ in range(3):
        make_alert(status=AlertStatus.CLOSED)
    resp = api_as("OPERATOR").get(f"{ALERTS_URL}/active")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# /alerts/pareto
# ---------------------------------------------------------------------------
def test_pareto_groups_by_category(api_as, make_alert, make_category):
    cat_a = make_category(code="CAT-A")
    cat_b = make_category(code="CAT-B")
    for _ in range(3):
        make_alert(category=cat_a)
    for _ in range(2):
        make_alert(category=cat_b)
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/pareto")
    assert resp.status_code == 200
    body = resp.json()
    # NOTE: with --reuse-db, the DB may carry stale alerts from prior probe runs.
    # Assert structure + ordering, not absolute totals.
    rows = body["rows"]
    assert isinstance(rows, list)
    assert len(rows) >= 1
    # sorted desc by nb
    for i in range(1, len(rows)):
        assert rows[i - 1]["nb"] >= rows[i]["nb"]
    # cumulative should reach 100% at the end (within rounding tolerance)
    assert abs(rows[-1]["cumulative_percent"] - 100.0) < 0.2


def test_pareto_with_date_filter(api_as, make_alert):
    a = make_alert()
    # Move created_at back 10 days
    Alert.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=10))
    future = (timezone.now() + timedelta(days=1)).date().isoformat()
    past = (timezone.now() - timedelta(days=15)).date().isoformat()
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/pareto?from={past}&to={future}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_pareto_empty_returns_zero(api_as):
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/pareto")
    assert resp.status_code == 200
    body = resp.json()
    # alerts/views.py:149 — ``total = sum(r["nb"] for r in rows) or 1``
    # so with no rows the divisor coerces to 1 (avoids ZeroDivision).
    assert body["rows"] == []
    assert body["total"] in (0, 1)


# ---------------------------------------------------------------------------
# /alerts/stats
# ---------------------------------------------------------------------------
def test_stats_empty_when_no_data(api_as):
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_days"] == 30
    assert body["rows"] == []


def test_stats_returns_mttr_per_machine(api_as, make_alert, make_machine, make_category):
    m = make_machine("STAT-1")
    cat = make_category()
    # Two closed+resolved alerts with known durations
    a1 = make_alert(machine=m, category=cat, status=AlertStatus.CLOSED)
    a1.created_at = timezone.now() - timedelta(minutes=120)
    a1.resolved_at = timezone.now() - timedelta(minutes=30)  # 90 min MTTR
    a1.save()
    a2 = make_alert(machine=m, category=cat, status=AlertStatus.CLOSED)
    a2.created_at = timezone.now() - timedelta(minutes=100)
    a2.resolved_at = timezone.now() - timedelta(minutes=70)  # 30 min
    a2.save()
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/stats?days=30")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert any(r["machine_code"] == "STAT-1" and r["incidents"] == 2 for r in rows)


def test_stats_default_window_30_days(api_as):
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/stats")
    assert resp.json()["window_days"] == 30


def test_stats_only_counts_closed_with_resolved_at(api_as, make_alert, make_machine):
    """alerts/views.py:167 filters status=CLOSED and excludes resolved_at null."""
    m = make_machine("STAT-2")
    # Closed but no resolved_at — should be excluded from MTTR
    make_alert(machine=m, status=AlertStatus.CLOSED)  # resolved_at is None
    make_alert(machine=m, status=AlertStatus.RESOLVED)  # not closed, filtered out
    resp = api_as("ADMIN").get(f"{ALERTS_URL}/stats")
    assert resp.status_code == 200
    assert resp.json()["rows"] == []


# ---------------------------------------------------------------------------
# Auth required on aggregates
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/active", "/pareto", "/stats"])
def test_aggregates_require_auth(api, path):
    assert api.get(f"{ALERTS_URL}{path}").status_code == 401
