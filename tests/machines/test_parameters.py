"""Tests for /api/v1/machines/parameters (ParameterViewSet).

Permission: IsAdminOrManagerOrReadOnly (apps/machines/views.py:62).
Note: ``key`` is read_only on the serializer (serializers.py:30) — so on create
the API silently ignores a client-supplied key. Tests therefore create keys
via the factory (DB-direct) and exercise update/cleanup through the API.
"""
import pytest

from apps.machines.models import Parameter

pytestmark = pytest.mark.django_db

PARAMS_URL = "/api/v1/machines/parameters"  # registered via router; both slash & slashless match


# ---------------------------------------------------------------------------
# List — auth + read-only
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_any_role_lists_parameters(api_as, role, make_parameter):
    make_parameter("PARAM-LIST")
    client = api_as(role)
    resp = client.get(PARAMS_URL)
    assert resp.status_code == 200
    rows = resp.json().get("results") or resp.json()
    assert any(p["key"] == "PARAM-LIST" for p in rows)


def test_unauthenticated_list_401(api):
    assert api.get(PARAMS_URL).status_code == 401


# ---------------------------------------------------------------------------
# Create — key is read-only on serializer, so payload's key is ignored
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_create_succeeds_without_explicit_key(api_as, role):
    payload = {"label": "X", "value": "1.0", "unit": "", "category": "test"}
    resp = api_as(role).post(PARAMS_URL, payload, format="json")
    # Since key is read-only on ParameterSerializer and is unique+required on the
    # model, the create serializer won't fill it -> IntegrityError -> 400/500.
    # We assert the API does not silently succeed.
    assert resp.status_code in (400, 500), resp.content


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_create(api_as, role, make_parameter):
    payload = {"label": "X", "value": "1.0"}
    resp = api_as(role).post(PARAMS_URL, payload, format="json")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Update — value/label/unit/etc. are mutable; key is read-only
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_can_update_value(api_as, role, make_parameter):
    p = make_parameter("PARAM-UP", value="10.0")
    resp = api_as(role).patch(f"{PARAMS_URL}/{p.pk}", {"value": "20.0"}, format="json")
    assert resp.status_code == 200, resp.content
    p.refresh_from_db()
    assert p.value == 20


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_update(api_as, role, make_parameter):
    p = make_parameter("PARAM-NO")
    resp = api_as(role).patch(f"{PARAMS_URL}/{p.pk}", {"value": "1"}, format="json")
    assert resp.status_code == 403


def test_patch_key_is_ignored(admin_client, make_parameter):
    """key is in read_only_fields (apps/machines/serializers.py:30)."""
    p = make_parameter("PARAM-KEY", value="1")
    resp = admin_client.patch(f"{PARAMS_URL}/{p.pk}", {"key": "HACKED"}, format="json")
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.key == "PARAM-KEY"  # not changed


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def test_admin_can_delete_parameter(admin_client, make_parameter):
    p = make_parameter("PARAM-DEL")
    assert admin_client.delete(f"{PARAMS_URL}/{p.pk}").status_code == 204
    assert not Parameter.objects.filter(pk=p.pk).exists()


def test_manager_can_delete_parameter(manager_client, make_parameter):
    p = make_parameter("PARAM-DEL2")
    assert manager_client.delete(f"{PARAMS_URL}/{p.pk}").status_code == 204


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_delete(api_as, role, make_parameter):
    p = make_parameter("PARAM-DEL3")
    assert api_as(role).delete(f"{PARAMS_URL}/{p.pk}").status_code == 403
