from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


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


class ShiftAssignment(models.Model):
    """Historical record of who worked which shift, on which machine, and
    when — unlike CustomUser.shift/is_on_duty/machine_assignment (single
    current-value fields), this is what lets Reclamation/Package answer
    "who was working on machine X at date/time Y". Self-populating: rows
    are created/closed by clock_in()/clock_out(), called from
    LoginView/LogoutView — never entered by hand, so the RH page is a
    read-only view over this table, the same way the audit log is."""

    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.CASCADE, related_name="shift_assignments",
    )
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="shift_assignments",
    )
    shift = models.CharField(max_length=20, choices=Shift.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affectation de shift"
        verbose_name_plural = "Affectations de shift"
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["user", "-starts_at"]),
            models.Index(fields=["machine", "-starts_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.full_name} — {self.shift} @ {self.starts_at:%Y-%m-%d %H:%M}"

    @classmethod
    def working_at(cls, when, machine=None, role=None):
        """Everyone on shift at a given datetime, optionally scoped to a
        machine and/or role. An assignment with no ends_at is treated as
        still ongoing (open-ended)."""
        from django.db.models import Q
        qs = cls.objects.filter(starts_at__lte=when).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=when)
        )
        if machine is not None:
            qs = qs.filter(machine=machine)
        if role is not None:
            qs = qs.filter(user__role=role)
        return qs.select_related("user", "machine")

    @classmethod
    def working_between(cls, start, end, machine=None):
        """Everyone whose shift overlaps [start, end) at all — used for
        Package/Bag traceability (plan.md §9), where production spans a
        range rather than a single instant like Reclamation's working_at.
        An assignment with no ends_at is treated as still ongoing."""
        from django.db.models import Q
        qs = cls.objects.filter(starts_at__lt=end).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=start)
        )
        if machine is not None:
            qs = qs.filter(machine=machine)
        return qs.select_related("user", "machine")

    @classmethod
    def clock_in(cls, user):
        """Called on login. Closes any stale open assignment for this user
        first (e.g. a missed logout from a previous session) so there's
        never more than one open row per user, then opens a new one from
        their current shift/machine. Users with no shift configured (e.g.
        ADMIN, SUPPLIER) aren't tracked here — nothing to open."""
        if not user.shift:
            return None
        cls.objects.filter(user=user, ends_at__isnull=True).update(ends_at=timezone.now())
        return cls.objects.create(
            user=user, machine=user.machine_assignment, shift=user.shift,
            starts_at=timezone.now(),
        )

    @classmethod
    def clock_out(cls, user):
        """Called on logout. Closes the user's currently open assignment,
        if any — a no-op for users clock_in() never opened one for."""
        cls.objects.filter(user=user, ends_at__isnull=True).update(ends_at=timezone.now())
