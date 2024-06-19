from scgp_po_upload.graphql.enums import SaveToSapStatus
from scgp_po_upload.implementations.excel_upload_validation import validate_file_name
from scgp_po_upload.models import PoUploadFileLog, PoUploadCustomerSettings
from sap_master_data import models as sap_master_data_models


def resolve_fail_files():
    return PoUploadFileLog.objects.filter(status=SaveToSapStatus.BEING_PROCESS).all()


def resolve_po_upload_customer_settings():
    return PoUploadCustomerSettings.objects.all()


def get_all_record_sold_to_master():
    return sap_master_data_models.SoldToMaster.objects.all()
