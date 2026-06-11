from django.apps import AppConfig


class SyncManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sync_manager'
    verbose_name = 'Offline Sync Manager'

    def ready(self):
        # Import signals and register them to wire up post_save/post_delete
        from sync_manager.signals import register_signals
        register_signals()
