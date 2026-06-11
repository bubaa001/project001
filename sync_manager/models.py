"""
Outbox Pattern: SyncRecord captures every local write and queues it for
remote sync to Supabase PostgreSQL by the django-q2 background cluster.
"""
from django.db import models
from django.utils import timezone


class SyncRecord(models.Model):
    """
    A single pending / processed / failed sync operation.
    One SyncRecord = one row that needs to be pushed upstream.
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ]

    table_name = models.CharField(max_length=100, db_index=True)
    row_id = models.BigIntegerField(db_index=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True,
    )

    # Serialised JSON payload of the full row (all fields)
    payload_json = models.JSONField(default=dict)

    # File paths that need uploading to Supabase Storage (list of local paths)
    file_paths = models.JSONField(default=list, blank=True)

    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['table_name', 'row_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['table_name', 'row_id', 'action']),
        ]

    def __str__(self):
        return f"[{self.status}] {self.action} {self.table_name}#{self.row_id}"

    def mark_synced(self):
        self.status = 'synced'
        self.synced_at = timezone.now()
        self.save(update_fields=['status', 'synced_at'])

    def mark_failed(self, error_msg: str):
        self.status = 'failed'
        self.retry_count += 1
        self.error_message = error_msg[:2000]
        self.save(update_fields=['status', 'retry_count', 'error_message'])

    def mark_pending(self):
        self.status = 'pending'
        self.save(update_fields=['status'])
