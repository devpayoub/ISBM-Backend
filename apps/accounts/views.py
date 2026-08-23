from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import log_activity
from apps.common.permissions import IsAdmin, IsAdminOrManagerOrMaintenance

from .models import CustomUser, ShiftAssignment
from .serializers import (
    LoginSerializer, MeSerializer, RegisterSerializer, ShiftAssignmentSerializer,
    UserSerializer,
)


@extend_schema(tags=["Auth"])
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        log_activity(user, "auth.login", "CustomUser", user.pk, user.email)
        ShiftAssignment.clock_in(user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # Clocking out must never depend on the client's refresh token being
        # well-formed/still valid — request.user is already proven by the
        # access token (IsAuthenticated), and that's the only thing
        # ShiftAssignment.clock_out() needs. Validating `refresh` here is
        # best-effort bookkeeping only, not a gate.
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh)
            except Exception:
                pass
        log_activity(request.user, "auth.logout", "CustomUser", request.user.pk, request.user.email)
        ShiftAssignment.clock_out(request.user)
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(tags=["Auth"])
class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        u = request.user
        for f in ("first_name", "last_name", "phone", "shift", "is_on_duty"):
            if f in request.data:
                setattr(u, f, request.data[f])
        u.save()
        return Response(MeSerializer(u).data)


@extend_schema(tags=["Users"])
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by("last_name", "first_name")
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsAdmin)
    filterset_fields = ("role", "shift", "is_on_duty")
    search_fields = ("email", "first_name", "last_name", "phone")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsAdminOrManagerOrMaintenance()]
        return [permission() for permission in self.permission_classes]

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsAdmin])
    def register(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["RH"])
class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """Read is open to any authenticated internal role (Reclamation/Package
    lookups in later phases need this); mutation is Admin/Manager only,
    matching NonConformity's inline-role-check style rather than a
    class-level permission so the same viewset can also host `working_at`
    (open to any authenticated role, not just admin/manager)."""

    queryset = ShiftAssignment.objects.select_related("user", "machine")
    serializer_class = ShiftAssignmentSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("user", "machine", "shift")
    ordering = ["-starts_at"]

    def _check_manage(self):
        if self.request.user.role not in ("ADMIN", "MANAGER"):
            raise PermissionDenied("Rôle insuffisant pour gérer les affectations de shift.")

    def perform_create(self, serializer):
        self._check_manage()
        obj = serializer.save()
        log_activity(self.request.user, "shift_assignment.created", "ShiftAssignment", obj.pk, f"{obj.user.full_name} — {obj.shift}")

    def perform_update(self, serializer):
        self._check_manage()
        obj = serializer.save()
        log_activity(self.request.user, "shift_assignment.updated", "ShiftAssignment", obj.pk, f"{obj.user.full_name} — {obj.shift}")

    def perform_destroy(self, instance):
        self._check_manage()
        detail = f"{instance.user.full_name} — {instance.shift}"
        pk = instance.pk
        instance.delete()
        log_activity(self.request.user, "shift_assignment.deleted", "ShiftAssignment", pk, detail)

    @action(detail=False, methods=["get"])
    def working_at(self, request):
        """Who was on shift at a given datetime — the lookup Reclamation
        and Package traceability (later phases) depend on."""
        when_raw = request.query_params.get("when")
        if not when_raw:
            raise ValidationError("Paramètre 'when' requis (ISO 8601).")
        when = parse_datetime(when_raw)
        if when is None:
            raise ValidationError("Format de date invalide pour 'when' (attendu ISO 8601).")
        machine_id = request.query_params.get("machine")
        role = request.query_params.get("role")
        rows = ShiftAssignment.working_at(when, machine=machine_id, role=role)
        return Response(ShiftAssignmentSerializer(rows, many=True).data)
