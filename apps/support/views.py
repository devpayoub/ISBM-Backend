from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_activity
from apps.common.permissions import IsAdminOrManagerOrMaintenance, IsSupplier

from .exports import export_tickets_excel, export_tickets_pdf
from .models import (
    CommentRequestType, SupplierSolution, Ticket, TicketAttachment, TicketClosure,
    TicketComment, TicketStatus, TicketStatusLog,
)
from .serializers import (
    SupplierSolutionSerializer, TicketAttachmentSerializer, TicketCloseSerializer,
    TicketCommentSerializer, TicketCreateSerializer, TicketSerializer,
    TicketValidateSerializer,
)
from .services import (
    broadcast_ticket_event, notify_diagnostic_available, notify_new_media,
    notify_solution_proposed, notify_ticket_assigned, notify_ticket_comment,
    notify_ticket_created, notify_ticket_resolved, notify_validation_decision,
)

CREATOR_ROLES = ("OPERATOR", "CONTROLLER", "MAINTENANCE", "MANAGER", "ADMIN")
# Routing a ticket to an external supplier is a bigger call than just
# declaring an incident, so it excludes OPERATOR — kept in sync with
# frontend/src/lib/auth/rbac.ts's 'assign_ticket_supplier' action.
ASSIGN_SUPPLIER_ROLES = ("ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE")


@extend_schema(tags=["Support"])
class TicketViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Deliberately not a full ModelViewSet: every mutation on a ticket has a
    dedicated, traceable action below (each writes a TicketStatusLog entry).
    A generic PATCH/PUT/DELETE would let any authenticated user — including
    a supplier — set fields like `status` directly with zero audit trail,
    which breaks the spec's full-traceability requirement."""

    queryset = Ticket.objects.select_related("machine", "reported_by").prefetch_related(
        "attachments", "comments", "status_logs", "solutions", "closure",
    )
    serializer_class = TicketSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("status", "criticality", "machine")
    search_fields = ("ticket_number", "description", "symptoms", "error_code")
    ordering_fields = ("created_at", "criticality")
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) == "SUPPLIER":
            # Strict server-side scoping: a supplier only ever sees tickets
            # explicitly assigned to them by whoever declared the ticket.
            # assigned_supplier is required at creation now, so there's no
            # machine-based fallback — a ticket with no supplier chosen
            # simply isn't visible to any supplier.
            return qs.filter(assigned_supplier=user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        return super().get_serializer_class()

    # --- create -------------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in CREATOR_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer un ticket SAV.")
        ticket = serializer.save(reported_by=user)
        notify_ticket_created(ticket)
        broadcast_ticket_event(ticket, "ticket.created")
        log_activity(user, "ticket.declared", "Ticket", ticket.pk, ticket.ticket_number)

        # The supplier is chosen right in the creation form now, so there's
        # no separate triage step left to do — go straight to
        # AWAITING_SUPPLIER instead of sitting in NEW waiting for an
        # "Assigner au fournisseur" click that would just re-pick someone
        # already picked. Keeps the status history honest (NEW is still
        # logged as the from_status) without leaving a dead-end button.
        self._transition(ticket, TicketStatus.AWAITING_SUPPLIER, user)
        notify_ticket_assigned(ticket)
        broadcast_ticket_event(ticket, "ticket.assigned")

    # --- workflow actions -----------------------------------------------
    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def assign_supplier(self, request, pk=None):
        ticket = self.get_object()
        if request.user.role not in ASSIGN_SUPPLIER_ROLES:
            raise PermissionDenied("Rôle insuffisant.")
        if not ticket.can_assign_supplier():
            raise ValidationError("Assignation non autorisée dans cet état.")
        self._transition(ticket, TicketStatus.AWAITING_SUPPLIER, request.user)
        notify_ticket_assigned(ticket)
        broadcast_ticket_event(ticket, "ticket.assigned")
        log_activity(request.user, "ticket.assigned", "Ticket", ticket.pk, ticket.ticket_number)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsSupplier])
    def start_diagnosis(self, request, pk=None):
        ticket = self.get_object()
        if not ticket.can_start_diagnosis():
            raise ValidationError("Diagnostic non autorisé dans cet état.")
        self._attribute_supplier(ticket, request.user)
        self._transition(ticket, TicketStatus.DIAGNOSING, request.user)
        notify_diagnostic_available(ticket)
        broadcast_ticket_event(ticket, "ticket.status_changed")
        log_activity(request.user, "ticket.diagnosing", "Ticket", ticket.pk, ticket.ticket_number)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsSupplier])
    def propose_solution(self, request, pk=None):
        ticket = self.get_object()
        if not ticket.can_propose_solution():
            raise ValidationError("Proposition de solution non autorisée dans cet état.")
        serializer = SupplierSolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        solution = serializer.save(ticket=ticket, proposed_by=request.user)
        self._attribute_supplier(ticket, request.user)
        self._transition(ticket, TicketStatus.SOLUTION_PROPOSED, request.user)
        notify_solution_proposed(ticket)
        broadcast_ticket_event(ticket, "ticket.solution_proposed", {"solution_id": solution.pk})
        log_activity(request.user, "ticket.solution_proposed", "Ticket", ticket.pk, ticket.ticket_number)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdminOrManagerOrMaintenance])
    def validate(self, request, pk=None):
        ticket = self.get_object()
        if not ticket.can_validate():
            raise ValidationError("Validation non autorisée dans cet état.")
        serializer = TicketValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        reason = serializer.validated_data.get("reason", "")
        if decision == "REFUSED" and not reason:
            raise ValidationError("Un motif est requis en cas de refus.")

        next_status = {
            "ACCEPTED": TicketStatus.INTERVENING,
            "REFUSED": TicketStatus.DIAGNOSING,
            "INFO_REQUESTED": TicketStatus.DIAGNOSING,
            "ONSITE_REQUESTED": TicketStatus.INTERVENING,
            "VIDEOCALL_REQUESTED": TicketStatus.DIAGNOSING,
        }[decision]
        self._transition(ticket, next_status, request.user, decision=decision, reason=reason)
        notify_validation_decision(ticket, decision, reason)
        broadcast_ticket_event(ticket, "ticket.status_changed", {"decision": decision})
        log_activity(request.user, "ticket.validated", "Ticket", ticket.pk, f"{ticket.ticket_number}: {decision}")
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdminOrManagerOrMaintenance])
    def close(self, request, pk=None):
        ticket = self.get_object()
        if not ticket.can_close():
            raise ValidationError("Clôture non autorisée dans cet état.")
        serializer = TicketCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        restarted_at = data.get("restarted_at") or timezone.now()
        total_downtime_min = int((restarted_at - ticket.downtime_start).total_seconds() / 60) if ticket.downtime_start else 0

        ticket.downtime_end = restarted_at
        TicketClosure.objects.create(
            ticket=ticket,
            repair_conforms=data.get("repair_conforms", True),
            machine_back_in_service=data.get("machine_back_in_service", True),
            restarted_at=restarted_at,
            total_downtime_min=max(total_downtime_min, 0),
            intervention_duration_min=data.get("intervention_duration_min"),
            parts_replaced=data.get("parts_replaced", ""),
            intervention_cost=data.get("intervention_cost"),
            closed_by=request.user,
        )
        # Resolved happens implicitly on the way to Closed for tickets that
        # skip straight from INTERVENING; keep both events for anyone
        # listening only for "resolved".
        if ticket.status != TicketStatus.RESOLVED:
            notify_ticket_resolved(ticket)
        self._transition(ticket, TicketStatus.CLOSED, request.user)
        broadcast_ticket_event(ticket, "ticket.closed")
        log_activity(request.user, "ticket.closed", "Ticket", ticket.pk, ticket.ticket_number)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        ticket = self.get_object()
        text = (request.data.get("text") or "").strip()
        if not text:
            raise ValidationError("Commentaire vide.")
        request_type = request.data.get("request_type") or ""
        if request_type and request_type not in CommentRequestType.values:
            raise ValidationError("Type de demande invalide.")
        comment = TicketComment.objects.create(
            ticket=ticket, user=request.user, text=text, request_type=request_type,
        )
        notify_ticket_comment(ticket)
        broadcast_ticket_event(ticket, "ticket.commented", {"comment_id": comment.pk})
        return Response(TicketCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated],
            parser_classes=[MultiPartParser])
    def add_attachment(self, request, pk=None):
        ticket = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            raise ValidationError("Aucun fichier fourni.")
        solution = None
        solution_id = request.data.get("solution")
        if solution_id:
            # Must belong to this same ticket — otherwise a caller could tag
            # a file onto an unrelated ticket's solution.
            solution = ticket.solutions.filter(pk=solution_id).first()
            if not solution:
                raise ValidationError("Solution introuvable pour ce ticket.")
        attachment = TicketAttachment.objects.create(
            ticket=ticket, solution=solution, file=file_obj,
            category=request.data.get("category", "PHOTO"),
            uploaded_by=request.user,
        )
        notify_new_media(ticket, uploaded_by_supplier=request.user.role == "SUPPLIER")
        broadcast_ticket_event(ticket, "ticket.attachment_added", {"attachment_id": attachment.pk})
        return Response(TicketAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)

    # --- export -----------------------------------------------------------
    @action(detail=False, methods=["get"])
    def export_pdf(self, request):
        return export_tickets_pdf(self.filter_queryset(self.get_queryset()))

    @action(detail=False, methods=["get"])
    def export_excel(self, request):
        return export_tickets_excel(self.filter_queryset(self.get_queryset()))

    # --- helpers ------------------------------------------------------
    @staticmethod
    def _attribute_supplier(ticket, user):
        """First supplier action on a ticket claims it, for unambiguous
        "pannes par fournisseur" reporting even if several suppliers are
        assigned to the same machine."""
        if not ticket.assigned_supplier_id:
            ticket.assigned_supplier = user
            ticket.save(update_fields=["assigned_supplier"])

    @staticmethod
    def _transition(ticket, to_status, user, decision="", reason=""):
        from_status = ticket.status
        ticket.status = to_status
        ticket.save(update_fields=["status", "updated_at"])
        TicketStatusLog.objects.create(
            ticket=ticket, from_status=from_status, to_status=to_status,
            decision=decision, reason=reason, changed_by=user,
        )
        # get_object()'s queryset prefetches attachments/comments/status_logs/
        # solutions/closure; those caches go stale the moment this (or an
        # earlier step in the same action, e.g. propose_solution/close
        # creating a SupplierSolution/TicketClosure first) creates a new
        # related row. Drop the cache so the response serializer re-queries
        # and actually reflects what was just created.
        ticket.refresh_from_db()


@extend_schema(tags=["Support"])
class SupportKPIsView(APIView):
    """Aggregate KPIs for the SAV module: response/resolution time, MTTR/MTBF,
    ticket volume by machine/supplier. Mirrors apps.dashboard.views'
    .values(...).annotate(Avg/Count) style."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        start = timezone.now() - timedelta(days=days)
        closed = Ticket.objects.filter(status=TicketStatus.CLOSED, closure__closed_at__gte=start)

        by_machine = list(
            closed.values("machine__code")
            .annotate(count=Count("id"), avg_downtime=Avg("closure__total_downtime_min"))
            .order_by("-count")
        )
        for row in by_machine:
            row["mttr_min"] = round(row.pop("avg_downtime") or 0, 1)
            # MTBF approximation: calendar window / failure count for that
            # machine (no operating-hours data source wired in yet).
            row["mtbf_min"] = round((days * 1440) / row["count"], 1) if row["count"] else None

        by_supplier = list(
            closed.exclude(assigned_supplier__isnull=True)
            .values("assigned_supplier__first_name", "assigned_supplier__last_name")
            .annotate(count=Count("id"), avg_cost=Avg("closure__intervention_cost"), total_cost=Sum("closure__intervention_cost"))
            .order_by("-count")
        )
        for row in by_supplier:
            row["supplier_name"] = f"{row.pop('assigned_supplier__first_name')} {row.pop('assigned_supplier__last_name')}".strip()
            row["avg_cost"] = round(row["avg_cost"], 2) if row["avg_cost"] is not None else None
            row["total_cost"] = round(row["total_cost"], 2) if row["total_cost"] is not None else None

        cost_agg = closed.aggregate(avg_cost=Avg("closure__intervention_cost"), total_cost=Sum("closure__intervention_cost"))

        solutions = SupplierSolution.objects.filter(ticket__status=TicketStatus.CLOSED, proposed_at__gte=start)
        # Average time from ticket creation to first supplier solution.
        response_minutes = []
        for sol in solutions.select_related("ticket"):
            delta = (sol.proposed_at - sol.ticket.created_at).total_seconds() / 60
            response_minutes.append(delta)
        avg_response_min = round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None

        resolution_minutes = list(
            closed.select_related("closure").values_list("created_at", "closure__closed_at")
        )
        res_deltas = [
            (closed_at - created_at).total_seconds() / 60
            for created_at, closed_at in resolution_minutes if closed_at
        ]
        avg_resolution_min = round(sum(res_deltas) / len(res_deltas), 1) if res_deltas else None

        # Flat, one-row-per-closed-ticket list — unlike by_machine/by_supplier
        # above (grouped aggregates), this is the spec's "historique des
        # interventions" / "pièces remplacées" report: every closure in the
        # window, so nothing needs cross-referencing individual tickets.
        interventions = [
            {
                "ticket_number": t.ticket_number,
                "machine_code": t.machine.code,
                "supplier_name": t.assigned_supplier.full_name if t.assigned_supplier_id else None,
                "closed_at": t.closure.closed_at,
                "total_downtime_min": t.closure.total_downtime_min,
                "parts_replaced": t.closure.parts_replaced,
                "intervention_cost": t.closure.intervention_cost,
            }
            for t in closed.select_related("machine", "assigned_supplier", "closure").order_by("-closure__closed_at")
        ]

        return Response({
            "window_days": days,
            "ticket_count": closed.count(),
            "avg_supplier_response_min": avg_response_min,
            "avg_resolution_min": avg_resolution_min,
            "avg_intervention_cost": round(cost_agg["avg_cost"], 2) if cost_agg["avg_cost"] is not None else None,
            "total_intervention_cost": round(cost_agg["total_cost"], 2) if cost_agg["total_cost"] is not None else None,
            "by_machine": by_machine,
            "by_supplier": by_supplier,
            "interventions": interventions,
        })
