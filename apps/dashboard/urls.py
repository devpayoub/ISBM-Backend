from django.urls import path

from .views import KPIsView, MachinesStatusView, MaterialsOverviewView, ParetoView, ShiftReportView

urlpatterns = [
    path("kpis", KPIsView.as_view(), name="dashboard-kpis"),
    path("machines-status", MachinesStatusView.as_view(), name="dashboard-machines-status"),
    path("pareto", ParetoView.as_view(), name="dashboard-pareto"),
    path("shift-report", ShiftReportView.as_view(), name="dashboard-shift-report"),
    path("materials-overview", MaterialsOverviewView.as_view(), name="dashboard-materials-overview"),
]
