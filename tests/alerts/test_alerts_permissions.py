"""Dedicated RBAC regression matrix — the executable authorization spec.

This file encodes the §2.2 table of the test plan as a single parametrized
test. It is the regression gate: any future role refactor (e.g. the 6-role
model in Plan_Back_Front_CRUD_ISBM.md) must keep this green or update here.

Limits: lifecycle actions (acknowledge/resolve/close/escalate) are out — those
need a specific alert state and are exercised in test_alerts_lifecycle.py.
Here we focus on read/create for each entity, which are the pure-RBAC paths.
"""
import pytest

pytestmark = pytest.mark.django_db

# (role, method, url, expected_status, marker)
# expected values use the rows in §2.2 of the plan.
# Read paths (GET) -> 200 for all authenticated roles on most list endpoints.
RBAC_MATRIX = [
    # ---- machines (read) ----
    ("ADMIN",       "GET", "/api/v1/machines",                200, None),
    ("MANAGER",     "GET", "/api/v1/machines",                200, None),
    ("CONTROLLER",  "GET", "/api/v1/machines",                200, None),
    ("MAINTENANCE", "GET", "/api/v1/machines",                200, None),
    ("OPERATOR",    "GET", "/api/v1/machines",                200, None),

    # ---- machines (create) ----
    ("ADMIN",       "POST", "/api/v1/machines",               201, None),
    ("MANAGER",     "POST", "/api/v1/machines",               201, None),
    ("CONTROLLER",  "POST", "/api/v1/machines",               403, None),
    ("MAINTENANCE", "POST", "/api/v1/machines",               403, None),
    ("OPERATOR",    "POST", "/api/v1/machines",               403, None),

    # ---- machines/parameters (read) ----
    ("OPERATOR",    "GET", "/api/v1/machines/parameters",     200, None),

    # ---- machines/parameters (create) — admins/managers get past gate but
    # serializer is read-only on `key` (unique+required on model) so the call
    # fails 400 with IntegrityError surfaced. We just assert it's not 403. ----
    ("ADMIN",       "POST", "/api/v1/machines/parameters",    400, "key_is_readonly"),
    ("MANAGER",     "POST", "/api/v1/machines/parameters",    400, "key_is_readonly"),
    ("CONTROLLER",  "POST", "/api/v1/machines/parameters",    403, None),
    ("MAINTENANCE", "POST", "/api/v1/machines/parameters",    403, None),
    ("OPERATOR",    "POST", "/api/v1/machines/parameters",    403, None),

    # ---- alerts (list) ----
    ("ADMIN",       "GET", "/api/v1/alerts",                  200, None),
    ("MANAGER",     "GET", "/api/v1/alerts",                  200, None),
    ("CONTROLLER",  "GET", "/api/v1/alerts",                  200, None),
    ("MAINTENANCE", "GET", "/api/v1/alerts",                  200, None),
    ("OPERATOR",    "GET", "/api/v1/alerts",                  200, None),

    # ---- alerts (declare) ----
    ("ADMIN",       "POST", "/api/v1/alerts",                  201, "needs_alert_data"),
    ("MANAGER",     "POST", "/api/v1/alerts",                  201, "needs_alert_data"),
    ("CONTROLLER",  "POST", "/api/v1/alerts",                  201, "needs_alert_data"),
    ("MAINTENANCE", "POST", "/api/v1/alerts",                  201, "needs_alert_data"),
    ("OPERATOR",    "POST", "/api/v1/alerts",                  403, "needs_alert_data"),

    # ---- alerts/categories (read) ----
    ("OPERATOR",    "GET", "/api/v1/alerts/categories",      200, None),

    # ---- alerts/categories (create) ----
    ("ADMIN",       "POST", "/api/v1/alerts/categories",      201, None),
    ("MANAGER",     "POST", "/api/v1/alerts/categories",      201, None),
    ("CONTROLLER",  "POST", "/api/v1/alerts/categories",      403, None),
    ("MAINTENANCE", "POST", "/api/v1/alerts/categories",      403, None),
    ("OPERATOR",    "POST", "/api/v1/alerts/categories",      403, None),

    # ---- users (list) ----
    ("ADMIN",       "GET", "/api/v1/auth/users",              200, None),
    ("MANAGER",     "GET", "/api/v1/auth/users",              403, None),
    ("CONTROLLER",  "GET", "/api/v1/auth/users",              403, None),
    ("MAINTENANCE", "GET", "/api/v1/auth/users",              403, None),
    ("OPERATOR",    "GET", "/api/v1/auth/users",              403, None),
]


def _machine_payload():
    return {
        "code": "RBAC-M", "name": "RBAC", "type": "ISBM",
        "status": "STOPPED", "nominal_bph": 100, "nominal_cph": 0,
        "cavities": 1, "is_active": True,
    }


def _param_payload():
    return {"label": "X", "value": "1.0", "unit": "", "category": "test"}


def _category_payload():
    return {
        "name": "Auto-cat", "code": "AUTO-CAT-RBAC",
        "severity_default": "MINOR", "requires_maintenance": False,
        "is_active": True,
    }


def _alert_payload(machine, category):
    return {
        "machine": machine.pk, "category": category.pk,
        "title": "RBAC", "description": "",
        "severity": "MAJOR", "worker_name": "T", "shift": "MORNING",
    }


@pytest.mark.parametrize("role,method,url,expected,marker", RBAC_MATRIX)
def test_rbac_matrix(api_as, role, method, url, expected, marker, make_machine, make_category):
    """Execute one row of the RBAC matrix. Markers tweak the payload to suit
    the endpoint (e.g. alerts need a machine+category)."""
    client = api_as(role)

    # Pick a body based on path so creation requests have valid fields.
    body = None
    if url == "/api/v1/machines" and method == "POST":
        body = _machine_payload()
    elif url == "/api/v1/machines/parameters" and method == "POST":
        body = _param_payload()
    elif url == "/api/v1/alerts/categories" and method == "POST":
        body = _category_payload()
    elif url == "/api/v1/alerts" and method == "POST" and marker == "needs_alert_data":
        body = _alert_payload(make_machine("RBAC-M"), make_category())

    # POST/CREATE usually requires JSON; GET doesn't.
    if method == "GET":
        resp = client.get(url)
    elif method == "POST":
        resp = client.post(url, body or {}, format="json")
    else:
        raise AssertionError(f"unsupported method {method}")

    msg = f"RBAC [{role} {method} {url}] expected {expected}, got {resp.status_code}"
    assert resp.status_code == expected, msg + f"\nbody={resp.content[:500]}"
