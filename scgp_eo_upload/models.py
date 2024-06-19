import enum

from django.db import models


class EoUploadLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True, blank=True)
    message_attributes = models.JSONField(null=True, blank=True)
    # TODO: update field that ends with _id to id
    message_group_id = models.CharField(max_length=64, null=True, blank=True)
    message_deduplication_id = models.CharField(max_length=64, null=True, blank=True)
    payload = models.JSONField(blank=True, null=True)
    orderid = models.IntegerField(blank=True, null=True)
    order_type = models.CharField(max_length=64, blank=True, null=True)
    state = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    log_key = models.CharField(max_length=256, blank=True, null=True)
    eo_no = models.CharField(max_length=64, blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    is_summary_email_send = models.BooleanField(default=False, blank=True, null=True)


class EoUploadLogOrderType(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    SPLIT = "split"
