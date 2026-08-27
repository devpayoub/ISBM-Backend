from django.conf import settings
from django.db import models
from django.db.models import Q


class MachineType(models.TextChoices):
    ISBM = "ISBM", "Souffleuse ISBM"
    INJECTION = "INJECTION", "Presse à injection"
    COMPRESSOR = "COMPRESSOR", "Compresseur"
    CHILLER = "CHILLER", "Groupe eau froide"


class MachineStatus(models.TextChoices):
    RUNNING = "RUNNING", "En marche"
    STOPPED = "STOPPED", "Arrêtée"
    MAINTENANCE = "MAINTENANCE", "Maintenance"
    BREAKDOWN = "BREAKDOWN", "En panne"


class Machine(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=MachineType.choices, default=MachineType.ISBM)
    status = models.CharField(max_length=20, choices=MachineStatus.choices, default=MachineStatus.RUNNING)

    nominal_bph = models.PositiveIntegerField(default=0, help_text="Cadence nominale bouteilles/heure")
    nominal_cph = models.PositiveIntegerField(default=0, help_text="Cadence nominale bouchons/heure")
    cavities = models.PositiveIntegerField(default=6)
    product_format = models.CharField(max_length=50, blank=True, default="")
    location = models.CharField(max_length=120, blank=True, default="")
    serial_number = models.CharField(max_length=100, blank=True, default="")
    manufacturer = models.CharField(max_length=120, blank=True, default="")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def get_andon_status(self) -> str:
        """RUNNING/GREEN unless there's a reason to say otherwise: BREAKDOWN
        (a CRITICAL alert is active) always reads RED; any other active alert
        keeps the machine RUNNING but flags ORANGE. See
        apps.alerts.services.sync_machine_andon_status, the single place
        that's allowed to change `status` — it's driven entirely by alerts,
        never set by hand."""
        if self.status in (MachineStatus.STOPPED, MachineStatus.BREAKDOWN):
            return "RED"
        has_active_alert = self.alerts.filter(
            status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]
        ).exists()
        return "ORANGE" if has_active_alert else "GREEN"

    def get_equipment_status(self) -> str:
        """New, component/parameter-driven status for the Ligne/Équipements
        hierarchy — deliberately separate from get_andon_status() above
        (alert-driven, used by the Dashboard Andon board, /alerts, and the
        sidebar). "The problems of the machine come from the components":
        WARNING here means at least one of this machine's own parameters, or
        any active component's parameters, is off target."""
        own = (p.status for p in self.parameters.all())
        child = (c.status for c in self.components.filter(is_active=True))
        return "WARNING" if any(s == "WARNING" for s in (*own, *child)) else "OK"


class Parameter(models.Model):
    """Configurable parameter (costs, thresholds, timing) with effective date."""

    key = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=200)
    value = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    # For non-numeric settings (e.g. STEG's optional outage time/notes) that
    # don't fit `value`'s DecimalField — blank for every purely numeric
    # parameter, which is still the vast majority of rows.
    text_value = models.CharField(max_length=200, blank=True, default="")
    unit = models.CharField(max_length=40, blank=True, default="")
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)
    category = models.CharField(max_length=60, blank=True, default="general")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"
        ordering = ["category", "key"]

    def __str__(self) -> str:
        return f"{self.label} = {self.value} {self.unit}".strip()


class MachineComponent(models.Model):
    """A named, referenced sub-assembly permanently attached to one line
    (Auto Loader, Hopper Dryer, Hot Runner, ...) — from the PDF's per-line
    equipment tables. Distinct from AuxiliaryEquipment, which can serve
    multiple lines (e.g. the shared air compressor)."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="components")
    name = models.CharField(max_length=120)
    reference = models.CharField(max_length=60, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Composant machine"
        verbose_name_plural = "Composants machine"
        ordering = ["machine", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.reference or '—'}) — {self.machine.code}"

    @property
    def status(self) -> str:
        return "WARNING" if any(p.status == "WARNING" for p in self.parameters.all()) else "OK"


class AuxiliaryEquipment(models.Model):
    """Shared support equipment (air compressor, air dryer, ...) that can
    serve more than one line — hence the M2M instead of MachineComponent's
    single FK."""

    name = models.CharField(max_length=120)
    reference = models.CharField(max_length=60, blank=True, default="")
    machines = models.ManyToManyField(Machine, blank=True, related_name="auxiliary_equipment")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Équipement auxiliaire"
        verbose_name_plural = "Équipements auxiliaires"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.reference or '—'})"


class Mold(models.Model):
    """A mold attached to one line. The PDF leaves most ISBM110/88 mold
    references blank on purpose (plan.md: "keep the item but allow its
    reference to be configured in the application") — reference is
    deliberately optional, unlike MachineComponent's (still-optional but
    normally populated) reference."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="molds")
    name = models.CharField(max_length=120, default="Mold")
    reference = models.CharField(max_length=60, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Moule"
        verbose_name_plural = "Moules"
        ordering = ["machine", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.reference or 'sans référence'}) — {self.machine.code}"


class MachineParameterDisplay(models.TextChoices):
    GAUGE = "GAUGE", "Jauge (%)"
    BAR = "BAR", "Barre + valeur"


class MachineParameter(models.Model):
    """A measured reading shown on the Ligne/Équipements 'Fiche Technique'
    hierarchy — e.g. "Pression Pré-soufflage: 8.2 bar / Cons: 8". Values are
    Admin-set config, not a live PLC feed (this app has no telemetry
    ingestion); `status` is computed live from how far `current_value` sits
    from `target_value`, never stored, so editing the tolerance or target
    immediately reflects everywhere it's read. Exactly one of machine/
    component is set — the machine's own top-level readings (Zone Vis 1-3,
    pressures...) vs. a specific sub-equipment's readings (Chiller, Dryer...),
    mirroring apps.maintenance.MaintenanceControl's machine/equipment split."""

    machine = models.ForeignKey(
        Machine, on_delete=models.CASCADE,
        null=True, blank=True, related_name="parameters",
    )
    component = models.ForeignKey(
        MachineComponent, on_delete=models.CASCADE,
        null=True, blank=True, related_name="parameters",
    )
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20, blank=True, default="")
    display = models.CharField(max_length=10, choices=MachineParameterDisplay.choices, default=MachineParameterDisplay.BAR)
    current_value = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    target_value = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    warning_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    order = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre machine"
        verbose_name_plural = "Paramètres machine"
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                check=Q(machine__isnull=False, component__isnull=True) | Q(machine__isnull=True, component__isnull=False),
                name="machine_parameter_exactly_one_target",
            ),
        ]

    def __str__(self) -> str:
        target = self.machine.code if self.machine_id else self.component.name
        return f"{self.name} ({target})"

    @property
    def status(self) -> str:
        if self.current_value is None or not self.target_value:
            return "OK"
        deviation_pct = abs(self.current_value - self.target_value) / self.target_value * 100
        return "WARNING" if deviation_pct > self.warning_tolerance_pct else "OK"


# Default parameters used during seeding. STEG parameters are seeded
# separately via migrations/0005_seed_steg_parameters.py, not here.
DEFAULT_PARAMETERS = [
    # key, label, value, unit, category
    ("SHIFT_DURATION_MIN", "Durée shift [min]", 1440, "min", "shift"),
]
