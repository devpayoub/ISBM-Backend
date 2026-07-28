"""
Idempotent seed command for the test suite.

Creates one user per role with a known password + reference machine/category
data so that pytest fixtures (tests/conftest.py) can rely on stable fixtures.
It is safe to re-run: existing rows are refreshed in place.

Run inside Docker:
    docker compose exec web python manage.py seed_test

Do NOT use in production — passwords are intentionally weak and known.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import CustomUser, Role, Shift
from apps.alerts.models import AlertCategory, Severity
from apps.machines.models import (
    DEFAULT_PARAMETERS, Machine, MachineStatus, MachineType, Parameter,
)

# Satisfies Django's default password validators:
#   min 10 chars, not too common, has digit, upper, lower, symbol.
PASSWORD = "Test12345!"

USERS = [
    # (email, first_name, last_name, role, shift, is_on_duty)
    ("admin.test@isbm.local",        "Admin",      "Test",  Role.ADMIN,       Shift.MORNING,   True),
    ("manager.test@isbm.local",      "Manager",    "Test",  Role.MANAGER,     Shift.MORNING,   True),
    ("controller.test@isbm.local",   "Controller", "Test",  Role.CONTROLLER,  Shift.MORNING,   True),
    ("maintenance.test@isbm.local",  "Maint",      "Test",  Role.MAINTENANCE, Shift.AFTERNOON, True),
    ("operator.test@isbm.local",     "Operator",   "Test",  Role.OPERATOR,    Shift.NIGHT,     True),
    # Off-duty controller — exercises the (currently silent) is_on_duty gate.
    ("controller.offduty@isbm.local","Offduty",    "Test",  Role.CONTROLLER,  Shift.NIGHT,     False),
]

MACHINES = [
    # (code, name, type, bph, cph, cavities, fmt)
    ("TEST-ISBM110", "Test ISBM 110", MachineType.ISBM,      720, 0,    6, "750 ml"),
    ("TEST-ISBM88",  "Test ISBM 88",  MachineType.ISBM,      1100, 0,   6, "250 ml"),
    ("TEST-INJ-CAPS","Test cap press",MachineType.INJECTION, 0,   1600, 8, "Bouchon"),
]

CATEGORIES = [
    # (name, code, severity_default, requires_maintenance)
    ("Hydraulic leak", "HYDRAULIC", Severity.MAJOR,    True),
    ("Electrical",     "ELEC",      Severity.CRITICAL, True),
    ("Quality defect", "QUALITY",   Severity.MINOR,    False),
]


class Command(BaseCommand):
    help = (
        "Idempotent seed for the test suite: one user per role + reference "
        "machines, parameters and alert categories. Safe to re-run."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed_users()
        self._seed_machines()
        self._seed_parameters()
        self._seed_categories()
        self.stdout.write(self.style.SUCCESS("seed_test terminé."))

    # ------------------------------------------------------------------
    def _seed_users(self):
        for email, fn, ln, role, shift, on_duty in USERS:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": fn, "last_name": ln,
                    "role": role, "shift": shift, "is_on_duty": on_duty,
                },
            )
            # Refresh in-place to absorb any drift (idempotent).
            user.first_name = fn
            user.last_name = ln
            user.role = role
            user.shift = shift
            user.is_on_duty = on_duty
            user.set_password(PASSWORD)
            user.save()
            tag = "créé" if created else "rafraîchi"
            self.stdout.write(f"  user {user.email} ({role}) — {tag}")

    def _seed_machines(self):
        for code, name, mtype, bph, cph, cavities, fmt in MACHINES:
            obj, created = Machine.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "type": mtype,
                    "nominal_bph": bph, "nominal_cph": cph,
                    "cavities": cavities, "product_format": fmt,
                    "status": MachineStatus.STOPPED,
                    "location": "Atelier ISBM", "is_active": True,
                },
            )
            self.stdout.write(f"  machine {obj.code}: {'créée' if created else 'existe'}")

    def _seed_parameters(self):
        for key, label, value, unit, category in DEFAULT_PARAMETERS:
            Parameter.objects.update_or_create(
                key=key,
                defaults={
                    "label": label, "value": Decimal(str(value)),
                    "unit": unit, "category": category,
                    "effective_from": date.today(), "is_active": True,
                },
            )

    def _seed_categories(self):
        for name, code, sev, req_maint in CATEGORIES:
            AlertCategory.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "severity_default": sev,
                    "requires_maintenance": req_maint, "is_active": True,
                },
            )
