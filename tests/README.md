# ISBM Backend — Test Suite

Role-aware pytest suite for the ISBM Backend (Phase 1+2: `accounts`, `machines`,
`alerts`). Targets the **5-role model** actually present in code
(`ADMIN / MANAGER / CONTROLLER / MAINTENANCE / OPERATOR`).

## Layout

```
Backend/
├── tests/
│   ├── conftest.py             fixtures: api_as(role), no_external_calls (autouse)
│   ├── factories.py            make_machine / make_category / make_alert / make_parameter
│   ├── accounts/               test_auth.py · test_users_crud.py
│   ├── machines/               test_machines_crud.py · test_parameters.py
│   └── alerts/                 test_alerts_crud.py · test_alerts_lifecycle.py
│                               test_alerts_comments.py · test_alerts_aggregates.py
│                               test_alerts_permissions.py  ← RBAC matrix spec
├── pytest.ini                  --reuse-db + strict config + markers
├── .coveragerc                 coverage on accounts/alerts/machines/common
└── apps/machines/management/commands/seed_test.py   optional idempotent seed
```

Tests build their **own** state via `tests/factories.py` — they do **not**
require `seed_test` to have been run. The command is provided as a debugging
aid for manual API exploration with stable credentials.

## Quick start (Docker Compose)

```bash
# 1. Build & start the whole stack
docker compose up -d db redis web worker beat

# 2. Install dev dependencies inside the web container
docker compose exec web pip install -r requirements/dev.txt

# 3. Run migrations (only required once per fresh DB)
docker compose exec web python manage.py migrate

# 4. Run the suite
docker compose exec web pytest tests/ -v --maxfail=1
```

## Coverage

```bash
docker compose exec web coverage run -m pytest tests/
docker compose exec web coverage report -m
# optional HTML report:
docker compose exec web coverage html && open coverage_html/index.html
```

Target ≥85% on `apps/{accounts,alerts,machines,common}`.

## Roles & test users

| Role | CLI string | On-duty fixture | Notes |
|---|---|---|---|
| Admin | `"ADMIN"` | `admin_user` / `admin_client` | full access |
| Manager | `"MANAGER"` | `manager_user` / `manager_client` | users read-only; alerts close |
| Controller | `"CONTROLLER"` | `controller_user` / `controller_client` | declares + escalates alerts |
| Maintenance | `"MAINTENANCE"` | `maintenance_user` / `maintenance_client` | acks/resolves alerts |
| Operator | `"OPERATOR"` | `operator_user` / `operator_client` | read-only on alerts |
| Off-duty controller | `"CONTROLLER"` | `offduty_controller` | documents on-duty bug |

All role fixtures auto-rebuild fresh isolated state for every test via
the factory in `conftest.py:_make_user`. Password is `Test12345!`.

Common helper:

```python
def my_test(api_as, make_machine):
    resp = api_as("ADMIN").post("/api/v1/machines", {...}, format="json")
    assert resp.status_code == 201
```

## Side-effect isolation

`tests/conftest.py:no_external_calls` (autouse) patches:

- `apps.alerts.services.broadcast_alert_event`  — no Channels/Redis publish
- `apps.alerts.services.notify_alert_created`  — no email/SMS send
- `apps.alerts.services.notify_escalation`     — no email/SMS send
- `apps.alerts.sms.send_sms`                   — Twilio no-op
- `apps.common.channels_utils.broadcast_to_alerts_group` — no Redis
- `django.db.transaction.on_commit`            — runs callbacks immediately
- `settings.EMAIL_BACKEND` → `locmem`          — emails stay in memory

There are **zero outbound SMTP/Twilio/Redis calls** during tests.

## Known transient markers

| Marker | Reason |
|---|---|
| `@pytest.mark.xfail` on `test_offduty_controller_can_still_declare_documented_bug` | `apps/alerts/views.py:55` has an empty `if not is_on_duty` block — on-duty gate is a no-op. Currently XPASS (test passes = bug confirmed). When the gate is fixed to enforce 403, it will become a real XFAIL and force the regression to be acknowledged. |
| `@pytest.mark.xfail` on `test_non_admin_delete_alert_should_be_forbidden_but_currently_succeeds` | `apps/alerts/views.py:38` viewset permission is `IsAuthenticated` only, and `destroy` has no `@action` override → any authenticated role can delete any alert. XFAIL because the expected 403 actually returns 204 (the bug). |

## Bugs discovered during test execution

These surface from the tests themselves — none are assertions added to "find" them; they were hit by real API calls.

| # | File | Resolve type | Symptom | Note |
|---|---|---|---|---|
| 1 | `apps/alerts/views.py:55` | code | `if not user.is_on_duty: pass` is a no-op — off-duty controllers can still declare alerts. | XPASS-marked test pins this; fix will flip to real failure. |
| 5 | `apps/alerts/views.py:38` | code | `destroy` action has no role gate; any authenticated user can DELETE any alert. | XFAIL-marked parametrized test pins this. |
| 6 | `apps/alerts/sms.py` | config | Twilio import is lazy so no-op when env vars are empty — non-issue, asserted via `no_external_calls`. | No code change needed. |
| 7 | `apps/machines/urls.py`, `apps/alerts/urls.py` | **FIXED in this PR** | The manual `MachineViewSet.as_view(...)` patterns came AFTER `path("", include(router.urls))`, so the router's API-root view silently shadowed the machine/alert list endpoints — `GET /api/v1/machines/` was returning `{"parameters": "..."}` (router link dict) instead of the machine list. | Reordered: manual paths FIRST, router include LAST. No view behaviour changed. |
| 8 | `apps/alerts/urls.py` (lines that register `acknowledge/resolve/close/escalate`) | code | The manual URL wiring `AlertViewSet.as_view({"patch": "close"})` doesn't pass the action's `permission_classes` kwarg (only DRF's router does). Result: action-level `permission_classes=[IsAuthenticated, IsAdminOrManager]` on `@action(...)` is **silently bypassed** — `close` and similar actions fall back to the viewset-level `IsAuthenticated`. Roles are then enforced only by the model helpers (`can_acknowledge`, `can_close`), which raise `ValidationError` (HTTP 400, not 403). | Tests assert the actual 400 behaviour (not a fictional 403). Fix would be either to route via `DefaultRouter` or to pass `permission_classes` explicitly via `as_view({"patch": "close"}, **action_kwargs)`. |

## Adding a new module test (recipe)

1. Create `tests/<module>/__init__.py` and `tests/<module>/test_<feature>.py`.
2. At module level: `pytestmark = pytest.mark.django_db`.
3. Add factories for new models in `tests/factories.py`.
4. Use `api_as("<ROLE>")` for clients, `make_*` for data.
5. Add RBAC rows to `tests/alerts/test_alerts_permissions.py:RBAC_MATRIX` if the
   new endpoint has role-based access rules (keep the matrix the single
   authoritative source for read/create gates).
