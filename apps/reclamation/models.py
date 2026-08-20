from django.conf import settings
from django.db import models
from django.utils import timezone


class ReclamationStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    INVESTIGATING = "INVESTIGATING", "En investigation"
    CORRECTED = "CORRECTED", "Corrigée"
    CLOSED = "CLOSED", "Clôturée"


class ReclamationSeverity(models.TextChoices):
    CRITICAL = "CRITICAL", "Critique"
    MAJOR = "MAJOR", "Majeur"
    MINOR = "MINOR", "Mineur"


class Reclamation(models.Model):
    """Client-reported problem with bottles/material (plan.md §6). Auto-
    numbered like NonConformity/Ticket; status enum copied from
    NonConformity's OPEN/INVESTIGATING/CORRECTED/CLOSED (documented default,
    no separate client-complaint workflow exists in the app yet)."""

    reference = models.CharField(max_length=30, unique=True, blank=True)
    client = models.CharField(max_length=150)
    reported_at = models.DateTimeField(default=timezone.now)
    description = models.TextField()

    stock_item = models.ForeignKey(
        "stock.StockItem", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reclamations",
    )
    product_reference = models.CharField(max_length=100, blank=True, default="")
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reclamations",
    )
    production_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Date/heure de production du produit concerné, si connue — utilisée pour identifier le personnel en poste.",
    )

    severity = models.CharField(max_length=20, choices=ReclamationSeverity.choices, default=ReclamationSeverity.MAJOR)
    status = models.CharField(max_length=20, choices=ReclamationStatus.choices, default=ReclamationStatus.OPEN)

    # Immutable snapshot of who was working when the reclamation was filed —
    # computed once via services.resolve_personnel() so it doesn't silently
    # change later if ShiftAssignment rows are edited/added.
    resolved_personnel = models.JSONField(default=dict, blank=True)

    resolution = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reclamations_created",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reclamations_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        ordering = ["-reported_at"]

    def __str__(self) -> str:
        return self.reference or f"Réclamation #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            count = Reclamation.objects.filter(reference__startswith=f"REC-{year}-").count() + 1
            self.reference = f"REC-{year}-{count:04d}"
        super().save(*args, **kwargs)


def _upload_to(instance, filename):
    return f"reclamation_attachments/{timezone.now():%Y/%m/%d}/{filename}"


class ReclamationAttachment(models.Model):
    reclamation = models.ForeignKey(Reclamation, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=_upload_to)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reclamation_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe de réclamation"
        verbose_name_plural = "Pièces jointes de réclamation"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"Attachment@{self.uploaded_at:%Y-%m-%d %H:%M}"
