import json
import logging
import uuid

from django.core.exceptions import ImproperlyConfigured, ValidationError

from saleor.plugins.manager import get_plugins_manager
from scgp_po_upload.graphql.enums import PoUploadType, SaveToSapStatus
from scgp_po_upload.implementations.excel_upload_validation import (
    _validate_excel_upload_file,
)
from scgp_po_upload.implementations.po_upload import update_status_po_file_log
from scgp_po_upload.models import PoUploadFileLog


def validate_excel_upload_file(
    user, file, order_type, sale_org, distribution_channel, division, upload_type
):
    """
    validate po file and mapping some field. If success, save file and create file log instance.
    """
    try:
        orders = _validate_excel_upload_file(file, sale_org, distribution_channel)
        extra_info = json.dumps(
            {
                "order_type": order_type,
                "sale_org": sale_org,
                "distribution_channel": distribution_channel,
                "division": division,
                "upload_type": upload_type,
            }
        )
        file_log_instance = PoUploadFileLog.objects.create(
            file_name=file.name,
            po_numbers=None,
            upload_type=PoUploadType.EXCEL,
            file=file,
            status=SaveToSapStatus.UPLOAD_FILE,
            uploaded_by=user,
            extra_info=extra_info,
        )
        logging.info(
            f"[Excel Upload] validate_po_file: updated file log status id: '{file_log_instance.id}' status: '{file_log_instance.status}'"
        )
        write_to_queue(file_log_instance.id)
        update_status_po_file_log(file_log_instance, SaveToSapStatus.UPLOAD_FILE)
        return orders, file_log_instance
    except ValidationError as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise ImproperlyConfigured("Internal Server Error.")


def write_to_queue(file_log_instance_id):
    try:
        file_log_instance = PoUploadFileLog.objects.get(id=file_log_instance_id)

        manager = get_plugins_manager()
        po_upload_sns = manager.get_plugin("scg.sns_po_upload")
        sns_response = po_upload_sns.sns_send_message(
            subject="sns_excel_upload",
            message=str(file_log_instance.id),
            message_attributes={},
            message_group_id="sns_excel_upload",
            message_deduplication_id=str(uuid.uuid1().int),
            connect_timeout=120,
            read_timeout=120,
        )
        logging.info(
            f"[Excel Upload] validate_excel_file :sns send message {file_log_instance.id if file_log_instance else None}"
        )
        logging.info(f"[Excel Upload] sns_response: {sns_response}")
        if sns_response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise ImproperlyConfigured(f"sns sent message failed: {sns_response}")
        update_status_po_file_log(file_log_instance, SaveToSapStatus.IN_QUEUE)
        return file_log_instance
    except PoUploadFileLog.DoesNotExist:
        raise ImproperlyConfigured(
            f"invalid id given to upload to queue {file_log_instance_id}"
        )
    except ValidationError as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise ImproperlyConfigured("Internal Server Error.")
