"""Tests for /api/v1/alerts/{id}/comments endpoint (POST).

apps/alerts/views.py:119 only requires IsAuthenticated — any logged-in user
may comment on any alert. (Read of comments is via the alert serializer.)
"""
import pytest

from apps.alerts.models import AlertComment

pytestmark = pytest.mark.django_db

ALERTS_URL = "/api/v1/alerts"


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_any_role_can_comment(api_as, role, make_alert):
    a = make_alert()
    resp = api_as(role).post(f"{ALERTS_URL}/{a.pk}/comments", {"text": "Hello"}, format="json")
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["text"] == "Hello"
    assert AlertComment.objects.filter(alert=a, text="Hello").exists()


def test_comment_empty_text_400(admin_client, make_alert):
    a = make_alert()
    resp = admin_client.post(f"{ALERTS_URL}/{a.pk}/comments", {"text": "   "}, format="json")
    assert resp.status_code == 400
    assert not AlertComment.objects.filter(alert=a).exists()


def test_comment_missing_text_400(admin_client, make_alert):
    a = make_alert()
    resp = admin_client.post(f"{ALERTS_URL}/{a.pk}/comments", {}, format="json")
    assert resp.status_code == 400


def test_unauthenticated_comment_401(api, make_alert):
    a = make_alert()
    resp = api.post(f"{ALERTS_URL}/{a.pk}/comments", {"text": "x"}, format="json")
    assert resp.status_code == 401


def test_comment_on_nonexistent_alert_404(admin_client):
    resp = admin_client.post(f"{ALERTS_URL}/9999999/comments", {"text": "x"}, format="json")
    assert resp.status_code == 404
