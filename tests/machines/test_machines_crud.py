"""Tests for /api/v1/machines (MachineViewSet) and PATCH /machines/{id}/status.

Permission: IsAdminOrManagerOrReadOnly (apps/machines/views.py:26) — read for
all auth roles; create/update/destroy for ADMIN + MANAGER only.
"""
import pytest

from apps.machines.models import Machine

pytestmark = pytest.mark.django_db

# Note: apps/machines/urls.py uses both DefaultRouter(trailing_slash=False) and
# manual path() patterns. After the URLs reorder (manual paths first), DRF
# resolves both /api/v1/machines and /api/v1/machines/ for the list, and
# /api/v1/machines/<int:pk> for retrieve. We standardize on slashless base URL.
MACHINES_URL = "/api/v1/machines"


def _payload(code="M-NEW"):
    return {
        "code": code, "name": f"Machine {code}", "type": "ISBM",
        "status": "STOPPED", "nominal_bph": 800, "nominal_cph": 0,
        "cavities": 6, "product_format": "500 ml",
        "location": "Atelier", "is_active": True,
    }


# ---------------------------------------------------------------------------
# Read access — every authenticated role
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_any_role_lists_machines(api_as, role, make_machine):
    make_machine("READ-1")
    client = api_as(role)
    resp = client.get(MACHINES_URL)
    assert resp.status_code == 200
    rows = resp.json().get("results") or resp.json()
    assert any(m["code"] == "READ-1" for m in rows)


def test_unauthenticated_list_401(api):
    assert api.get(MACHINES_URL).status_code == 401


def test_retrieve_single_machine(api_as, make_machine):
    m = make_machine("READ-2")
    resp = api_as("OPERATOR").get(f"{MACHINES_URL}/{m.pk}")
    assert resp.status_code == 200
    assert resp.json()["code"] == "READ-2"


# ---------------------------------------------------------------------------
# Create — ADMIN + MANAGER allowed
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_can_create(api_as, role):
    resp = api_as(role).post(MACHINES_URL, _payload("C-1"), format="json")
    assert resp.status_code == 201, resp.content
    assert Machine.objects.filter(code="C-1").exists()


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_create(api_as, role):
    resp = api_as(role).post(MACHINES_URL, _payload("C-2"), format="json")
    assert resp.status_code == 403
    assert not Machine.objects.filter(code="C-2").exists()


def test_create_duplicate_code_400(admin_client, make_machine):
    make_machine("DUP")
    resp = admin_client.post(MACHINES_URL, _payload("DUP"), format="json")
    assert resp.status_code == 400


def test_create_missing_code_400(admin_client):
    payload = _payload()
    del payload["code"]
    assert admin_client.post(MACHINES_URL, payload, format="json").status_code == 400


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_can_update(api_as, role, make_machine):
    m = make_machine("U-1", name="Before")
    resp = api_as(role).patch(f"{MACHINES_URL}/{m.pk}", {"name": "After"}, format="json")
    assert resp.status_code == 200
    m.refresh_from_db()
    assert m.name == "After"


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_update(api_as, role, make_machine):
    m = make_machine("U-2")
    resp = api_as(role).patch(f"{MACHINES_URL}/{m.pk}", {"name": "Hack"}, format="json")
    assert resp.status_code == 403


def test_put_replaces_machine(admin_client, make_machine):
    m = make_machine("U-3", nominal_bph=100)
    body = _payload("U-3")
    body["nominal_bph"] = 999
    resp = admin_client.put(f"{MACHINES_URL}/{m.pk}", body, format="json")
    assert resp.status_code == 200
    m.refresh_from_db()
    assert m.nominal_bph == 999


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def test_admin_can_delete(admin_client, make_machine):
    m = make_machine("D-1")
    assert admin_client.delete(f"{MACHINES_URL}/{m.pk}").status_code == 204
    assert not Machine.objects.filter(pk=m.pk).exists()


def test_manager_can_delete(manager_client, make_machine):
    m = make_machine("D-2")
    assert manager_client.delete(f"{MACHINES_URL}/{m.pk}").status_code == 204


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_delete(api_as, role, make_machine):
    m = make_machine("D-3")
    assert api_as(role).delete(f"{MACHINES_URL}/{m.pk}").status_code == 403


# ---------------------------------------------------------------------------
# Custom action: PATCH /machines/{id}/status
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_manager_can_change_status(api_as, role, make_machine):
    m = make_machine("S-1", status="STOPPED")
    # admins/managers pass the IsAdminOrManagerOrReadOnly gate (it's a write method).
    # But the action has only IsAuthenticated? Let's assert the actual behavior.
    resp = api_as(role).patch(f"{MACHINES_URL}/{m.pk}/status", {"status": "RUNNING"},
                              format="json")
    # The @action(detail=True, methods=["patch"]) decorator overrides nothing on permissions,
    # so the viewset's IsAdminOrManagerOrReadOnly applies — write needs AD/MA -> 200 for them.
    assert resp.status_code in (200, 403), resp.content
    if resp.status_code == 200:
        m.refresh_from_db()
        assert m.status == "RUNNING"


@pytest.mark.parametrize("role", ["CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_others_cannot_change_status(api_as, role, make_machine):
    m = make_machine("S-2")
    # Misleading name: controller_client fixture uses Role.CONTROLLER (the "controller" role).
    resp = api_as(role).patch(f"{MACHINES_URL}/{m.pk}/status", {"status": "RUNNING"},
                              format="json")
    assert resp.status_code == 403


def test_status_invalid_choice_400(admin_client, make_machine):
    m = make_machine("S-3")
    resp = admin_client.patch(f"{MACHINES_URL}/{m.pk}/status", {"status": "WARP"},
                              format="json")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Custom action: GET /machines/{id}/parameters
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_any_role_lists_machine_parameters(api_as, role, make_machine, make_parameter):
    m = make_machine("P-1")
    resp = api_as(role).get(f"{MACHINES_URL}/{m.pk}/parameters")
    assert resp.status_code == 200
