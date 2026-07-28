from django.conf import settings
from django.db import models
from django.utils import timezone


class NcSource(models.TextChoices):
    INTERNAL = "INTERNAL", "Interne"
    CUSTOMER = "CUSTOMER", "Client"
    AUDIT = "AUDIT", "Audit"
    ALERT = "ALERT", "Alerte"


class NcType(models.TextChoices):
    CRITICAL = "CRITICAL", "Critique"
    MAJOR = "MAJOR", "Majeur"
    MINOR = "MINOR", "Mineur"


class NcStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    INVESTIGATING = "INVESTIGATING", "En investigation"
    CORRECTED = "CORRECTED", "Corrigée"
    CLOSED = "CLOSED", "Clôturée"


class NonConformity(models.Model):
    nc_number = models.CharField(max_length=30, unique=True, blank=True)
    source = models.CharField(max_length=20, choices=NcSource.choices, default=NcSource.INTERNAL)
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="non_conformities",
    )
    product = models.CharField(max_length=120, blank=True, default="")
    type = models.CharField(max_length=20, choices=NcType.choices, default=NcType.MAJOR)
    description = models.TextField()
    root_cause = models.TextField(blank=True, default="")
    corrective_action = models.TextField(blank=True, default="")
    preventive_action = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=NcStatus.choices, default=NcStatus.OPEN)

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="non_conformities_opened",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    linked_alert = models.ForeignKey(
        "alerts.Alert", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="non_conformities",
    )

    class Meta:
        verbose_name = "Non-conformité"
        verbose_name_plural = "Non-conformités"
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return self.nc_number or f"NC #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.nc_number:
            year = timezone.now().year
            count = NonConformity.objects.filter(nc_number__startswith=f"NC-{year}-").count() + 1
            self.nc_number = f"NC-{year}-{count:04d}"
        super().save(*args, **kwargs)


class DocStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    READY = "READY", "Prêt"
    APPROVED = "APPROVED", "Approuvé"


def _upload_to(instance, filename):
    return f"audit_docs/{timezone.now():%Y/%m/%d}/{filename}"


class AuditDocument(models.Model):
    title = models.CharField(max_length=200)
    clause = models.CharField(max_length=40, blank=True, default="")
    file = models.FileField(upload_to=_upload_to)
    version = models.CharField(max_length=20, blank=True, default="1.0")
    status = models.CharField(max_length=20, choices=DocStatus.choices, default=DocStatus.DRAFT)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audit_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Document d'audit"
        verbose_name_plural = "Documents d'audit"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"
