from django.db import models
from django.utils import timezone


class PluginConfig(models.Model):
    name = models.CharField(max_length=128, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    configuration = models.JSONField(blank=True)
    identifier = models.CharField(max_length=128)

    class Meta:
        db_table = "plugins_pluginconfiguration"
        managed = False


class MulesoftLog(models.Model):
    url = models.CharField(max_length=255, blank=True, null=True)
    request = models.TextField(null=True, blank=True)
    response = models.TextField(null=True, blank=True)
    exception = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    retry = models.BooleanField(default=False)
    # opts
    feature = models.CharField(max_length=255, blank=True, null=True)
    order_number = models.CharField(max_length=255, blank=True, null=True)
    orderid = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "mulesoft_api_logs"


class PmtMaterialMaster(models.Model):
    material_code = models.CharField(max_length=50, unique=True)
    is_hold = models.BooleanField(default=False)
    hold_remark = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "pmt_material_master"
