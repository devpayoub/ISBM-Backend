from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrManager, IsController

from .models import AuditDocument, NcStatus, NonConformity
from .serializers import AuditDocumentSerializer, NonConformitySerializer

CAN_MANAGE = IsAdminOrManager | IsController


class NonConformityViewSet(viewsets.ModelViewSet):
    queryset = NonConformity.objects.select_related("machine", "opened_by")
    serializer_class = NonConformitySerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("status", "type", "source", "machine")
    search_fields = ("nc_number", "description", "product")
    ordering = ["-opened_at"]

    def perform_create(self, serializer):
        if self.request.user.role not in ("ADMIN", "MANAGER", "CONTROLLER"):
            raise PermissionDenied("Rôle insuffisant pour créer une non-conformité.")
        serializer.save(opened_by=self.request.user)

    def perform_update(self, serializer):
        if self.request.user.role not in ("ADMIN", "MANAGER", "CONTROLLER"):
            raise PermissionDenied("Rôle insuffisant pour modifier une non-conformité.")
        serializer.save()

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, CAN_MANAGE])
    def close(self, request, pk=None):
        nc = self.get_object()
        if nc.status == NcStatus.CLOSED:
            raise ValidationError("Non-conformité déjà clôturée.")
        nc.status = NcStatus.CLOSED
        nc.closed_at = timezone.now()
        nc.save()
        return Response(NonConformitySerializer(nc).data)

    @action(detail=False, methods=["get"])
    def open(self, request):
        rows = self.get_queryset().exclude(status=NcStatus.CLOSED)
        return Response(NonConformitySerializer(rows, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-clause")
    def by_clause(self, request):
        rows = self.get_queryset().values("type").annotate(nb=Count("id")).order_by("-nb")
        return Response(list(rows))


class AuditDocumentViewSet(viewsets.ModelViewSet):
    queryset = AuditDocument.objects.select_related("uploaded_by")
    serializer_class = AuditDocumentSerializer
    permission_classes = (IsAuthenticated, CAN_MANAGE)
    parser_classes = (MultiPartParser, FormParser)
    filterset_fields = ("status", "clause")
    search_fields = ("title", "clause")
    ordering = ["-uploaded_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
