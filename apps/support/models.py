from django.conf import settings
from django.db import models
from django.utils import timezone


class Criticality(models.TextChoices):
    CRITICAL = "CRITICAL", "Critique"
    HIGH = "HIGH", "Élevée"
    MEDIUM = "MEDIUM", "Moyenne"
    LOW = "LOW", "Faible"


class TicketStatus(models.TextChoices):
    NEW = "NEW", "Nouveau"
    AWAITING_SUPPLIER = "AWAITING_SUPPLIER", "En attente fournisseur"
    DIAGNOSING = "DIAGNOSING", "Diagnostic en cours"
    SOLUTION_PROPOSED = "SOLUTION_PROPOSED", "Solution proposée"
    INTERVENING = "INTERVENING", "Intervention en cours"
    RESOLVED = "RESOLVED", "Résolu"
    CLOSED = "CLOSED", "Clôturé"


class Ticket(models.Model):
    ticket_number = models.CharField(max_length=30, unique=True, blank=True)

    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.PROTECT, related_name="support_tickets",
    )
    alert = models.ForeignKey(
        "alerts.Alert", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="support_tickets",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tickets_reported",
    )
    # Set the first time a supplier acts on the ticket (start_diagnosis or
    # propose_solution) — a machine can have several suppliers assigned, so
    # this attributes the ticket to whichever one actually engaged, which is
    # what "pannes par fournisseur" reporting needs to be unambiguous.
    assigned_supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tickets_handled",
    )

    criticality = models.CharField(max_length=20, choices=Criticality.choices, default=Criticality.MEDIUM)
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.NEW)

    production_line = models.CharField(max_length=120, blank=True, default="")
    equipment_detail = models.CharField(max_length=200, blank=True, default="")
    error_code = models.CharField(max_length=60, blank=True, default="")

    description = models.TextField()
    symptoms = models.TextField(blank=True, default="")
    production_impacted = models.CharField(max_length=200, blank=True, default="")

    downtime_start = models.DateTimeField(null=True, blank=True)
    downtime_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket SAV"
        verbose_name_plural = "Tickets SAV"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["machine", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_number} — {self.machine.code}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            year = timezone.now().year
            count = Ticket.objects.filter(ticket_number__startswith=f"SAV-{year}-").count() + 1
            self.ticket_number = f"SAV-{year}-{count:04d}"
        if not self.downtime_start:
            self.downtime_start = timezone.now()
        super().save(*args, **kwargs)

    # state-machine helpers — return False when the transition is not allowed.
    def can_assign_supplier(self) -> bool:
        return self.status == TicketStatus.NEW

    def can_start_diagnosis(self) -> bool:
        return self.status == TicketStatus.AWAITING_SUPPLIER

    def can_propose_solution(self) -> bool:
        return self.status in (TicketStatus.AWAITING_SUPPLIER, TicketStatus.DIAGNOSING)

    def can_validate(self) -> bool:
        return self.status == TicketStatus.SOLUTION_PROPOSED

    def can_close(self) -> bool:
        return self.status in (TicketStatus.RESOLVED, TicketStatus.INTERVENING)

    def is_terminal(self) -> bool:
        return self.status == TicketStatus.CLOSED


def _upload_to(instance, filename):
    return f"ticket_attachments/{timezone.now():%Y/%m/%d}/{filename}"


class AttachmentCategory(models.TextChoices):
    PHOTO = "PHOTO", "Photo"
    VIDEO = "VIDEO", "Vidéo"
    PDF = "PDF", "PDF"
    REPORT = "REPORT", "Rapport"
    SCREENSHOT = "SCREENSHOT", "Capture d'écran"
    ALARM_LOG = "ALARM_LOG", "Journal des alarmes"
    TECHNICAL_FILE = "TECHNICAL_FILE", "Fichier technique"


class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    # Set when a file belongs to a specific solution proposal (notice, plans,
    # explanatory video, software update...) rather than the ticket generally.
    solution = models.ForeignKey(
        "SupplierSolution", on_delete=models.CASCADE,
        null=True, blank=True, related_name="attachments",
    )
    file = models.FileField(upload_to=_upload_to)
    category = models.CharField(max_length=20, choices=AttachmentCategory.choices, default=AttachmentCategory.PHOTO)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ticket_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe de ticket"
        verbose_name_plural = "Pièces jointes de ticket"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.get_category_display()}@{self.uploaded_at:%Y-%m-%d %H:%M}"


class CommentRequestType(models.TextChoices):
    QUESTION = "QUESTION", "Question"
    TEST_REQUEST = "TEST_REQUEST", "Essai complémentaire demandé"
    PHOTO_REQUEST = "PHOTO_REQUEST", "Photos supplémentaires demandées"


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    # Blank = a plain comment; set only when the supplier is using this
    # comment to make one of the spec's three specific diagnostic requests
    # rather than just talking, so the UI can flag it distinctly.
    request_type = models.CharField(max_length=20, choices=CommentRequestType.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commentaire de ticket"
        verbose_name_plural = "Commentaires de ticket"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment@{self.created_at:%Y-%m-%d %H:%M}"


class ValidationDecision(models.TextChoices):
    ACCEPTED = "ACCEPTED", "Acceptée"
    REFUSED = "REFUSED", "Refusée"
    INFO_REQUESTED = "INFO_REQUESTED", "Informations complémentaires demandées"
    ONSITE_REQUESTED = "ONSITE_REQUESTED", "Intervention sur site demandée"
    VIDEOCALL_REQUESTED = "VIDEOCALL_REQUESTED", "Assistance visioconférence demandée"


class TicketStatusLog(models.Model):
    """Full audit trail of every status transition and validation decision."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="status_logs")
    from_status = models.CharField(max_length=20, choices=TicketStatus.choices, blank=True, default="")
    to_status = models.CharField(max_length=20, choices=TicketStatus.choices)
    decision = models.CharField(max_length=25, choices=ValidationDecision.choices, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historique de statut de ticket"
        verbose_name_plural = "Historiques de statut de ticket"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.from_status or '—'} → {self.to_status}"


class SupplierSolution(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="solutions")
    diagnostic = models.TextField(blank=True, default="")
    probable_cause = models.TextField(blank=True, default="")
    root_cause = models.TextField(blank=True, default="")
    repair_procedure = models.TextField(blank=True, default="")
    spare_parts = models.TextField(blank=True, default="")
    estimated_duration_min = models.PositiveIntegerField(null=True, blank=True)
    urgency = models.CharField(max_length=20, choices=Criticality.choices, default=Criticality.MEDIUM)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    proposed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solution fournisseur"
        verbose_name_plural = "Solutions fournisseur"
        ordering = ["-proposed_at"]

    def __str__(self) -> str:
        return f"Solution@{self.proposed_at:%Y-%m-%d %H:%M}"


class TicketClosure(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="closure")
    repair_conforms = models.BooleanField(default=True)
    machine_back_in_service = models.BooleanField(default=True)
    restarted_at = models.DateTimeField(null=True, blank=True)
    total_downtime_min = models.PositiveIntegerField(default=0)
    intervention_duration_min = models.PositiveIntegerField(null=True, blank=True)
    parts_replaced = models.TextField(blank=True, default="")
    intervention_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Clôture de ticket"
        verbose_name_plural = "Clôtures de ticket"

    def __str__(self) -> str:
        return f"Closure@{self.closed_at:%Y-%m-%d %H:%M}"
