from django.db import models


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


# Default parameters used during seeding. STEG parameters are seeded
# separately via migrations/0005_seed_steg_parameters.py, not here.
DEFAULT_PARAMETERS = [
    # key, label, value, unit, category
    ("SHIFT_DURATION_MIN", "Durée shift [min]", 1440, "min", "shift"),
]
