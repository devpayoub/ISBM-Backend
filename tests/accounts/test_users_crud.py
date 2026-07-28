"""Tests for /api/v1/auth/users (UserViewSet) and the register action.

Permission gate: ``IsAdmin`` (apps/accounts/views.py:48) — only ADMIN can list,
create, update, delete users. The register action re-asserts IsAdmin too.
"""
import pytest

from apps.accounts.models import CustomUser, Role

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/auth/users"


def _new_user_payload(role="CONTROLLER", email=None):
    return {
        "email": email or f"new-{role.lower()}@isbm.local",
        "first_name": "New",
        "last_name": "User",
        "role": role,
        "shift": "MORNING",
        "phone": "+216 71 000 100",
        "password": "Test12345!",
        "password2": "Test12345!",
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def test_admin_lists_users(admin_client, make_user):
    for role in ["MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"]:
        make_user(role)
    resp = admin_client.get(USERS_URL)
    assert resp.status_code == 200
    body = resp.json()
    # Could be paginated or list — accept both shapes.
    rows = body.get("results", body) if isinstance(body, dict) else body
    roles = {u["role"] for u in rows}
    assert {"ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"} <= roles


@pytest.mark.parametrize("role", ["MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_non_admin_cannot_list_users(api_as, role):
    client = api_as(role)
    assert client.get(USERS_URL).status_code == 403


def test_unauthenticated_cannot_list_users(api):
    assert api.get(USERS_URL).status_code == 401


# ---------------------------------------------------------------------------
# Register (POST /users/register)
# ---------------------------------------------------------------------------
def test_admin_registers_user(admin_client):
    payload = _new_user_payload(role="MAINTENANCE")
    resp = admin_client.post(f"{USERS_URL}/register", payload, format="json")
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["role"] == "MAINTENANCE"
    assert CustomUser.objects.filter(email=payload["email"]).exists()


@pytest.mark.parametrize("role", ["MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_non_admin_register_forbidden(api_as, role):
    client = api_as(role)
    resp = client.post(f"{USERS_URL}/register", _new_user_payload(), format="json")
    assert resp.status_code == 403


def test_register_password_mismatch_400(admin_client):
    payload = _new_user_payload()
    payload["password2"] = "Different123!"
    resp = admin_client.post(f"{USERS_URL}/register", payload, format="json")
    assert resp.status_code == 400
    assert "password2" in resp.json()


def test_register_weak_password_400(admin_client):
    payload = _new_user_payload()
    payload["password"] = "123"
    payload["password2"] = "123"
    resp = admin_client.post(f"{USERS_URL}/register", payload, format="json")
    assert resp.status_code == 400


def test_register_duplicate_email_400(admin_client, make_user):
    existing = make_user("CONTROLLER", email="dup@isbm.local")
    payload = _new_user_payload(email=existing.email)
    resp = admin_client.post(f"{USERS_URL}/register", payload, format="json")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------
def test_admin_updates_user(admin_client, make_user):
    target = make_user("OPERATOR")
    resp = admin_client.patch(f"{USERS_URL}/{target.pk}", {"phone": "+216 22 333 444"},
                              format="json")
    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.phone == "+216 22 333 444"


def test_non_admin_update_forbidden(api_as, make_user):
    guest = api_as("OPERATOR")
    target = make_user("MANAGER")
    assert guest.patch(f"{USERS_URL}/{target.pk}", {"phone": "x"}, format="json").status_code == 403


def test_admin_deletes_user(admin_client, make_user):
    target = make_user("CONTROLLER", email="del@isbm.local")
    resp = admin_client.delete(f"{USERS_URL}/{target.pk}")
    assert resp.status_code == 204
    assert not CustomUser.objects.filter(pk=target.pk).exists()


@pytest.mark.parametrize("role", ["MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_non_admin_delete_forbidden(api_as, make_user, role):
    guest = api_as(role)
    target = make_user("CONTROLLER")
    assert guest.delete(f"{USERS_URL}/{target.pk}").status_code == 403


# ---------------------------------------------------------------------------
# Filters / search
# ---------------------------------------------------------------------------
def test_filter_by_role(admin_client):
    admin_client.post(f"{USERS_URL}/register", _new_user_payload(role="MAINTENANCE"),
                      format="json")
    admin_client.post(f"{USERS_URL}/register", _new_user_payload(role="MAINTENANCE",
                      email="b@isbm.local"), format="json")
    resp = admin_client.get(f"{USERS_URL}?role=MAINTENANCE")
    assert resp.status_code == 200
    rows = resp.json().get("results") or resp.json()
    assert rows and all(u["role"] == "MAINTENANCE" for u in rows)


def test_search_by_email(admin_client, make_user):
    make_user("MANAGER", email="marie.curie@isbm.local")
    resp = admin_client.get(f"{USERS_URL}?search=marie")
    assert resp.status_code == 200
    rows = resp.json().get("results") or resp.json()
    assert any("marie" in u["email"] for u in rows)
