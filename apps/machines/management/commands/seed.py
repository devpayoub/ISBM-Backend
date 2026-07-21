from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import CustomUser, Role, Shift
from apps.machines.models import (
    DEFAULT_PARAMETERS, Machine, MachineStatus, MachineType, Parameter,
)


class Command(BaseCommand):
    help = "Seed default machines, parameters, and one admin user."

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed_machines()
        self._seed_parameters()
        self._seed_admin()
        self.stdout.write(self.style.SUCCESS("Seed terminé."))

    def _seed_machines(self):
        machines = [
            ("ISBM110", "ISBM 110 — Bouteille 750 ml", MachineType.ISBM, 720, 0, 6, "750 ml"),
            ("ISBM88", "ISBM 88 — Bouteille 250 ml", MachineType.ISBM, 1100, 0, 6, "250 ml"),
            ("INJ-CAPS", "Presse à injection bouchons", MachineType.INJECTION, 0, 1600, 8, "Bouchon"),
            ("COMP-AIR", "Compresseur d'air atelier", MachineType.COMPRESSOR, 0, 0, 1, ""),
            ("CHILLER-01", "Groupe eau froide 01", MachineType.CHILLER, 0, 0, 1, ""),
        ]
        for code, name, type_, bph, cph, cavities, fmt in machines:
            obj, created = Machine.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "type": type_,
                    "nominal_bph": bph, "nominal_cph": cph,
                    "cavities": cavities, "product_format": fmt,
                    "status": MachineStatus.STOPPED,
                    "location": "Atelier ISBM",
                },
            )
            self.stdout.write(f"  Machine {obj.code}: {'créée' if created else 'existe'}")

    def _seed_parameters(self):
        for key, label, value, unit, category in DEFAULT_PARAMETERS:
            obj, created = Parameter.objects.update_or_create(
                key=key,
                defaults={
                    "label": label, "value": Decimal(str(value)),
                    "unit": unit, "category": category,
                    "effective_from": date.today(), "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"  Paramètre {obj.key}: créé")

    def _seed_admin(self):
        email = "admin@isbm.local"
        if CustomUser.objects.filter(email=email).exists():
            self.stdout.write("  Admin existe déjà.")
            return
        u = CustomUser.objects.create_superuser(
            email=email, password="admin12345",
            first_name="Administrateur", last_name="ISBM",
        )
        u.role = Role.ADMIN
        u.shift = Shift.MORNING
        u.phone = ""
        u.save()
        self.stdout.write(self.style.WARNING(
            f"  Admin créé: {u.email} / mot de passe: admin12345 (à changer immédiatement)"
        ))
