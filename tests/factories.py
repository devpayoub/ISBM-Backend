"""Minimal in-test factories for DB objects.

Tests build their own state via these helpers — they never depend on
``manage.py seed_test`` having been run. Each function is idempotent-ish
(get_or_create on a stable key).
"""
from __future__ import annotations

import uuid

from apps.alerts.models import Alert, AlertCategory, AlertStatus, Severity
from apps.machines.models import Machine, MachineStatus, MachineType, Parameter
from datetime import date
from decimal import Decimal


def make_machine(code: str = None, **kwargs) -> Machine:
    code = code or f"M-{uuid.uuid4().hex[:8]}"
    defaults = {
        "name": f"Machine {code}",
        "type": MachineType.ISBM,
        "status": MachineStatus.STOPPED,
        "nominal_bph": 720,
        "cavities": 6,
        "is_active": True,
        "location": "Atelier ISBM",
    }
    defaults.update(kwargs)
    machine, _ = Machine.objects.get_or_create(code=code, defaults=defaults)
    return machine


def make_category(code: str = "HYDRAULIC", **kwargs) -> AlertCategory:
    defaults = {
        # Default name is derived from the code so multiple test categories
        # don't collapse under the same name (pareto groups by category__name).
        "name": f"Cat {code}",
        "severity_default": Severity.MAJOR,
        "requires_maintenance": True,
        "is_active": True,
    }
    defaults.update(kwargs)
    cat, _ = AlertCategory.objects.get_or_create(code=code, defaults=defaults)
    return cat


def make_parameter(key: str = "TEST_PARAM", **kwargs) -> Parameter:
    defaults = {
        "label": "Test parameter",
        "value": Decimal("1.0"),
        "unit": "",
        "effective_from": date.today(),
        "is_active": True,
        "category": "general",
    }
    defaults.update(kwargs)
    param, _ = Parameter.objects.get_or_create(key=key, defaults=defaults)
    # Refresh mutable fields idempotently
    for k, v in defaults.items():
        setattr(param, k, v)
    param.save()
    return param


def make_alert(machine=None, category=None, *, status=AlertStatus.OPEN,
               severity=Severity.MAJOR, reported_by=None, **kwargs) -> Alert:
    """Create an Alert already in a given ``status`` (bypasses the view layer).

    Use for lifecycle tests that need a starting state other than OPEN.
    """
    machine = machine or make_machine()
    category = category or make_category()
    defaults = {
        "title": kwargs.pop("title", "Test alert"),
        "description": kwargs.pop("description", ""),
        "severity": severity,
        "status": status,
        "worker_name": kwargs.pop("worker_name", "T. Operator"),
        "shift": kwargs.pop("shift", "MORNING"),
        "reported_by": reported_by,
    }
    defaults.update(kwargs)
    # Let the model's save() compute priority_score, then patch status if needed.
    alert = Alert.objects.create(machine=machine, category=category, **defaults)
    return alert
