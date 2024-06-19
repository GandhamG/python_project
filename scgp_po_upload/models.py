from django.db import models

from saleor.account.models import User
from sap_master_data.models import SoldToMaster
from scgp_po_upload.graphql.enums import PoUploadType, SaveToSapStatus
from scgp_po_upload.s3_storage import EOrderingS3Storage


class PoUploadFileLog(models.Model):
    file_name = models.CharField(max_length=255, blank=False, null=False)
    po_numbers = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    extra_info = models.JSONField(blank=True, null=True)
    upload_type = models.CharField(
        choices=PoUploadType.CHOICES, default=PoUploadType.TXT, max_length=1
    )
    status = models.CharField(
        choices=SaveToSapStatus.CHOICES,
        default=SaveToSapStatus.BEING_PROCESS,
        max_length=255,
    )
    note = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(
        upload_to="po_upload_files", blank=True, storage=EOrderingS3Storage()
    )
    uploaded_by = models.ForeignKey(
        User, related_name="po_upload_file_logs", on_delete=models.CASCADE, null=True
    )


class PoUploadCustomerSettings(models.Model):
    sold_to = models.ForeignKey(SoldToMaster, on_delete=models.CASCADE)
    use_customer_master = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
