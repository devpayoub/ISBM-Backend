from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "apps.alerts"
    verbose_name = "Alertes temps réel"

    def ready(self):
        from django.conf import settings
        from django_celery_beat.models import IntervalSchedule, PeriodicTask
        from django.db.utils import OperationalError, ProgrammingError

        try:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=2, period=IntervalSchedule.MINUTES,
            )
            PeriodicTask.objects.update_or_create(
                name="alerts:check-escalations",
                defaults={
                    "task": "apps.alerts.tasks.check_escalations",
                    "interval": schedule,
                    "enabled": True,
                },
            )
        except (OperationalError, ProgrammingError):
            pass
