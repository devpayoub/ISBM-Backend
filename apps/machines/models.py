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
    value = models.DecimalField(max_digits=12, decimal_places=4)
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


# Default parameters used during seeding & referenced by OEE / costs.
DEFAULT_PARAMETERS = [
    # key, label, value, unit, category
    ("COST_PET_KG", "Coût PET [DA/kg]", 2.80, "DA/kg", "costs"),
    ("COST_ENERGY_KWH", "Coût énergie [DA/kWh]", 0.75, "DA/kWh", "costs"),
    ("COST_LABOR_H", "Coût main d'oeuvre [DA/h]", 25.0, "DA/h", "costs"),
    ("COST_AIR_M3", "Coût air comprimé [DA/m³]", 0.05, "DA/m³", "costs"),
    ("SHIFT_DURATION_MIN", "Durée shift [min]", 1440, "min", "shift"),
    ("TRS_THRESHOLD", "Seuil TRS [%]", 70.0, "%", "oee"),
    ("CADENCE_ISBM110", "Cadence ISBM110 [BPH]", 720, "BPH", "machines"),
    ("CADENCE_ISBM88", "Cadence ISBM88 [BPH]", 1100, "BPH", "machines"),
    ("CADENCE_CAPS", "Cadence bouchons [CPH]", 1600, "CPH", "machines"),
]
