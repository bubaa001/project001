from django.apps import AppConfig


class SyncManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sync_manager'
    verbose_name = 'Offline Sync Manager'

    def ready(self):
        # Import signals and register them to wire up post_save/post_delete
        from sync_manager.signals import register_signals
        register_signals()

        # Create schedule records in the django_q database table.
        # These drive the cron-like background sync every 60 seconds.
        self._ensure_schedules()

    @staticmethod
    def _ensure_schedules():
        """Idempotent: create django-q2 Schedule records if they don't exist."""
        try:
            from django_q.models import Schedule
            from django.utils import timezone

            schedule, created = Schedule.objects.get_or_create(
                name='sync_all_pending',
                defaults={
                    'func': 'sync_manager.scheduler.sync_all_pending',
                    'schedule_type': Schedule.MINUTES,
                    'minutes': 1,          # run every 1 minute
                    'repeats': -1,          # forever
                    'next_run': timezone.now(),
                },
            )
            if created:
                import logging
                logger = logging.getLogger('sync_manager')
                logger.info("Created schedule: %s (runs every %s min)",
                            schedule.name, schedule.minutes)
        except Exception:
            pass  # table doesn't exist yet during first migrate
