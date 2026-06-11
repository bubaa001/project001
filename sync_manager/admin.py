from django.contrib import admin
from .models import SyncRecord


@admin.register(SyncRecord)
class SyncRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'action', 'table_name', 'row_id',
                    'retry_count', 'created_at', 'synced_at')
    list_filter = ('status', 'action', 'table_name')
    search_fields = ('table_name', 'error_message')
    readonly_fields = ('created_at', 'synced_at', 'retry_count')
    ordering = ('-created_at',)
