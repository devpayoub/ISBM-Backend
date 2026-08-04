from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    MANAGER = "MANAGER", "Chef d'équipe"
    CONTROLLER = "CONTROLLER", "Contrôleur"
    MAINTENANCE = "MAINTENANCE", "Maintenance"
    OPERATOR = "OPERATOR", "Opérateur"
    SUPPLIER = "SUPPLIER", "Fournisseur"


class Shift(models.TextChoices):
    MORNING = "MORNING", "Matin (06h-14h)"
    AFTERNOON = "AFTERNOON", "Après-midi (14h-22h)"
    NIGHT = "NIGHT", "Nuit (22h-06h)"


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", Role.CONTROLLER)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        return self._create_user(email, password, **extra)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField("Email", unique=True)

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.CONTROLLER,
    )
    shift = models.CharField(
        max_length=20, choices=Shift.choices, null=True, blank=True,
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    machine_assignment = models.ForeignKey(
        "machines.Machine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="operators",
    )
    is_on_duty = models.BooleanField(default=False)

    # Used only for role=SUPPLIER: which machines this supplier services, for
    # scoping their visibility into the SAV ticket module (a supplier may
    # cover several machines, unlike machine_assignment above which is a
    # single-machine link used for Controllers).
    assigned_machines = models.ManyToManyField(
        "machines.Machine", blank=True, related_name="assigned_suppliers",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_role_display()})"
