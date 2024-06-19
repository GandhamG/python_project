import io
import json
import logging
import re
import time
import uuid
from datetime import datetime
from functools import reduce

import magic
import pandas as pd
import pytz
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.utils import timezone

from common.cp.cp_helper import filter_cp_order_line
from common.enum import MulesoftServiceType
from common.helpers import (
    DateHelper,
    format_sap_decimal_values_for_pdf,
    mock_confirm_date,
)
from common.mulesoft_api import MulesoftApiRequest
from common.newrelic_metric import add_metric_process_order, force_update_attributes
from common.sap.sap_api import SapApiRequest
from saleor.plugins.manager import get_plugins_manager
from sap_master_data import models as master_models
from sap_master_data.models import (
    SoldToMaster,
    SoldToMaterialMaster,
    SoldToPartnerAddressMaster,
    SoldToTextMaster,
)
from sap_migration import models as migration_models
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import (
    Contract,
    ContractMaterial,
    MaterialVariantMaster,
    Order,
    OrderLineIPlan,
    OrderLines,
)
from scg_checkout.contract_order_update import is_order_contract_project_name_special
from scg_checkout.graphql.enums import (
    CIP_BU,
    AtpCtpStatus,
    DocType,
    ExcelUploadHeaderColumn,
    IPLanConfirmStatus,
    IPlanOrderItemStatus,
    IPLanResponseStatus,
    PaymentTerm,
    ScgOrderStatus,
    ScgOrderStatusSAP,
)
from scg_checkout.graphql.helper import (
    PAYMENT_TERM_MAPPING,
    convert_date_time_timezone_asia,
    convert_date_time_to_timezone_asia,
    delete_order_in_db_to_avoid_duplication,
    get_alternated_material_errors,
    get_alternated_material_related_data,
    get_date_time_now_timezone_asia,
    get_internal_emails_by_config,
    get_product_group_from_es_17,
    get_sold_to_partner,
    get_summary_details_from_data,
)
from scg_checkout.graphql.implementations.iplan import (
    confirm_i_plan,
    get_contract_no_name_from_order,
    get_external_emails_by_config,
    get_material_variant_description_en_from_order_line,
    get_payment_method_name_from_order,
    get_po_number_from_order,
    get_sale_org_name_from_order,
    get_sold_to_no_name,
    get_stands_for_company,
    po_upload_request_i_plan,
    send_mail_customer_fail_alternate,
    update_order_line_after_call_i_plan,
)
from scg_checkout.graphql.implementations.orders import ASIA_BANGKOK_TIMEZONE
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_create_order,
    get_excel_upload_order_level_error_message,
    get_order_partner,
)
from scg_checkout.graphql.resolves.contracts import (
    get_data_from_order_text_list,
    map_sap_contract_item,
    sap_mapping_contract_material_variant,
)
from scgp_cip.common.enum import CPRequestType
from scgp_cip.dao.order.sale_organization_master_repo import SalesOrganizationMasterRepo
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.service.create_order_service import (
    call_cp,
    call_es16_for_excel_upload,
    create_cip_order_excel,
)
from scgp_cip.service.excel_upload_service import send_email_for_excel_upload_orders
from scgp_export.graphql.enums import ItemCat, SapEnpoint, TextID
from scgp_export.graphql.resolvers.export_sold_tos import resolve_sold_to_name
from scgp_export.implementations.sap import get_web_user_name

# from scgp_po_upload.error_codes import ScgpPoUploadErrorCode
from scgp_po_upload.graphql.enums import (
    BeingProcessConstants,
    ContractErrorMessage,
    IPlanAcknowledge,
    PoUploadMode,
    PoUploadType,
    ResponseCodeES17,
    SapType,
    SaveToSapStatus,
    UploadType,
)
from scgp_po_upload.graphql.helpers import (
    get_i_plan_error_messages,
    get_item_level_message,
    html_to_pdf,
    load_error_message,
    validate_order_msg,
)
from scgp_po_upload.implementations.po_upload_validation import (  # fetch_and_validate_product_group,
    _validate_po_file,
    validate_duplicate_po_for_customer_user,
    validate_file_content,
)
from scgp_po_upload.models import PoUploadCustomerSettings, PoUploadFileLog
from scgp_require_attention_items.graphql.helper import update_attention_type_r5
from scgp_user_management.models import (
    EmailConfigurationExternal,
    EmailConfigurationFeatureChoices,
    EmailConfigurationInternal,
)


@transaction.atomic
def validate_po_file(user, file, sold_to_code=None):
    """
    validate po file and mapping some field. If success, save file and create file log instance.
    """
    try:
        orders = _validate_po_file(user, file, sold_to_code=sold_to_code)
        po_numbers = [order["po_number"] for order in orders]
        file_log_instance = PoUploadFileLog.objects.create(
            file_name=file.name,
            po_numbers=po_numbers,
            file=file,
            status=SaveToSapStatus.UPLOAD_FILE,
            uploaded_by=user,
        )
        logging.info(
            f"[PO Upload] validate_po_file: updated file log status id: '{file_log_instance.id}' status: '{file_log_instance.status}'"
        )
        manager = get_plugins_manager()
        po_upload_sns = manager.get_plugin("scg.sns_po_upload")
        sns_response = po_upload_sns.sns_send_message(
            subject="sns_po_upload",
            message=str(file_log_instance.id),
            message_attributes={},
            message_group_id="sns_po_upload",
            message_deduplication_id=str(uuid.uuid1().int),
            connect_timeout=120,
            read_timeout=120,
        )
        logging.info(
            f"[PO Upload] validate_po_file :sns send message {file_log_instance.id if file_log_instance else None}"
        )
        logging.info(f"[PO Upload] sns_response: {sns_response}")
        if sns_response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise ImproperlyConfigured(f"sns sent message failed: {sns_response}")
        update_status_po_file_log(file_log_instance, SaveToSapStatus.IN_QUEUE)
        return orders, file_log_instance
    except ValidationError as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise ImproperlyConfigured("Internal Server Error.")


def retry_upload_file(id):
    po_log_file = PoUploadFileLog.objects.filter(
        id=id, status=SaveToSapStatus.BEING_PROCESS
    ).first()
    if po_log_file is not None:
        # Public message to SNS
        manager = get_plugins_manager()
        po_upload_sns = manager.get_plugin("scg.sns_po_upload")
        sns_response = po_upload_sns.sns_send_message(
            subject="sns_po_upload",
            message=str(po_log_file.id),
            message_attributes={},
            message_group_id="sns_po_upload",
            message_deduplication_id=str(uuid.uuid1().int),
            connect_timeout=120,
            read_timeout=120,
        )
        logging.info(f"[PO Upload] sns_response: {sns_response}")
        if sns_response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise ImproperlyConfigured(f"sns sent message failed: {sns_response}")
        logging.info(f"[PO Upload] retry_upload_file {po_log_file.id}")
        update_status_po_file_log(po_log_file, SaveToSapStatus.IN_QUEUE)
        return True

    return False


def po_upload_to_sap():
    """
    System will call I-Plan to reserve stock
    AND Call SAP to save order
    AND Get Response from SAP [Auto Accept or Roll Back]
    @return:
    """
    # need to check on different thread
    file_log = get_po_upload_running()
    if file_log:
        logging.info(
            f"[PO Upload] po_upload_to_sap : file log {file_log.id} is running, skip"
        )
        return
    manager = get_plugins_manager()
    po_upload = manager.get_plugin("scg.sqs_po_upload")
    messages = po_upload.sqs_receive_message()
    logging.info(f"[PO Upload] po_upload_to_sap : get data from sqs {messages}")
    msgs = []
    for message in messages:
        msgs.append(message.body)
        message.delete()
    logging.info(f"[PO Upload] po_upload_to_sap : all po on sqs {msgs}")
    for msg in msgs:
        file_log = get_file_log_instance(msg)
        if not file_log:
            return True
        if PoUploadType.EXCEL == file_log.upload_type:
            handle_excel_upload(file_log, manager)
        else:
            handle_po_file(file_log, manager)


def get_file_log_instance(msg):
    body = json.loads(msg)
    file_id = body.get("Message")
    logging.info(f"[PO Upload] handle_po_file: {file_id}")
    return PoUploadFileLog.objects.filter(id=file_id).first()


def handle_po_file(file_log, manager):
    """
    Get and handle file by SQS message
    @param file_log: file log instance
    @param manager:
    @return: Boolean: Handle success or not
    """
    file_id = file_log.id
    try:
        result, is_being_process, _ = save_po_order(file_log, manager)
        if result:
            file_log_status = (
                SaveToSapStatus.SUCCESS
                if not is_being_process
                else SaveToSapStatus.BEING_PROCESS
            )
            update_status_po_file_log(file_log, file_log_status)
            logging.info(f"[PO Upload] success process: {file_id}")
            return True

        # Update file status is fail
        file_log_status = (
            SaveToSapStatus.FAIL
            if not is_being_process
            else SaveToSapStatus.BEING_PROCESS
        )
        update_status_po_file_log(file_log, file_log_status)
        if is_being_process:
            logging.info(f"[PO Upload] being process: {file_id}")
        else:
            logging.info(f"[PO Upload] failed process: {file_id}")
        return True
    except Exception as e:
        update_status_po_file_log(file_log, SaveToSapStatus.FAIL)
        logging.exception(
            f"[PO Upload] handle_po_file: Error occurs when handle file {file_id}"
        )
        send_mail_po_upload_when_exceptions(e, file_log, manager)
        return False


def build_failed_order_line_data(
    failed_order_lines, item_no_excel_line_dic, sap_item_msg, sap_so_no
):
    order_lines_for_mail_list = []

    for failed_line in failed_order_lines:
        item_no = failed_line.item_no
        excel_row = item_no_excel_line_dic.get(failed_line.item_no)
        order_line_for_mail = {
            "so_no": sap_so_no,
            "mat_code": failed_line.customer_mat_35
            if failed_line.customer_mat_35
            else failed_line.material_code,
            "mat_desc": excel_row.get("material_description")
            if excel_row and excel_row.get("material_description")
            else "",
            "error": sap_item_msg.get(item_no),
            "line_no": excel_row.get("line_no")
            if excel_row and excel_row.get("line_no")
            else "",
        }
        order_lines_for_mail_list.append(order_line_for_mail)
    return order_lines_for_mail_list


def build_failed_order_data(
    failed_order_lines,
    order_db_data,
    item_no_excel_line_dic,
    sap_item_msg,
    sap_so_no=None,
):
    sold_to_data = order_db_data.sold_to
    return {
        "sold_to_code": sold_to_data.sold_to_code,
        "sold_to_name": resolve_sold_to_name(sold_to_data.sold_to_code),
        "po_number": order_db_data.po_number,
        "lines": build_failed_order_line_data(
            failed_order_lines, item_no_excel_line_dic, sap_item_msg, sap_so_no
        ),
    }


def build_failed_order_data_when_exception(items):
    sold_to_code = items[0].get("sold_to").zfill(10)
    sold_to = SoldToMasterRepo.get_sold_to_data(sold_to_code)
    order_lines = []
    for item in items:
        order_line = {
            "so_no": None,
            "mat_code": item.get("material_code"),
            "mat_desc": item.get("material_description"),
            "error": "Error in creating order in db",
            "line_no": item.get("line_no"),
        }
        order_lines.append(order_line)

    return {
        "sold_to_code": sold_to_code,
        "sold_to_name": sold_to.sold_to_name if sold_to else None,
        "po_number": items[0].get("po_number"),
        "lines": order_lines,
    }


@transaction.atomic
def process_row(header_data, items, file_log):
    failed_order_data = {}
    order_lines = []
    order = None
    item_no_excel_line_dic = {}
    try:
        order, order_lines, item_no_excel_line_dic = create_cip_order_excel(
            header_data, items, file_log.uploaded_by
        )
        cp_order_lines = filter_cp_order_line(order_lines)
        if cp_order_lines:
            call_cp(
                order,
                order.so_no,
                cp_order_lines,
                CPRequestType.NEW.value,
                is_excel_upload=True,
            )
        (
            sap_response,
            sap_success,
            order_item_message,
            sap_order_messages,
            is_order_created,
        ) = call_es16_for_excel_upload(order, order_lines)
        sap_so_no = sap_response.get("salesdocument")
        logging.info(
            f"[Excel Upload]- so_no:{sap_response.get('salesdocument')} order_item_message:{order_item_message}, sap_order_messages: {sap_order_messages}, is_order_created: {is_order_created}"
        )
        failed_order_lines = _segregate_failed_order_line_for_excel_upload(
            order_item_message, order_lines
        )
        if len(sap_order_messages) > 0:
            sap_item_msg = get_excel_upload_order_level_error_message(
                order_item_message, sap_order_messages, order_lines
            )
            failed_order_data = build_failed_order_data(
                order_lines,
                order,
                item_no_excel_line_dic,
                sap_item_msg,
                sap_so_no,
            )
        elif failed_order_lines:
            failed_order_data = build_failed_order_data(
                failed_order_lines,
                order,
                item_no_excel_line_dic,
                order_item_message,
                sap_so_no,
            )
        if not is_order_created:
            transaction.set_rollback(True)
        return failed_order_data, order.saved_sap_at
    except Exception as e:
        if order and len(order_lines) > 0:
            sap_item_messages = get_common_error_message(
                order_lines, "Unable to connect to SAP or CP"
            )
            failed_order_data = build_failed_order_data(
                order_lines, order, item_no_excel_line_dic, sap_item_messages, None
            )
        else:
            logging.exception(f"[Excel Upload] Failed to create excel order: {e}")
            failed_order_data = build_failed_order_data_when_exception(items)
        transaction.set_rollback(True)
        logging.exception(f"[Excel Upload] Failed to process excel order: {e}")
        return failed_order_data, None


def get_common_error_message(order_lines, error_message):
    sap_item_messages = {}
    for line in order_lines:
        sap_item_messages[line.item_no] = error_message
    return sap_item_messages


def get_to_and_cc_for_excel_upload(uploaded_by, sale_org_code):
    mail_to = []
    internal_emails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.EXCEL_UPLOAD, sale_org_code, "", CIP_BU
    )
    mail_to.append(uploaded_by.email)
    cc_to = internal_emails
    return mail_to, cc_to


def build_mail_data(
    fail_order_list, file_log, order_status_count, ui_parsed_data, sap_save_date_time
):
    sale_org_code = ui_parsed_data.get("sale_org")
    uploaded_by = file_log.uploaded_by
    sale_org = SalesOrganizationMasterRepo.get_sale_organization_by_code(sale_org_code)
    mail_to, cc_to = get_to_and_cc_for_excel_upload(uploaded_by, sale_org_code)
    mail_params = {
        "to": mail_to,
        "cc": cc_to,
        "sale_org_code": sale_org_code,
        "sale_org_name": sale_org.name,
        "file": file_log.file_name,
        "save_sap_date_time": sap_save_date_time.astimezone(
            pytz.timezone(ASIA_BANGKOK_TIMEZONE)
        ).strftime("%d-%m-%Y %H:%M:%S")
        if sap_save_date_time
        else None,
        "uploader": f"{uploaded_by.first_name} {uploaded_by.last_name}",
        "total_number_of_order": order_status_count.get("total_orders"),
        "total_fail_order": order_status_count.get("total_fail"),
        "total_partial_success_order": order_status_count.get("partial_fail"),
        "total_success_orders": order_status_count.get("total_success"),
        "sale_org_short_name": sale_org.short_name,
        "upload_date_time": file_log.created_at,
        "order_status_details": fail_order_list,
    }
    return mail_params


def handle_excel_upload(file_log, manager=None):
    logging.info("[Excel Upload] starting excel processing")
    ui_data = file_log.extra_info
    ui_parsed_data = None
    if ui_data:
        try:
            ui_parsed_data = json.loads(ui_data)
        except ValueError:
            logging.exception(
                f"[Excel Upload] handle_excel_upload: Error while parsing UI data json {ui_data}"
            )
            return
        if ui_parsed_data:
            file_object = file_log.file
            if file_object:
                mapped_excel_data_list = []
                sap_save_date_time = None
                extract_excel_data(file_object, mapped_excel_data_list)
                fail_order_list = []
                order_status_count = {}
                if mapped_excel_data_list:
                    total_orders = 0
                    total_partial_fail = 0
                    if UploadType.GROUP.value == ui_parsed_data.get("upload_type"):
                        group_order_dic = {}
                        for item in mapped_excel_data_list:
                            group_order_dic_key = (
                                f'{item.get("sold_to")}-{item.get("po_number", "")}'
                            )
                            if group_order_dic_key not in group_order_dic:
                                group_order_dic[group_order_dic_key] = []
                            group_order_dic[group_order_dic_key].append(item)
                        for items in group_order_dic.values():
                            failed_order_data, sap_save_time = process_row(
                                ui_parsed_data, items, file_log
                            )
                            total_orders += 1
                            if failed_order_data:
                                fail_order_list.append(failed_order_data)
                            if total_orders == 1:
                                sap_save_date_time = sap_save_time

                            failed_order_lines = failed_order_data.get("lines")
                            if failed_order_lines:
                                if failed_order_lines[0].get("so_no"):
                                    total_partial_fail += 1
                    else:
                        for item in mapped_excel_data_list:
                            failed_order_data, sap_save_time = process_row(
                                ui_parsed_data, [item], file_log
                            )
                            if failed_order_data:
                                fail_order_list.append(failed_order_data)
                            if total_orders == 1:
                                sap_save_date_time = sap_save_time
                            total_orders += 1
                    logging.info(
                        f"[Excel Upload]- failed_order_data:{failed_order_data}"
                    )
                    order_status_count["total_orders"] = total_orders
                    order_status_count["total_fail"] = len(fail_order_list)
                    order_status_count["partial_fail"] = total_partial_fail
                    order_status_count["total_success"] = total_orders - len(
                        fail_order_list
                    )
                    mail_params = build_mail_data(
                        fail_order_list,
                        file_log,
                        order_status_count,
                        ui_parsed_data,
                        sap_save_date_time,
                    )
                    send_email_for_excel_upload_orders(manager, mail_params)
                if len(fail_order_list) > 0:
                    update_status_po_file_log(file_log, SaveToSapStatus.FAIL)
                    logging.info(f"[Excel Upload] process: {file_log.id} failed")
                else:
                    update_status_po_file_log(file_log, SaveToSapStatus.SUCCESS)
                    logging.info(f"[Excel Upload] process: {file_log.id} successful")


def extract_excel_data(file_object, mapped_excel_data_list):
    column_map = ExcelUploadHeaderColumn().find("ALL", "")
    field_type = {col["index"]: "string" for col in column_map}
    df = pd.read_excel(file_object, dtype=field_type, keep_default_na=False)
    sheet_lines = df.values.tolist()
    del sheet_lines[:2]
    excel_line_no = 4
    for line in sheet_lines:
        mapped_excel_data = {}
        for col in column_map:
            mapped_excel_data[col["field"]] = line[col["index"]]
        mapped_excel_data["line_no"] = excel_line_no
        mapped_excel_data_list.append(mapped_excel_data)
        excel_line_no += 1


def get_i_plan_order_lines(i_plan_response):
    if not i_plan_response:
        return [], []
    i_plan_request_error_message = get_i_plan_error_messages(i_plan_response)
    ddq_response = i_plan_response.get("DDQResponse", {})
    i_plan_response_header = ddq_response.get("DDQResponseHeader", [])
    i_plan_order = i_plan_response_header[0]  # Response has only one header
    i_plan_order_lines = i_plan_order["DDQResponseLine"]
    i_plan_order_lines = sorted(
        i_plan_order_lines, key=lambda item: float(item["lineNumber"])
    )
    return i_plan_order_lines, i_plan_request_error_message


def fetch_product_group_of_first_item(sap_success_order_lines, contract_no):
    sap_item = sap_success_order_lines[0]
    material_codes = []
    material_code = sap_item.get("productCode")
    grade_gram_code = material_code[:10]
    material_codes.append(material_code)
    material_codes.append(grade_gram_code)
    contract_material = ContractMaterial.objects.filter(
        material_code__in=material_codes,
        contract_no=contract_no,
    )
    material_data = contract_material.filter(material_code=material_code).first()
    grade_gram_data = contract_material.filter(material_code=grade_gram_code).first()
    product_group = ""
    if material_data:
        product_group = material_data.mat_group_1
    elif grade_gram_data:
        product_group = grade_gram_data.mat_group_1
    return product_group


@transaction.atomic
def save_po_order(file_log, manager):  # noqa: C901
    logging.info("[PO Upload] save_po_order: start ")
    try:
        update_status_po_file_log(file_log, SaveToSapStatus.IN_PROGRESS)
        order_status_dict = {}
        sap_response = {}
        is_being_process = False
        file_object = file_log.file
        file_object = convert_text_file_encoding(file_object, "utf-8")
        user = file_log.uploaded_by
        i_plan_confirm_error_message = []
        order_header_message = []
        orders_data = validate_file_content(
            user, file_object, sold_to_code=None, raise_error=False
        )
        validate_duplicate_po_for_customer_user(user, orders_data)
        validate_items_material(orders_data)
        for order_data in orders_data:
            start_time = time.time()
            try:
                order_item_invalid_material = []
                error_messages = []
                for item in order_data["items"]:
                    if item["error_messages"]:
                        order_item_invalid_material.append(item)
                        for error_message in item["error_messages"]:
                            error_messages.append(
                                item["sku_code"] + " " + error_message
                            )
                try:
                    response = SapApiRequest.call_es_14_contract_detail(
                        contract_no=order_data["contract_number"]
                    )
                except Exception as e:
                    logging.exception(
                        "[PO Upload] Exception during ES14 call for contract "
                        + order_data["contract_number"]
                        + ":"
                        + str(e)
                    )
                    error_message = ContractErrorMessage.TECHNICAL_ERROR
                    error_message_list = [error_message]
                    send_email_after_po_upload_failure(
                        error_message,
                        error_message_list,
                        file_log,
                        is_being_process,
                        manager,
                        order_data,
                    )
                    continue
                if not validate_contract(
                    order_data, manager, file_log, is_being_process, response
                ):
                    continue

                order, _ = save_domestic_order(order_data, user, response)
                order.po_upload_file_log = file_log
                order_status_dict[order.id] = {
                    "order_data": order,
                    "success": True,
                    "error_messages": error_messages,
                    "error_code": [],
                    "order_items_out": [],
                    "is_being_process": False,
                    "is_error_item": False,
                    "save_sap_datetime": None,
                    "error_message_object": None,
                    "order_data_from_file": order_data,
                    "is_sap_or_iplan_failed": False,
                }

                update_status_po_file_log(file_log, SaveToSapStatus.CALL_IPLAN_REQUEST)
                try:
                    (
                        i_plan_response,
                        alt_mat_i_plan_dict,
                        alt_mat_variant_obj_dict,
                        alt_mat_errors,
                    ) = po_upload_request_i_plan(order, manager, order_data)
                    (
                        i_plan_order_lines,
                        i_plan_request_error_message,
                    ) = get_i_plan_order_lines(i_plan_response)
                except Exception as e:
                    logging.info(
                        f"[PO Upload] error occurred when requesting iplan request: {e}"
                    )
                    add_connection_error_message(
                        order,
                        order_item_invalid_material,
                        order_status_dict,
                        sap_response,
                        order_header_message,
                    )
                    continue

                (
                    i_plan_success,
                    failed_order_items,
                    success_order_items,
                    failed_descriptions,
                ) = check_atp_ctp_result(i_plan_order_lines)

                (
                    dict_item_no,
                    dict_order_lines,
                    i_plan_success_order_lines,
                    order_lines,
                ) = update_iplan_order(
                    failed_descriptions,
                    i_plan_order_lines,
                    order,
                    order_status_dict,
                    success_order_items,
                    failed_order_items,
                    alt_mat_i_plan_dict,
                    alt_mat_variant_obj_dict,
                    alt_mat_errors,
                )

                if i_plan_success:
                    if not user.is_staff:
                        po_upload_mode = PoUploadMode.CUSTOMER
                    else:
                        po_upload_mode = PoUploadMode.CS_ADMIN

                    update_status_po_file_log(file_log, SaveToSapStatus.CALL_SAP)

                    try:
                        sap_response = request_create_order_sap(
                            order,
                            manager,
                            [
                                dict_item_no.get(item_no)
                                for item_no in success_order_items
                            ],
                            po_upload_mode,
                        )
                    except Exception as e:
                        logging.exception(
                            f"[PO Upload] error occurred when requesting ES17: {e}"
                        )
                        add_connection_error_message(
                            order,
                            order_item_invalid_material,
                            order_status_dict,
                            sap_response,
                            order_header_message,
                        )
                        continue
                    save_sap_datetime = timezone.now()
                    order.saved_sap_at = save_sap_datetime
                    order_status_dict[order.id][
                        "save_sap_datetime"
                    ] = convert_date_time_timezone_asia(save_sap_datetime)
                    (
                        sap_success,
                        sap_order_messages,
                        sap_item_messages,
                        sap_error_code,
                        order_header_message_from_sap,
                        is_order_being_process,
                        is_sap_item_error,
                        order_item_message,
                    ) = get_error_messages_from_sap_response_for_create_order(
                        sap_response, dict_order_lines, file_upload=True
                    )
                    sap_errors = sap_order_messages + sap_item_messages
                    order_header_message.extend(order_header_message_from_sap)
                    if is_order_being_process:
                        is_being_process = True
                        order_status_dict[order.id]["is_being_process"] = True
                    if is_sap_item_error:
                        order_status_dict[order.id]["is_error_item"] = True

                    (
                        sap_success_order_line,
                        sap_fail_order_line,
                    ) = _segregate_i_plan_success_order_line_to_sap_order_line(
                        i_plan_success_order_lines,
                        sap_response,
                        order_status_dict,
                        order,
                        dict_item_no,
                    )

                    update_status_po_file_log(
                        file_log, SaveToSapStatus.CALL_IPLAN_CONFIRM
                    )
                    if len(sap_success_order_line) != 0:
                        i_plan_response["DDQResponse"]["DDQResponseHeader"][0][
                            "DDQResponseLine"
                        ] = sap_success_order_line
                        # Call i-plan confirm item when sap create order successfully
                        sap_order_number = sap_response.get("salesdocument")
                        try:
                            i_plan_acknowledge = confirm_i_plan(
                                i_plan_response=i_plan_response,
                                status=IPLanConfirmStatus.COMMIT.value,
                                manager=manager,
                                sap_order_number=sap_order_number,
                                sap_response=sap_response,
                                order=order,
                                order_lines=order_lines,
                            )
                        except Exception as e:
                            update_attention_type_r5(order_lines)
                            logging.info(
                                f"[PO Upload] error occurred when requesting iplan confirm: {e}"
                            )
                            add_connection_error_message(
                                order,
                                order_item_invalid_material,
                                order_status_dict,
                                sap_response,
                                order_header_message,
                            )
                            order.so_no = sap_order_number
                            delete_order_in_db_to_avoid_duplication(sap_order_number)
                            order.save()
                            continue
                        i_plan_confirm_error_message = get_i_plan_error_messages(
                            i_plan_acknowledge
                        )
                        check_acknowledge(i_plan_acknowledge, dict_order_lines)
                        update_order_line_with_sap_data(sap_response, dict_order_lines)
                        order.product_group = fetch_product_group_of_first_item(
                            sap_success_order_line, order.contract.code
                        )
                        if not order.product_group:
                            logging.info(
                                f"[PO Upload] Order {order.so_no} product group is blank"
                                f" via Contract material"
                            )
                            order.product_group = get_product_group_from_es_17(
                                sap_response
                            )
                            logging.info(
                                f"[PO Upload] Using ES17 response Order {order.so_no}"
                                f" product group updated to {order.product_group}"
                            )
                        order.status_sap = ScgOrderStatusSAP.COMPLETE.value
                        order.status = ScgOrderStatus.RECEIVED_ORDER.value
                        order.so_no = sap_order_number
                        order.eo_no = sap_order_number
                        delete_order_in_db_to_avoid_duplication(sap_order_number)
                        order.save()
                        order_status_dict[order.id][
                            "success_items"
                        ] = sap_success_order_line

                    if len(sap_fail_order_line) != 0:
                        i_plan_response["DDQResponse"]["DDQResponseHeader"][0][
                            "DDQResponseLine"
                        ] = sap_fail_order_line
                        try:
                            i_plan_acknowledge = confirm_i_plan(
                                i_plan_response=i_plan_response,
                                status=IPLanConfirmStatus.ROLLBACK.value,
                                manager=manager,
                                order=order,
                                order_lines=order_lines,
                            )
                            check_acknowledge(i_plan_acknowledge, dict_order_lines)
                        except Exception as e:
                            update_attention_type_r5(order_lines)
                            logging.info(
                                f"[PO Upload] error occurred when requesting iplan confirm: {e}"
                            )
                            add_connection_error_message(
                                order,
                                order_item_invalid_material,
                                order_status_dict,
                                sap_response,
                                order_header_message,
                            )
                            order.so_no = sap_order_number
                            delete_order_in_db_to_avoid_duplication(sap_order_number)
                            order.save()
                            continue

                        _update_status_order_line(
                            sap_fail_order_line, dict_order_lines, dict_item_no
                        )
                        order_status_dict[order.id]["error_messages"] = list(
                            sap_errors
                        ) + list(set(order_status_dict[order.id]["error_messages"]))
                        order_status_dict[order.id]["error_code"] += sap_error_code

                    if len(sap_success_order_line) == 0:
                        order_status_dict[order.id]["success"] = False

                else:
                    order_status_dict[order.id]["success"] = False
                    order_status_dict[order.id]["is_error_item"] = False

                is_i_plan_error_item_all = (
                    len(i_plan_request_error_message) == len(i_plan_order_lines)
                    or len(i_plan_confirm_error_message) == len(i_plan_order_lines)
                ) or False
                error_message_object = {
                    "order_header_message": order_header_message,
                    "order_item_message": order_item_message if i_plan_success else {},
                    "i_plan_request_error_message": i_plan_request_error_message,
                    "i_plan_confirm_error_message": i_plan_confirm_error_message,
                    "order_item_invalid_material": order_item_invalid_material,
                    "is_i_plan_error_item_all": is_i_plan_error_item_all,
                }
                order_status_dict[order.id][
                    "error_message_object"
                ] = error_message_object
                if order_item_invalid_material:
                    order_status_dict[order.id]["is_error_item"] = True
                if order_status_dict[order.id]["success"]:
                    log_metric(order.id, start_time)
            except Exception as e:
                logging.info(
                    f"[PO Upload] error occurred while processing file {file_log.id}: {e}"
                )
                if type(e) != "ValidationError":
                    error_message = ContractErrorMessage.TECHNICAL_ERROR
                    error_message_list = [error_message]
                    send_email_after_po_upload_failure(
                        error_message,
                        error_message_list,
                        file_log,
                        is_being_process,
                        manager,
                        order_data,
                    )
                    continue
                send_mail_po_upload_when_exceptions(e, file_log, manager)
                return False, False, None

        success = False
        for order_status in order_status_dict.values():
            success = prepare_and_send_mail_after_create_sap_order(
                file_log,
                manager,
                order_status,
                sap_response,
                success,
                user,
            )
            send_mail_customer_fail_alternate(order, manager)
        return (
            success,
            is_being_process,
            order_status_dict,
        )
    except Exception as e:
        logging.info(f"[PO Upload] save_po_order: error exception {str(e)}")
        logging.exception("Error when call I-Plan/SAP: " + str(e))
        send_mail_po_upload_when_exceptions(e, file_log, manager)
        return False, False, None


def send_mail_po_upload_when_exceptions(e, file_log, manager):
    orders_data = validate_file_content(
        file_log.uploaded_by, file_log.file, sold_to_code=None, raise_error=False
    )
    if e.__class__.__name__ == "ValidationError":
        error_message = []
        for errors in dict(e).values():
            for message in errors:
                error_message.append(message)
        error_message_list = error_message
    else:
        error_message = ContractErrorMessage.TECHNICAL_ERROR
        error_message_list = [error_message]
    for order_data in orders_data:
        send_email_after_po_upload_failure(
            error_message=error_message,
            error_message_list=error_message_list,
            file_log=file_log,
            is_being_process=False,
            manager=manager,
            order_data=order_data,
        )


def prepare_and_send_mail_after_create_sap_order(
    file_log,
    manager,
    order_status,
    sap_response,
    success,
    user,
):
    is_error_item_all = False
    if order_status["order_items_out"] == len(order_status["error_code"]) or (
        order_status.get("error_message_object", {}) or {}
    ).get("is_i_plan_error_item_all"):
        is_error_item_all = True
    if order_status["success"]:
        success = True
    try:
        send_email_after_create_sap_order(
            manager,
            user,
            order_status["order_data"],
            file_log,
            order_status["save_sap_datetime"],
            order_partners=sap_response.get("orderPartners", []),
            errors=order_status["error_messages"],
            errors_code=order_status["error_code"],
            is_being_process=order_status["is_being_process"],
            is_error_item=order_status["is_error_item"],
            is_error_item_all=is_error_item_all,
            error_message_object=order_status["error_message_object"],
            order_status=order_status,
            order_data=order_status["order_data_from_file"],
            is_sap_or_iplan_failed=order_status["is_sap_or_iplan_failed"],
        )
    except Exception as e:
        logging.exception("Send mail failed: " + str(e))
        # Delete fail order (draft order)
    if order_status["is_being_process"]:
        order_status["order_data"].delete()
    return success


def update_iplan_order(
    failed_descriptions,
    i_plan_order_lines,
    order,
    order_status_dict,
    success_order_items,
    failed_order_items,
    alt_mat_i_plan_dict=None,
    alt_mat_variant_obj_dict=None,
    alt_mat_errors=None,
):
    # Update iPlan for all item
    qs_order_lines = OrderLines.objects.filter(order=order)
    dict_order_lines = {}
    for qs_order_line in qs_order_lines:
        dict_order_lines[str(qs_order_line.item_no)] = qs_order_line
    for item_no in failed_descriptions.keys():
        mat_description = get_material_variant_description_en_from_order_line(
            dict_order_lines[item_no]
        )
        order_status_dict[order.id]["error_messages"].append(
            f"{mat_description} {failed_descriptions[item_no]}"
            if mat_description
            else f"{dict_order_lines[item_no].material_code} {failed_descriptions[item_no]}"
        )
        order_status_dict[order.id]["is_error_item"] = True
    i_plan_success_order_lines = get_i_plan_success_order_lines(
        i_plan_order_lines, success_order_items
    )
    order_lines = update_order_line_after_call_i_plan(
        dict_order_lines,
        i_plan_order_lines,
        order=order,
        alt_mat_i_plan_dict=alt_mat_i_plan_dict,
        alt_mat_variant_obj_dict=alt_mat_variant_obj_dict,
        alt_mat_errors=alt_mat_errors,
    )
    dict_order_lines = {}
    dict_item_no = {}
    for qs_order_line in order_lines:
        dict_order_lines[str(qs_order_line.item_no)] = qs_order_line
        dict_item_no[str(qs_order_line.original_item_no)] = str(qs_order_line.item_no)
    for order_item in i_plan_success_order_lines:
        e_ordering_order_line = dict_order_lines.get(
            dict_item_no.get(order_item.get("lineNumber").lstrip("0"))
        )
        item_status_en = IPlanOrderItemStatus.ITEM_CREATED.value
        item_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            IPlanOrderItemStatus.ITEM_CREATED.value
        )
        e_ordering_order_line.item_status_en = item_status_en
        e_ordering_order_line.item_status_th = item_status_th
        e_ordering_order_line.original_request_date = dict_order_lines.get(
            e_ordering_order_line.item_no
        ).original_request_date
        e_ordering_order_line.po_item_no = e_ordering_order_line.original_item_no.split(
            "."
        )[0]
        e_ordering_order_line.save()
    for order_item in failed_order_items:
        e_ordering_order_line = dict_order_lines.get(dict_item_no.get(order_item))
        item_status_en = IPlanOrderItemStatus.FAILED.value
        e_ordering_order_line.item_status_en = item_status_en
        e_ordering_order_line.item_status_th = None
        e_ordering_order_line.save()
    return dict_item_no, dict_order_lines, i_plan_success_order_lines, order_lines


def add_connection_error_message(
    order,
    order_item_invalid_material,
    order_status_dict,
    sap_response,
    order_header_message,
):
    order_status_dict[order.id]["success"] = False
    order_status_dict[order.id]["is_error_item"] = False
    order_status_dict[order.id]["error_messages"].append(
        ContractErrorMessage.TECHNICAL_ERROR
    )
    error_message_object = {
        "order_header_message": order_header_message
        + [ContractErrorMessage.TECHNICAL_ERROR],
        "order_item_message": sap_response.get("orderItemsOut", []),
        "i_plan_request_error_message": [],
        "i_plan_confirm_error_message": [],
        "order_item_invalid_material": order_item_invalid_material,
        "is_i_plan_error_item_all": False,
    }
    order_status_dict[order.id]["error_message_object"] = error_message_object
    order_status_dict[order.id]["is_sap_or_iplan_failed"] = True


def check_atp_ctp_result(i_plan_order_lines):
    failed_order_items = []
    success_order_items = []
    failed_description = {}
    i_plan_success = False
    if not i_plan_order_lines:
        return (
            i_plan_success,
            failed_order_items,
            success_order_items,
            failed_description,
        )
    for line in i_plan_order_lines:
        if line["returnStatus"].lower() == IPLanResponseStatus.SUCCESS.value.lower():
            i_plan_success = True
            success_order_items.append(line["lineNumber"])
        else:
            failed_order_items.append(line["lineNumber"])
            failed_description[line["lineNumber"]] = line["returnCodeDescription"]

    return i_plan_success, failed_order_items, success_order_items, failed_description


def save_i_plan_success_item(order, dict_order_lines, i_plan_order_lines):
    """
    Save i-plan success item to eOrdering DB
    @param order: Order in eOrdering
    @param dict_order_lines: List object line request success to iPlan
    @param i_plan_order_lines: All response line from iPlan
    @return:
    """
    e_ordering_order_lines = []
    e_ordering_order_lines_i_plan = []
    for i_plan_line in i_plan_order_lines:
        item_no = i_plan_line.get("lineNumber")
        e_ordering_order_line = dict_order_lines.get(item_no)
        if not e_ordering_order_line:
            continue

        i_plan_on_hand_stock = i_plan_line.get("onHandStock")
        i_plan_operations = i_plan_line.get("DDQResponseOperation") or None
        i_plan_confirm_quantity = i_plan_line.get("quantity")
        i_plan_confirm_date = i_plan_line.get("dispatchDate")
        i_plan_plant = i_plan_line.get("warehouseCode")

        # Update order line i-plan table
        e_ordering_order_line_i_plan = e_ordering_order_line.iplan
        atp_ctp_status = None
        if i_plan_on_hand_stock is True and not i_plan_operations:
            atp_ctp_status = AtpCtpStatus.ATP.value
        elif i_plan_on_hand_stock is False and not i_plan_operations:
            atp_ctp_status = AtpCtpStatus.ATP_FUTURE.value
        elif i_plan_on_hand_stock is False and i_plan_operations:
            atp_ctp_status = AtpCtpStatus.CTP.value

        if not e_ordering_order_line_i_plan:
            e_ordering_order_line_i_plan = OrderLineIPlan.objects.create(
                atp_ctp=atp_ctp_status,
                iplant_confirm_quantity=i_plan_confirm_quantity,
            )
            e_ordering_order_line.iplan = e_ordering_order_line_i_plan
        else:
            e_ordering_order_line_i_plan.atp_ctp_detail = atp_ctp_status
            e_ordering_order_lines_i_plan.append(e_ordering_order_line_i_plan)

        # Update order line table
        e_ordering_order_line.i_plan_on_hand_stock = i_plan_on_hand_stock
        e_ordering_order_line.i_plan_operations = i_plan_operations
        e_ordering_order_line.confirmed_date = i_plan_confirm_date
        e_ordering_order_line.plant = i_plan_plant
        e_ordering_order_lines.append(e_ordering_order_line)

    if len(e_ordering_order_lines):
        OrderLines.objects.bulk_update(
            e_ordering_order_lines,
            fields=[
                "confirmed_date",
                "i_plan_on_hand_stock",
                "i_plan_operations",
                "iplan",
            ],
        )

    if len(e_ordering_order_lines_i_plan):
        OrderLineIPlan.objects.bulk_update(
            e_ordering_order_lines_i_plan,
            fields=[
                "atp_ctp",
            ],
        )


def save_domestic_order(order_data, user, response=None):
    """
    Save domestic order when upload PO with status as draft
    @param order_data:
    @param user:
    @return: order
    """
    logging.info("[PO Upload] save_domestic_order: start ")
    sold_to = SoldToMaster.objects.filter(
        sold_to_code=order_data.get("sold_to_code")
    ).first()

    list_po_codes = []
    for order_line in order_data.get("items"):
        list_po_codes.append(order_line.get("sku_code"))
    contract = po_upload_sync_contract(
        order_data.get("contract_number"), sold_to, list_po_codes, True, response
    )
    # fetch_and_validate_product_group(order_data, order_data.get("sold_to_code"), False)
    incoterm_1_code = order_data.get("incoterm1", "")
    incoterm_1 = master_models.Incoterms1Master.objects.filter(
        code=incoterm_1_code
    ).first()

    sales_organization = None
    distribution_channel = None
    division = None
    sales_group = None
    sales_office = None
    company = None
    if contract:
        sales_organization = contract.sales_organization
        distribution_channel = contract.distribution_channel
        division = contract.division
        sales_group = contract.sales_group
        sales_office = contract.sales_office
        company = contract.company

    order = Order.objects.create(
        status=ScgOrderStatus.DRAFT.value,
        po_number=order_data.get("po_number"),
        ship_to=get_ship_to_code_name(
            order_data.get("sold_to_code"), order_data.get("ship_to_code")
        ),
        bill_to=order_data.get("bill_to_code"),
        sold_to_id=sold_to.id,
        type=OrderType.DOMESTIC.value,
        remark=order_data.get("remark1"),
        web_user_name=get_web_user_name(order_type=OrderType.PO, user=user),
        created_by=user,
        contract=contract,
        sales_organization=sales_organization,
        distribution_channel=distribution_channel,
        division=division,
        sales_group=sales_group,
        sales_office=sales_office,
        company=company,
        payment_term=contract.payment_term,
        payer=order_data.get("payer_code", ""),
        incoterms_1=incoterm_1,
        incoterms_2=order_data.get("incoterm2", ""),
        internal_comments_to_logistic=order_data.get("remark1", ""),
        product_information=order_data.get("remark2", ""),
    )

    is_special_contract = is_order_contract_project_name_special(order)

    order_lines, order_request_date, total_price = save_order_line(
        is_special_contract, order, order_data
    )

    order.request_date = order_request_date
    order.total_price = total_price
    order.save()
    return order, order_lines


def save_order_line(is_special_contract, order, order_data):
    order_lines_info = order_data.get("items")
    order_lines = []
    total_price = 0
    order_request_date = None
    for order_line in order_lines_info:
        if not order_line.get("error_messages"):
            sku_code = order_line.get("sku_code")
            material_variant = (
                MaterialVariantMaster.objects.filter(
                    code=sku_code, material__isnull=False
                )
                .order_by("-id")
                .first()
            )
            material = None
            if material_variant:
                material = material_variant.material

            quantity = order_line.get("order_quantity", 0)

            i_plans = OrderLineIPlan.objects.create(
                attention_type=None,
                atp_ctp=None,
                atp_ctp_detail=None,
                block=None,
                run=None,
                iplant_confirm_quantity=None,
                item_status=None,
                original_date=None,
                inquiry_method_code=None,
                transportation_method=None,
                type_of_delivery=None,
                fix_source_assignment=None,
                split_order_item=None,
                partial_delivery=None,
                consignment=None,
                paper_machine=None,
            )

            if material:
                line = prepare_order_line_with_material(
                    i_plans,
                    is_special_contract,
                    material,
                    material_variant,
                    order,
                    order_line,
                    quantity,
                    sku_code,
                )
            else:
                line = prepare_order_line_without_material(
                    i_plans, is_special_contract, order, order_line, quantity, sku_code
                )
            order_lines.append(line)
            if not order_request_date:
                order_request_date = order_line.get("delivery_date")
    OrderLines.objects.bulk_create(order_lines)
    return order_lines, order_request_date, total_price


def prepare_order_line_without_material(
    i_plans, is_special_contract, order, order_line, quantity, sku_code
):
    line = OrderLines(
        order=order,
        item_no=order_line.get("po_item_no"),
        po_item_no=order_line.get("po_item_no"),
        po_no=order_line.get("po_number"),
        material=None,
        material_variant=None,
        quantity=quantity,
        request_date=order_line.get("delivery_date"),
        sales_unit=order_line.get("order_unit"),
        remark="C1" if is_special_contract else "",
        shipping_mark=order_line.get("remark"),
        iplan=i_plans,
        ship_to=order_line.get("ship_to", ""),
        type=OrderType.DOMESTIC.value,
        weight=None,
        weight_unit=None,
        total_weight=None,
        inquiry_method=InquiryMethodType.DOMESTIC.value,
        original_request_date=order_line.get("delivery_date"),
        material_code=sku_code,
    )
    return line


def prepare_order_line_with_material(
    i_plans,
    is_special_contract,
    material,
    material_variant,
    order,
    order_line,
    quantity,
    sku_code,
):
    line = OrderLines(
        order=order,
        item_no=order_line.get("po_item_no"),
        po_item_no=order_line.get("po_item_no"),
        po_no=order_line.get("po_number"),
        material=material,
        material_variant=material_variant,
        quantity=quantity,
        request_date=order_line.get("delivery_date"),
        sales_unit=order_line.get("order_unit") or material_variant.sales_unit,
        remark="C1" if is_special_contract else "",
        shipping_mark=order_line.get("remark"),
        iplan=i_plans,
        ship_to=order_line.get("ship_to", ""),
        type=OrderType.DOMESTIC.value,
        weight=material.gross_weight,
        weight_unit=material.weight_unit,
        total_weight=material.gross_weight * quantity
        if material.gross_weight
        else None,
        inquiry_method=InquiryMethodType.DOMESTIC.value,
        original_request_date=order_line.get("delivery_date"),
        material_code=sku_code,
    )
    return line


def send_email_after_create_sap_order(
    manager,
    user,
    order,
    file_log,
    save_time,
    order_partners=None,
    errors=None,
    errors_code=None,
    is_being_process=False,
    is_error_item=False,
    is_error_item_all=False,
    error_message_object=None,
    order_status=None,
    order_data=None,
    is_sap_or_iplan_failed=False,
):
    """
    send mail after request SAP successfully
    @param manager:
    @param user: object user
    @param order: object order
    @param file_log: object file
    @param save_time:
    @param errors: List error
    @return:
    """
    if save_time is None:
        save_time = convert_date_time_timezone_asia(timezone.now())
    start_time = convert_date_time_to_timezone_asia(file_log.created_at)
    sold_to_code = order.sold_to.sold_to_code
    order_number = order.so_no or ""
    logging.info(
        "[PO Upload] send_email_after_create_sap_order: start for SO NO: {order_number}"
    )
    if order.ship_to:
        _, ship_to_name_address = order.ship_to.split("-", 1)
    else:
        ship_to_name_address = ""
    place_of_delivery = f"{ship_to_name_address or ''}"
    payment_terms = (
        PAYMENT_TERM_MAPPING.get(order.contract.payment_term_key, "")
        if order.contract
        else ""
    )
    product_group = order.product_group if order.product_group else ""
    sale_org = order.sales_organization.code if order.sales_organization else ""
    logging.info(
        "[PO Upload] send_email_after_create_sap_order: SO NO: {order_number}, "
        "product group:{product_group}, sale_org:{sale_org}"
    )
    is_po_upload_order_error = False

    order_item_message = error_message_object.get("order_item_message")
    i_plan_request_error_message = error_message_object.get(
        "i_plan_request_error_message"
    )
    i_plan_confirm_error_message = error_message_object.get(
        "i_plan_confirm_error_message"
    )
    order_header_message = error_message_object.get("order_header_message")
    is_i_plan_error_item_all = error_message_object.get("is_i_plan_error_item_all")
    if order_header_message or is_error_item_all or is_i_plan_error_item_all:
        is_po_upload_order_error = True
    # if (errors and not is_error_item) or
    if (
        is_being_process
        or ResponseCodeES17.BLACKLIST_CUSTOMER.get("code") in errors_code
        or is_error_item_all
    ):
        is_po_upload_order_error = True

    template_data = {
        "order_number": order_number,
        "customer_po_number": order.po_number,
        "file_name": file_log.file_name,
        "record_date": f"{start_time} ถึง {save_time}",
        "customer_name": get_sold_to_no_name(sold_to_code, return_only_name=True),
        "place_of_delivery": place_of_delivery,
        "payment_terms": payment_terms or "",
        "shipping": "ส่งให้",
        "contract_number": get_contract_no_name_from_order(order)
        if order.contract
        else "",
        "note": order.internal_comments_to_logistic or "",
        "error_messages": list(set(errors)) if errors else [],
        "alt_mat_errors": get_alternated_material_errors(order),
    }
    order_lines = list(OrderLines.objects.filter(order=order).all())
    order_lines.sort(key=lambda line: int(line.item_no))
    data = []
    material_code = ""
    order_line_from_file = None
    if is_sap_or_iplan_failed is False:
        for order_line in order_lines:
            for line in order_status["order_data_from_file"]["items"]:
                if line["po_item_no"] == order_line.item_no:
                    order_line_from_file = line
                    break
            item_level_message = get_item_level_message(
                order_item_message,
                i_plan_request_error_message,
                i_plan_confirm_error_message,
                order_line,
            )
            variant = order_line.material_variant
            if variant:
                material_description = variant.description_en
                material_code = variant.code
            else:
                material_description = order_line_from_file.get("sku_code", "")
            material = order_line.material
            if material:
                material_code = material.material_code
            qty = int(order_line.quantity)
            qty_ton = format_sap_decimal_values_for_pdf(order_line.net_weight_ton)
            if item_level_message and not (int(order_line.quantity)):
                for item in order_data["items"]:
                    if order_line.item_no == item["po_item_no"]:
                        qty = item["order_quantity"]
                        # removed the qty_ton calculation based on ticket SEO-6876
            data.append(
                {
                    "item_no": order_line.item_no,
                    "material_description": get_alternated_material_related_data(
                        order_line, material_description
                    ),
                    "qty": qty,
                    "sales_unit": order_line.sales_unit,
                    "qty_ton": qty_ton,
                    "request_delivery_date": order_line.original_request_date.strftime(
                        "%d.%m.%Y"
                    )
                    if order_line.original_request_date
                    else "",
                    "iplan_confirm_date": order_line.request_date.strftime("%d.%m.%Y")
                    if order_line.request_date
                    else "",
                    "message": item_level_message,
                    "material_code": material_code,
                }
            )

    # remove iplan_confirm_date SEO-5470
    for item in data:
        if item["message"] != "" or order_header_message or is_po_upload_order_error:
            item["iplan_confirm_date"] = ""

    if error_message_object["order_item_invalid_material"]:
        data += [
            {
                "item_no": line["po_item_no"],
                "material_description": line["sku_code"],
                "qty": line["order_quantity"],
                "sales_unit": line["order_unit"],
                "qty_ton": "",
                "request_delivery_date": str(
                    line.get("delivery_date").strftime("%d.%m.%Y")
                ),
                "iplan_confirm_date": "",
                "message": "".join(line.get("error_messages")),
                "material_code": line["sku_code"],
            }
            for line in error_message_object["order_item_invalid_material"]
        ]
    if order_header_message:
        data = sorted(data, key=lambda item: int(item["item_no"]))
    else:
        data = _sorted_item_data(data)
    sales_unit, total_qty, total_qty_ton = get_summary_details_from_data(data)
    ship_to = order.ship_to and order.ship_to.split("\n")
    file_name_pdf = f"{order.so_no}{sold_to_code}"
    template_pdf_data = {
        "po_no": order.po_number,
        "sale_org_name": get_sale_org_name_from_order(order),
        "so_no": order_number,
        "file_name": file_log.file_name,
        "date_time": save_time,
        "sold_to_no_name": get_sold_to_no_name(sold_to_code),
        "sold_to_address": _get_sold_to_address(sold_to_code),
        "ship_to_no_name": ship_to and ship_to[0] or "",
        "ship_to_address": ship_to[1] if ship_to and len(ship_to) == 2 else "",
        "payment_method_name": get_payment_method_name_from_order(order),
        "contract_no_name": get_contract_no_name_from_order(order)
        if order.contract
        else "",
        "remark_order_info": order.internal_comments_to_logistic or "",
        "created_by": f"{user.first_name} {user.last_name}",
        "errors": errors or [],
        "data": data,
        "total_qty": total_qty,
        "total_qty_ton": total_qty_ton,
        "sales_unit": sales_unit,
        "file_name_pdf": file_name_pdf,
        "is_po_upload_order_error": is_po_upload_order_error,
        "print_date_time": get_date_time_now_timezone_asia(),
        "message": "\n".join(order_header_message)
        if len(order_header_message) > 0
        else "",
    }
    pdf = html_to_pdf(
        template_pdf_data,
        "po_upload_header.html",
        "po_upload_content.html",
    )

    subject = f'{get_stands_for_company(order)} Order upload "{file_log.file_name}"_{get_sold_to_no_name(sold_to_code, True)}'
    if not order_number or is_error_item or errors:
        subject = f'{"item " if is_error_item else ""}ERROR_{get_stands_for_company(order)} Order upload "{file_log.file_name}"_{get_sold_to_no_name(sold_to_code, True)}'
        if is_po_upload_order_error:
            subject = f'ERROR_{get_stands_for_company(order)} Order upload FAILED "{file_log.file_name}"_{get_sold_to_no_name(sold_to_code, True)}'

    logging.info(
        "[PO Upload] send_email_after_create_sap_order: email from config will be retrieved"
        " for SO NO:{order_number} with product group:{product_group}, sale_org:{sale_org}"
    )
    sale_orgs = []
    if sale_org:
        if sale_org[0] == "0":
            sale_orgs.append(sale_org.lstrip("0"))
        sale_orgs.append(sale_org)

    mail_to = []
    internal_emails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.PO_UPLOAD, sale_orgs, product_group.split(",")
    )
    external_email_to_list, external_cc_to_list = get_external_emails_by_config(
        EmailConfigurationFeatureChoices.PO_UPLOAD,
        sold_to_code,
        product_group.split(","),
    )

    bu_and_team_of_email = EmailConfigurationInternal.objects.filter(
        po_upload=True
    ).values("bu", "team")

    for pair_bu_and_team in bu_and_team_of_email:
        if "Sales" in pair_bu_and_team["team"]:
            sales_employee_email = get_sales_employee_email(
                sold_to_code, order_partners
            )
            if sales_employee_email:
                mail_to.append(sales_employee_email)

    # add User who performed the PO Upload
    external_email_to_list.append(user.email)
    if external_email_to_list:
        external_email_to_list = list(set(external_email_to_list))
    mail_to.extend(external_email_to_list)
    cc_to = internal_emails + external_cc_to_list
    if not mail_to:
        mail_to = cc_to
        cc_to = []
    manager.scgp_po_upload_send_mail(
        "scg.email",
        mail_to,
        template_data,
        subject,
        "index.html",
        pdf,
        None,
        cc_to,
    )
    logging.info("[PO Upload] send_email_after_create_sap_order: finish ")


def check_acknowledge(i_plan_acknowledge, dict_order_lines):
    """
    Check acknowledge iPlan success or not
    If not, update flag R5 for order line
    @param i_plan_acknowledge:
    @param dict_order_lines:
    @return:
    """
    i_plan_acknowledge_headers = i_plan_acknowledge.get("DDQAcknowledge").get(
        "DDQAcknowledgeHeader"
    )
    if len(i_plan_acknowledge_headers):
        # Check commit i-plan success or not to update order status
        i_plan_acknowledge_header = i_plan_acknowledge_headers[0]
        i_plan_acknowledge_line = i_plan_acknowledge_header.get("DDQAcknowledgeLine")
        commit_failed_items = []
        for acknowledge_line in i_plan_acknowledge_line:
            if (
                acknowledge_line.get("returnStatus") or ""
            ).lower() != IPlanAcknowledge.SUCCESS.value.lower():
                line_number = acknowledge_line.get("lineNumber")
                if commit_failed_item := dict_order_lines.get(line_number):
                    commit_failed_items.append(commit_failed_item)

        # if commit i-plan failure => order is flagged R5
        if len(commit_failed_items):
            update_attention_type_r5(commit_failed_items)


def update_order_line_with_sap_data(sap_response, dict_order_lines):
    """
    Update data order line with data response from SAP
    @param sap_response:
    @param dict_order_lines:
    @return:
    """
    updated_line = []
    for sap_order_item in sap_response.get("orderItemsOut", []):
        item_no = str(sap_order_item.get("itemNo")).lstrip("0")
        order_line_obj = dict_order_lines.get(item_no)
        if order_line_obj:
            # Update the request date and confirmed date
            compute_confirm_and_request_date(order_line_obj)
            order_line_obj.weight_unit_ton = sap_order_item.get("weightUnitTon", "")
            order_line_obj.weight_unit = sap_order_item.get("weightUnit", "")
            order_line_obj.net_weight_ton = sap_order_item.get("netWeightTon")
            order_line_obj.gross_weight_ton = sap_order_item.get("grossWeightTon")
            updated_line.append(order_line_obj)
            dict_order_lines[item_no] = order_line_obj
        if not order_line_obj:
            updated_line.net_price = sap_order_item.get("netValue", 0)
            updated_line.price_currency = sap_order_item.get("currency")

    OrderLines.objects.bulk_update(
        updated_line,
        [
            "net_price",
            "price_currency",
            "request_date",
            "confirmed_date",
            "weight_unit_ton",
            "weight_unit",
            "net_weight_ton",
            "gross_weight_ton",
        ],
    )


"""
1. NOTE: PO Upload doesn't have special plant & container line items hence no need to check
2. For normal line items, based on IPlan status calculate mock confirm date if required else request date should be updated with disaptch date
"""


def compute_confirm_and_request_date(order_line):
    order_line_obj_i_plan = order_line.iplan
    dispatch_date = (
        order_line_obj_i_plan.iplant_confirm_date
        if order_line_obj_i_plan and order_line_obj_i_plan.iplant_confirm_date
        else None
    )
    if not dispatch_date:
        dispatch_date = mock_confirm_date(
            order_line.request_date, order_line_obj_i_plan.item_status
        )
    order_line.confirmed_date = dispatch_date
    order_line.request_date = order_line.confirmed_date


def po_upload_sync_contract(contract_no, sold_to, list_po_codes, commit, response):
    """
    Sync contract, input material in po files
    @param response:
    @param commit:
    @param contract_no:
    @param sold_to: sold to object
    @param list_po_codes:
    @return:
    """
    logging.info("[PO Upload] po_upload_sync_contract: start ")
    currency = ""

    response_data = response.get("data", [])
    if len(response_data) == 0:
        raise ValidationError(
            {"contract_no": contract_no, "error": "No data found in ES-14 response"}
        )
    response_data = response_data[0]
    contract = Contract.objects.filter(code=contract_no).first()

    if not contract:
        contract = Contract.objects.create(code=contract_no)

    if not contract.sold_to:
        contract.sold_to = sold_to

    condition_list = response_data.get("conditionList", [])
    for item in condition_list:
        if item.get("currency"):
            currency = item.get("currency")
            break
    list_items = response_data.get("contractItem", [])
    list_items_mat_group = ", ".join(set([item["matGroup1"] for item in list_items]))
    contact_persons = prepare_contact_person_using_sap14_response(response_data)

    order_text_list = response_data.get("orderText", [])
    order_text_list_data = get_data_from_order_text_list(order_text_list)

    contract_sale_detail = {
        "distribution_channel": response_data.get("distributionChannel", "10"),
        "division": response_data.get("division", "00"),
        "sale_org": response_data.get("saleOrg", "0750"),
        "sale_office": response_data.get("saleOffice", "0750"),
        "sale_group": response_data.get("saleGroup", "0750"),
        "bill_to": response_data.get("billTo", "0000000181"),
        "customer_no": response_data.get("customerNo", "0000000181"),
        "ship_to": response_data.get("shipTo"),
        "ship_to_name": response_data.get("shipToName"),
        "unloading_point": response_data.get("unloadingPoint"),
        "payer": response_data.get("payer"),
        "contact_person": contact_persons,
        "sales_employee": response_data.get("salesEmployee"),
        "author": response_data.get("author"),
        "end_customer": response_data.get("endCustomer"),
        "po_no": response_data.get("poNo"),
        "currency": currency,
        "incoterms_2": response_data.get("incoterms2"),
        "payment_term_key": response_data.get("pymTermKey"),
        "payment_term": response_data.get("pymTermDes"),
        "project_name": response_data.get("projectName"),
        "prc_group1": list_items_mat_group,
    }
    contract_sale_detail = {**contract_sale_detail, **order_text_list_data}
    sync_contract_sale_detail(contract, contract_sale_detail, commit)
    list_condition = response_data.get("conditionList", [])
    contract_item_objects = reduce(
        lambda previous, current: {**previous, current.get("itemNo"): current},
        list_items,
        {},
    )

    set_contract_item_fields(contract_item_objects, list_condition)

    kwargs = {"is_po_upload_flow": True, "list_po_codes": list_po_codes}
    list_contract_material = map_sap_contract_item(
        contract, contract_item_objects, order_text_list, **kwargs
    )

    dict_materials = {}
    for contract_material in list_contract_material:
        dict_materials[
            contract_material.material.material_code
        ] = contract_material.material

    response_es15 = get_all_variant_of_contract(contract, dict_materials.keys())
    if response_es15.get("status", "") == "success" and len(
        response_es15.get("data", [])
    ):
        data = response_es15.get("data", [])[0]
        products = data.get("productList")
        for product_data in products:
            product_code = product_data.get("productCode", "")
            material_object = dict_materials.get(product_code)

            materials_standard = classify_material(
                product_data, "Standard", list_po_codes
            )
            materials_non_standard = classify_material(
                product_data, "Non-Standard", list_po_codes
            )

            sap_mapping_contract_material_variant(
                material_object.id, materials_standard, "Standard"
            )
            sap_mapping_contract_material_variant(
                material_object.id, materials_non_standard, "Non-Standard"
            )

    return contract


def set_contract_item_fields(contract_item_objects, list_condition):
    extracted_condition_type = ["ZN00", "ZPR2"]
    for item_no in contract_item_objects.keys():
        item_conditions = list(
            filter(
                lambda item: item.get("conditionType") in extracted_condition_type
                and item.get("itemNo") == item_no,
                list_condition,
            )
        )
        commission_zcm1 = list(
            filter(
                lambda item: item.get("conditionType") == "ZCM1"
                and item.get("itemNo") == item_no,
                list_condition,
            )
        )
        commission_zcm3 = list(
            filter(
                lambda item: item.get("conditionType") == "ZCM3"
                and item.get("itemNo") == item_no,
                list_condition,
            )
        )
        contract_item_objects.get(item_no)["conditions"] = item_conditions
        contract_item_objects.get(item_no)["commission_zcm1"] = commission_zcm1
        contract_item_objects.get(item_no)["commission_zcm3"] = commission_zcm3


def prepare_contact_person_using_sap14_response(response_data):
    contact_person_list = response_data.get("contactPerson", [])
    contact_persons = None
    if contact_person_list:
        contact_persons = ", ".join(
            [
                f"{contact_person.get('contactPersonNo')} - {contact_person.get('contactPersonName')}"
                for contact_person in contact_person_list
                if contact_person
            ]
        )
    return contact_persons


def classify_material(product_data, mat_type, list_po_codes):
    """
    Return list standard and non-standard material
    @param product_data:
    @param mat_type:
    @param list_po_codes:
    @return:
    """
    material = []
    list_variant = product_data.get("matNonStandard", [])
    if mat_type == "Standard":
        list_variant = product_data.get("matStandard", [])
    for variant in list_variant:
        if variant.get("matCode", "") in list_po_codes:
            material.append({**{"variantType": mat_type}, **variant})

    return material


def get_all_variant_of_contract(contract, list_material_codes):
    products = []
    for material_code in list_material_codes:
        products.append({"productCode": material_code})

    param = {
        "piMessageId": str(uuid.uuid1().int),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "customerNo": contract.sold_to.sold_to_code,
        "product": products,
    }

    try:
        log_val = {
            "contract_no": contract.code,
        }
        response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.SAP.value, **log_val
        ).request_mulesoft_post("sales/materials/search", param)
    except Exception as e:
        logging.exception(
            "[PO Upload] Exception during ES15 call for contract variant "
            + str(contract.code)
            + ":"
            + str(e)
        )
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)
    return response


def sync_contract_sale_detail(
    contract: migration_models.Contract, params: dict, commit: bool
):
    distribution_channel = migration_models.DistributionChannelMaster.objects.filter(
        code=params.get("distribution_channel")
    ).first()
    division = migration_models.DivisionMaster.objects.filter(
        code=params.get("division")
    ).first()
    sale_group = migration_models.SalesGroupMaster.objects.filter(
        code=params.get("sale_group")
    ).first()
    sale_office = migration_models.SalesOfficeMaster.objects.filter(
        code=params.get("sale_office")
    ).first()
    sales_organization = migration_models.SalesOrganizationMaster.objects.filter(
        code=params.get("sale_org")
    ).first()

    "In case we don't have any unloading point from ES-14, get the first row from database, probably..."
    if params.get("unloading_point") is None:
        unloading_point_obj = master_models.SoldToUnloadingPointMaster.objects.filter(
            sold_to_code=params.get("customer_no")
        ).first()
        unloading_point = (
            unloading_point_obj.unloading_point
            if unloading_point_obj is not None
            else None
        )
    else:
        unloading_point = params.get("unloading_point")

    bill_to_obj = master_models.SoldToPartnerAddressMaster.objects.filter(
        sold_to_code=params.get("customer_no"), partner_code=params.get("bill_to")
    ).first()
    if bill_to_obj:
        bill_to_format = f"{params.get('bill_to')} - {bill_to_obj.name1}"
    else:
        # Mock up data in case there aren't any bill to found
        bill_to_format = f'{params.get("ship_to", "TEST SAP")} - {params.get("ship_to_name", "TEST SAP")}'

    contract.distribution_channel = distribution_channel
    contract.division = division
    contract.sales_group = sale_group
    contract.sales_organization = sales_organization
    contract.sales_office = sale_office
    contract.bill_to = bill_to_format
    contract.prc_group1 = params.get("prc_group1")

    update_attr = [
        "po_no",
        "payer",
        "contact_person",
        "sales_employee",
        "author",
        "end_customer",
        "currency",
        "port_of_loading",
        "shipping_mark",
        "uom",
        "port_of_discharge",
        "no_of_containers",
        "gw_uom",
        "payment_instruction",
        "production_information",
        "payment_term_key",
        "payment_term",
        "project_name",
        "internal_comments_to_warehouse",
        "remark",
        "incoterms_2",
        "web_user_line_lang" "port_of_loading_lang",
        "shipping_mark_lang",
        "uom_lang",
        "port_of_discharge_lang",
        "no_of_containers_lang",
        "gw_uom_lang",
        "payment_instruction_lang",
        "remark_lang",
        "production_information_lang",
        "internal_comments_to_warehouse_lang",
        "etd_lang",
        "eta_lang",
        "surname_lang",
        "external_comments_to_customer_lang",
        "internal_comments_to_logistic_lang",
        "web_user_line_lang",
    ]

    for attr in update_attr:
        setattr(contract, attr, params.get(attr, ""))

    if unloading_point:
        contract.unloading_point = unloading_point
    if commit:
        contract.save()


def get_ship_to_code_name(sold_to_code, ship_to_code):
    partner_role = "WE"
    ship_to_name = ""
    ship_to_address = ""
    sold_to_channel_partners = master_models.SoldToChannelPartnerMaster.objects.filter(
        sold_to_code=sold_to_code, partner_code=ship_to_code, partner_role=partner_role
    )
    if sold_to_channel_partners:
        for sold_to_channel_partner in sold_to_channel_partners:
            address_link = sold_to_channel_partner.address_link
            partner_code = sold_to_channel_partner.partner_code
            sold_to_partner_address = (
                master_models.SoldToPartnerAddressMaster.objects.filter(
                    sold_to_code=sold_to_code,
                    address_code=address_link,
                    partner_code=partner_code,
                    name1__isnull=False,
                ).last()
            )
            if not sold_to_partner_address:
                continue

            ship_to_address = (
                f"{sold_to_partner_address.street} {sold_to_partner_address.district} "
                f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"
            )
            ship_to_name = f"{sold_to_partner_address.name1}"
            break
    return f"{ship_to_code} - {ship_to_name or ''}\n{ship_to_address or ''}"


def request_create_order_sap(order, manager, success_order_items, po_upload_mode=""):
    """
    Call SAP create order for only po_upload
    :params order: e-ordering order
    :params manager: plugin manager
    :params po_upload_mode: A for Customer Role, B for CS Role, '' for normal case
    :return: SAP response
    """
    order_lines = (
        OrderLines.objects.annotate(
            item_no_int=Cast("item_no", output_field=IntegerField())
        )
        .filter(order=order, item_no__in=success_order_items)
        .order_by("item_no_int")
    )
    sold_to_code = order.contract.sold_to.sold_to_code
    contract = order.contract

    text_id_lang_obj = get_text_id_lang_obj_from_text_master_by_sold_to_code(
        sold_to_code
    )

    internal_comments_to_warehouse = (
        order.internal_comments_to_warehouse
        or order.internal_comment_to_warehouse
        or ""
    )
    internal_comments_to_logistic = order.internal_comments_to_logistic or ""
    external_comments_to_customer = order.external_comments_to_customer or ""
    product_information = (
        order.product_information or order.production_information or ""
    )
    # remark = order.remark or ""
    payment_instruction = order.payment_instruction or ""
    contract = order.contract
    internal_comments_to_warehouse_lang = (
        contract.internal_comments_to_warehouse_lang or ""
    )
    internal_comments_to_logistic_lang = (
        contract.internal_comments_to_logistic_lang or ""
    )
    external_comments_to_customer_lang = (
        contract.external_comments_to_customer_lang or ""
    )
    web_user_line_lang = contract.web_user_line_lang or ""
    production_information_lang = contract.production_information_lang or ""
    payment_instruction_lang = contract.payment_instruction_lang or ""
    sales_organization = contract and contract.sales_organization or None
    sales_organization_code = sales_organization and sales_organization.code or None
    if order.sales_organization:
        sales_organization_code = order.sales_organization.code

    order_partners = get_order_partner(order, order_lines)

    request_items = []
    request_schedules = []
    request_texts = []
    web_user_name = []
    item_no = "000000"

    if order.web_user_name:
        web_user_name = order.web_user_name.split("\n")

    if len(web_user_name) == 2:
        _, *_names = web_user_name[1].split(" ")
        uname = " ".join(_names)
        web_user_name_z095 = {
            "itemNo": item_no,
            "textId": TextID.SYSTEM_SOURCE.value,
        }
        if TextID.SYSTEM_SOURCE.value in text_id_lang_obj:
            web_user_name_z095["language"] = text_id_lang_obj[
                TextID.SYSTEM_SOURCE.value
            ]["language"]

        web_user_name_z095["textLines"] = ([{"textLine": web_user_name[0]}],)
        request_texts.append(web_user_name_z095)

        web_user_name_zk01 = {
            "itemNo": item_no,
            "textId": TextID.WEB_USERNAME.value,
        }
        if web_user_line_lang:
            web_user_name_zk01["language"] = web_user_line_lang
        elif TextID.WEB_USERNAME.value in text_id_lang_obj:
            web_user_name_zk01["language"] = text_id_lang_obj[
                TextID.WEB_USERNAME.value
            ]["language"]

        web_user_name_zk01["textLines"] = ([{"textLine": uname}],)
        request_texts.append(web_user_name_zk01)

    if internal_comments_to_warehouse:
        text_ids = TextID.HEADER_ICTW.value
        # Get language from es14 or text_id_lang_obj(soldtotextmaster)
        language = internal_comments_to_warehouse_lang or text_id_lang_obj.get(
            text_ids, {}
        ).get("language")

        handle_request_text_to_es17(
            request_texts,
            internal_comments_to_warehouse,
            item_no,
            text_ids,
            lang=language,
        )

    text_ids = TextID.HEADER_ICTL.value
    # Get language from es14 or text_id_lang_obj(soldtotextmaster)
    language = internal_comments_to_logistic_lang or text_id_lang_obj.get(
        text_ids, {}
    ).get("language")
    handle_request_text_to_es17(
        request_texts,
        internal_comments_to_logistic,
        item_no,
        text_ids,
        lang=language,
    )

    if external_comments_to_customer:
        text_ids = TextID.HEADER_ECTC.value
        # Get language from es14 or text_id_lang_obj(soldtotextmaster)
        language = external_comments_to_customer_lang or text_id_lang_obj.get(
            text_ids, {}
        ).get("language")
        handle_request_text_to_es17(
            request_texts,
            external_comments_to_customer,
            item_no,
            text_ids,
            lang=language,
        )

    text_ids = TextID.HEADER_PI.value
    # Get language from es14 or text_id_lang_obj(soldtotextmaster)
    language = production_information_lang or text_id_lang_obj.get(text_ids, {}).get(
        "language"
    )
    handle_request_text_to_es17(
        request_texts,
        product_information,
        item_no,
        text_ids,
        lang=language,
    )

    # if remark:
    #     text_ids = TextID.HEADER_REMARK.value
    #     handle_request_text_to_es17(request_texts, remark, item_no, text_ids)

    if payment_instruction:
        text_ids = TextID.HEADER_PAYIN.value
        # Get language from es14 or text_id_lang_obj(soldtotextmaster)
        language = payment_instruction_lang or text_id_lang_obj.get(text_ids, {}).get(
            "language"
        )
        handle_request_text_to_es17(
            request_texts, payment_instruction, item_no, text_ids, lang=language
        )

    request_items_container = []
    request_schedules_container = []
    request_texts_container = []
    item_running_no = 10
    for line in order_lines:
        if line.item_no is not None:
            line.item_no = str(line.item_no).zfill(6)
        if line.item_cat_eo == ItemCat.ZKC0.value:
            (
                request_items_container,
                request_schedules_container,
                request_texts_container,
            ) = handle_lines_to_request_es17(
                line,
                order,
                request_items_container,
                request_schedules_container,
                request_texts_container,
                item_running_no,
                text_id_lang_obj,
                internal_comments_to_warehouse_lang,
                internal_comments_to_logistic_lang,
            )
        else:
            (
                request_items,
                request_schedules,
                request_texts,
            ) = handle_lines_to_request_es17(
                line,
                order,
                request_items,
                request_schedules,
                request_texts,
                item_running_no,
                text_id_lang_obj,
                internal_comments_to_warehouse_lang,
                internal_comments_to_logistic_lang,
            )

        # if line.shipping_mark:
        text_ids = TextID.ITEM_REMARK_PO_UPLOAD.value
        # Get language from text_id_lang_obj(soldtotextmaster)
        language = text_id_lang_obj.get(text_ids, {}).get("language")
        handle_request_text_to_es17(
            request_texts,
            line.shipping_mark,
            line.item_no,
            text_ids,
            lang=language,
        )
        if line.remark and order.type == OrderType.EXPORT.value:
            handle_request_text_to_es17(
                request_texts,
                line.remark,
                line.item_no,
                TextID.ITEM_REMARK.value,
                lang=language,
            )

        item_running_no += 10

    request_items += request_items_container
    request_schedules += request_schedules_container
    request_texts += request_texts_container

    request_id = str(uuid.uuid1().int)
    req_date = order.request_date or order.request_delivery_date or None
    if isinstance(req_date, str):
        req_date = datetime.strptime(req_date, "%Y-%m-%d")

    contract_code = order.contract.code if order.contract else ""

    params = {
        "piMessageId": request_id,
        "testrun": False,
        "poUploadMode": po_upload_mode,
        "savePartialItem": bool(po_upload_mode),
        "orderHeader": {
            "docType": DocType.ZBV.value
            if contract.payment_term_key == PaymentTerm.DEFAULT.value
            else DocType.ZOR.value,
            "salesOrg": sales_organization_code,
            "distributionChannel": order.distribution_channel
            and order.distribution_channel.code
            or "",
            "division": order.division and order.division.code or "",
            "salesGroup": order.sales_group.code or "",
            "reqDate": req_date and req_date.strftime("%d/%m/%Y") or "",
            "incoterms1": order.incoterms_1 and order.incoterms_1.code or "",
            "incoterms2": order.incoterms_2,
            "paymentTerm": contract.payment_term_key,
            "poNo": get_po_number_from_order(order),
            "contactNo": contract_code,
        },
        "orderPartners": order_partners,
        "orderItemsIn": request_items,
        "orderSchedulesIn": request_schedules,
        "orderTexts": request_texts,
    }
    log_val = {"orderid": order.id}
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value, **log_val
    ).request_mulesoft_post(SapEnpoint.ES_17.value, params, encode=True)
    return response


def handle_lines_to_request_es17(
    line,
    order,
    request_items,
    request_schedules,
    request_texts,
    item_running_no,
    text_id_lang_obj=None,
    internal_comments_to_warehouse_lang="",
    internal_comments_to_logistic_lang="",
):
    sale_unit = ""
    confirm_quantity = 0

    internal_comments_to_warehouse = line.internal_comments_to_warehouse
    external_comments_to_customer = line.external_comments_to_customer

    if line.iplan:

        if line.iplan.on_hand_stock and line.iplan.order_type != AtpCtpStatus.CTP.value:
            confirm_quantity = line.iplan.iplant_confirm_quantity or 0

    item_no = str(line.item_no or line.eo_item_no)
    mat_code = (
        line.material_variant and line.material_variant.code or line.material_code or ""
    )
    if line.item_cat_eo == ItemCat.ZKC0.value:
        confirm_quantity = line.quantity
        sale_unit = line.contract_material.weight_unit if line.contract_material else ""

    order_line_i_plan = line.iplan
    req_date = line.request_date
    dispatch_date = (
        order_line_i_plan.iplant_confirm_date
        if order_line_i_plan and order_line_i_plan.iplant_confirm_date
        else None
    )
    if not dispatch_date:
        dispatch_date_str = mock_confirm_date(req_date, order_line_i_plan.item_status)
        dispatch_date = (
            DateHelper.iso_str_to_obj(dispatch_date_str) if dispatch_date_str else ""
        )
    request_items.append(
        {
            "itemNo": str(item_no).zfill(6),
            "materialNo": mat_code,
            "targetQty": line.quantity,
            "salesUnit": sale_unit or "ROL",
            "plant": line.plant or "",
            "poNo": line.po_no,
            "poDate": line.original_request_date.strftime("%d/%m/%Y")
            if line.original_request_date
            else "",
            "poitemNo": line.po_item_no,
            "refDoc": order.contract.code if order.contract else "",
        }
    )
    request_schedules.append(
        {
            "itemNo": str(item_no).zfill(6),
            "reqDate": dispatch_date.strftime("%d/%m/%Y")
            if dispatch_date and dispatch_date != req_date
            else req_date.strftime("%d/%m/%Y"),
            "reqQty": line.quantity,
            "confirmQty": confirm_quantity,
        }
    )
    if text_id_lang_obj is None:
        text_id_lang_obj = {}
    if internal_comments_to_warehouse:
        text_ids = TextID.ITEM_ICTW.value
        # Get language from es14 or text_id_lang_obj(soldtotextmaster)
        language = internal_comments_to_warehouse_lang or text_id_lang_obj.get(
            text_ids, {}
        ).get("language")
        handle_request_text_to_es17(
            request_texts, internal_comments_to_warehouse, item_no, text_ids, language
        )

    if external_comments_to_customer:
        text_ids = TextID.ITEM_ECTC.value
        # Get language from es14 or text_id_lang_obj(soldtotextmaster)
        # internal_comments_to_logistic_lang is lang from Z002 code from at 'graphql/resolves/contracts.py'
        language = internal_comments_to_logistic_lang or text_id_lang_obj.get(
            text_ids, {}
        ).get("language")
        handle_request_text_to_es17(
            request_texts, external_comments_to_customer, item_no, text_ids, language
        )

    return request_items, request_schedules, request_texts


def handle_request_text_to_es17(request_texts, text_lines, item_no, text_id, lang=""):
    text_line = text_lines.split("\n")
    text_item = {
        "itemNo": item_no,
        "textId": text_id,
    }
    if lang:
        text_item["language"] = lang

    text_item["textLines"] = [{"textLine": item} for item in text_line]
    request_texts.append(text_item)


def get_sales_group_code_by_sold_to_code(sold_to_code):
    sold_to_external = master_models.SoldToExternalSalesGroup.objects.filter(
        sold_to_code=sold_to_code
    ).first()
    if not sold_to_external:
        return ""

    return sold_to_external.sales_group_code


def get_text_id_lang_obj_from_text_master_by_sold_to_code(sold_to_code):
    """
    This function returns an object with text_id as the key and the rest of the data as its value,
    filtered by the sold_to_code.

    :param sold_to_code: sold to code used to filter the data
    :return: an object with text_id as the key
    """
    data = SoldToTextMaster.objects.filter(sold_to_code=sold_to_code).values(
        "language", "text_id"
    )

    # Create the object with text_id as the key and the rest of the data as its value
    text_id_obj = {d["text_id"]: d for d in data}

    return text_id_obj


def get_i_plan_success_order_lines(i_plan_order_lines, success_order_items):
    i_plan_success_order_lines = []
    for order_item in i_plan_order_lines:
        if order_item["lineNumber"] in success_order_items:
            i_plan_success_order_lines.append(order_item)
    return i_plan_success_order_lines


def get_i_plan_fail_order_lines(
    i_plan_order_lines, failed_order_items, order_status_dict, dict_order_lines, order
):
    i_plan_fail_order_lines = []
    for order_item in i_plan_order_lines:
        if order_item["lineNumber"] in failed_order_items:
            i_plan_fail_order_lines.append(order_item)
            mat_description = get_material_variant_description_en_from_order_line(
                dict_order_lines.get(order_item["lineNumber"])
            )
            order_status_dict[order.id]["is_error_item"] = True
            order_status_dict[order.id]["error_messages"].add(
                f'{mat_description} {"Request ATP/ATP failed"}'
            )
    return i_plan_fail_order_lines


def get_error_message_from_sap_response(sap_response, dict_order_lines):
    error_msg_order_header = load_error_message()
    sap_errors = []
    sap_errors_code = []
    is_being_process = False
    is_items_error = False
    order_error_messages = []
    item_error_messages = []
    order_header_msg = []
    if sap_response.get("data"):
        for data in sap_response.get("data"):
            if data.get("type").lower() == SapType.ERROR.value.lower():
                error_message = data.get("message")
                validate_order_msg(data, error_msg_order_header, order_header_msg)
                error_code = data.get("number", "")
                item_no = data.get("itemNo").lstrip("0") if data.get("itemNo") else None
                item_id = data.get("id", "")
                if (
                    item_no
                    and error_code != ResponseCodeES17.BEING_PROCESS["code"]
                    and not re.match("^V\\d+$", item_id)
                ):
                    is_items_error = True
                    order_line = dict_order_lines.get(item_no)
                    mat_description = (
                        get_material_variant_description_en_from_order_line(order_line)
                    )
                    if mat_description:
                        error_message = f'{mat_description} {data.get("message")}'
                    if error_message not in item_error_messages:
                        item_error_messages.append(error_message)
                else:
                    if error_code == ResponseCodeES17.BEING_PROCESS["code"]:
                        error_message = f'{data.get("id", "")}{data.get("number", "")} '
                        error_message += f'เอกสารการขาย {data.get("messageV1", "")} '
                        error_message += f'กำลังประมวลผลอยู่ในขณะนี้ (โดยผู้ใช้ {data.get("messageV2", "")})'
                    else:
                        error_message = f'{data.get("id", "")}{data.get("number", "")} {data.get("message", "")}'
                    if error_message not in order_error_messages:
                        order_error_messages.append(error_message)

                sap_errors_code.append(error_code)
                if (
                    data.get("id", "").lower()
                    == BeingProcessConstants.BEING_PROCESS_CODE_ID.lower()
                    and data.get("number") == BeingProcessConstants.BEING_PROCESS_CODE
                ):
                    is_being_process = True

        sap_errors = order_error_messages + item_error_messages
    order_header_msg = list(set(order_header_msg))
    return (
        is_being_process,
        sap_errors,
        sap_errors_code,
        is_items_error,
        order_header_msg,
    )


def get_sales_employee_email(sold_to_code, order_partners):
    partner_no = None
    sales_email = None
    if order_partners is None:
        order_partners = []
    for order_partner in order_partners:
        if order_partner.get("partnerRole", "") == "VE":
            partner_no = order_partner.get("partnerNo", None)
            break
    if partner_no is not None:
        sales_email = (
            SoldToPartnerAddressMaster.objects.filter(
                sold_to_code=sold_to_code, partner_code=partner_no
            )
            .values_list("email", flat=True)
            .first()
        )
    return sales_email


def get_emailconfig_external(sold_to_code, feature, product_groups):
    mail_to = []
    cc_to = []
    mailto_list = list(
        EmailConfigurationExternal.objects.filter(
            sold_to_code=sold_to_code, feature=feature, product_group__in=product_groups
        ).values("mail_to", "cc_to")
    )
    for mail in mailto_list:
        (mail_to.extend(split_string_to_list(mail["mail_to"], ",")))
        (cc_to.extend(split_string_to_list(mail["cc_to"], ",")))
    return mail_to, cc_to


def split_string_to_list(string, split_with):
    data_list = []
    if string is not None:
        for x in string.split(split_with):
            if len(x.strip()) != 0:
                data_list.append(x.strip())
        return data_list
    else:
        return []


def _sorted_item_data(data):
    item_success = []
    item_failed = []
    for item in data:
        if item.get("message"):
            item_failed.append(item)
        else:
            item_success.append(item)
    item_success.sort(key=lambda line: int(line["item_no"]))
    item_failed.sort(key=lambda line: int(line["item_no"]))
    return item_success + item_failed


def validate_items_material(orders_data):
    sap_material_codes = MaterialVariantMaster.objects.values_list("code", flat=True)
    sold_to_material_masters = SoldToMaterialMaster.objects.values(
        "material_code", "sold_to_material_code", "sold_to_code"
    )
    po_upload_customer_settings = PoUploadCustomerSettings.objects.select_related(
        "sold_to__sold_to_code"
    ).values(
        "sold_to__sold_to_code",
        "use_customer_master",
    )
    return _validate_convert_sap_material_code(
        orders_data,
        po_upload_customer_settings,
        sold_to_material_masters,
        sap_material_codes,
    )


def _is_convert_to_sap(sold_to_code, po_upload_customer_settings):
    for item in po_upload_customer_settings:
        if (
            item["sold_to__sold_to_code"] == sold_to_code
            and item["use_customer_master"]
        ):
            return True
    return False


def _convert_to_sap_material_code(
    sold_to_code, material_code, sold_to_material_masters
):
    for item in sold_to_material_masters:
        if (
            sold_to_code == item["sold_to_code"]
            and material_code == item["sold_to_material_code"]
        ):
            return item["material_code"]
    return material_code


def _validate_convert_sap_material_code(
    orders_data,
    po_upload_customer_settings,
    sold_to_material_masters,
    sap_material_codes,
):
    for order in orders_data:
        sold_to_code = order.get("sold_to_code")
        need_convert_to_sap = _is_convert_to_sap(
            sold_to_code, po_upload_customer_settings
        )
        for item in order.get("items", []):
            sku_code = item.get("sku_code")
            if need_convert_to_sap:
                item["sku_code"] = _convert_to_sap_material_code(
                    sold_to_code, sku_code, sold_to_material_masters
                )

                if item["sku_code"] not in sap_material_codes:
                    item["error_messages"].append("ER01 ไม่พบรหัสสินค้า")
    return orders_data


def format_error_message(error_message):
    return error_message.get("code") + error_message.get("message")


def validate_contract(order_data, manager, file_log, is_being_process, response):
    contract_no = order_data["contract_number"]
    logging.info(f"[PO Upload] validate_contract: start contract no. {contract_no}")
    try:
        error_message_list = []
        error_message = ""
        if response is None:
            error_message = ContractErrorMessage.TECHNICAL_ERROR
        if not error_message:
            if str(response.get("status", "200")) == "500":
                error_message = ContractErrorMessage.TECHNICAL_ERROR
            elif (
                "reason" in response
                and response.get("reason") in ContractErrorMessage.ERROR_CODE_MESSAGE
            ):
                error_message = format_error_message(
                    ContractErrorMessage.ERROR_CODE_MESSAGE.get(response["reason"])
                )
            elif str(response.get("reason")).startswith("Contract end date was on"):
                error_message = format_error_message(
                    ContractErrorMessage.ERROR_CODE_MESSAGE.get(
                        "Contract end date was on"
                    )
                )
            error_message_list.append(error_message)
        if error_message:
            sold_to = SoldToMaster.objects.filter(
                sold_to_code=order_data.get("sold_to_code")
            ).first()
            list_po_codes = [order_data.get("po_number")]
            response_data = (
                response.get("data", [])[0] if response.get("data", []) else None
            )
            contract = po_upload_sync_contract(
                contract_no, sold_to, list_po_codes, False, response
            )
            ship_to = get_ship_to_code_name(
                response_data.get("soldTo"), response_data.get("shipTo")
            )
            order = Order()
            order.sold_to = sold_to
            order.contract = contract
            order.ship_to = ship_to
            order.sales_organization = contract.sales_organization
            order.po_number = order_data.get("po_number")

            error_message_object = {
                "order_header_message": error_message_list,
                "order_item_message": [],
                "i_plan_request_error_message": [],
                "i_plan_confirm_error_message": [],
                "order_item_invalid_material": [],
                "is_i_plan_error_item_all": False,  # is_i_plan_error_item_all,
            }

            send_email_after_create_sap_order(
                manager,
                file_log.uploaded_by,
                order,
                file_log,
                convert_date_time_timezone_asia(timezone.now()),
                order_partners=[],
                errors=[error_message],
                errors_code=[],
                is_being_process=is_being_process,
                is_error_item=False,
                is_error_item_all=True,
                error_message_object=error_message_object,
                order_data=order_data,
            )
            return False

        return True
    except Exception as e:
        logging.info(
            f"[PO Upload] validate_contract: Fail on contract no. {contract_no}"
        )
        logging.exception(e)
        raise e


def send_email_after_po_upload_failure(
    error_message,
    error_message_list,
    file_log,
    is_being_process,
    manager,
    order_data,
):
    sold_to = SoldToMaster.objects.filter(
        sold_to_code=order_data.get("sold_to_code")
    ).first()
    contract = Contract.objects.filter(code=order_data.get("contract_number")).first()

    order = Order()
    order.sold_to = sold_to
    order.ship_to = get_ship_to_code_name(
        order_data.get("sold_to_code"), order_data.get("ship_to_code")
    )
    if not contract:
        order.sales_organization = None
    else:
        order.contract = contract
        order.sales_organization = contract.sales_organization
    order.po_number = order_data.get("po_number")
    order.internal_comments_to_logistic = order_data.get("remark1", "")
    error_message_object = {
        "order_header_message": error_message_list,
        "order_item_message": [],
        "i_plan_request_error_message": [],
        "i_plan_confirm_error_message": [],
        "order_item_invalid_material": [],
        "is_i_plan_error_item_all": False,
    }
    if type(error_message) == str:
        error_message = [error_message]
    send_email_after_create_sap_order(
        manager,
        file_log.uploaded_by,
        order,
        file_log,
        convert_date_time_timezone_asia(timezone.now()),
        order_partners=[],
        errors=error_message,
        errors_code=[],
        is_being_process=is_being_process,
        is_error_item=False,
        is_error_item_all=True,
        error_message_object=error_message_object,
        order_data=order_data,
    )
    return False


def _get_sold_to_address(sold_to_code):
    sold_partner_address_master = get_sold_to_partner(sold_to_code)
    list_address = ["street", "district", "city", "postal_code"]
    final_address = []
    for addr in list_address:
        name_attr = getattr(sold_partner_address_master, addr, "")
        if name_attr:
            final_address.append(name_attr)
    return " ".join(final_address)


def _segregate_i_plan_success_order_line_to_sap_order_line(
    i_plan_success_order_lines, sap_response, order_status_dict, order, dict_item_no
):
    sap_success_order_line = []
    sap_fail_order_line = i_plan_success_order_lines
    if sap_response.get("orderItemsOut"):
        order_status_dict[order.id]["order_items_out"] = len(
            sap_response.get("orderItemsOut")
        )
        sap_success_order_line = []
        sap_fail_order_line = []
        sap_response_success_line_no = [
            int(item["itemNo"])
            for item in sap_response.get("orderItemsOut")
            if not item.get("itemStatus")
        ]
        for item in i_plan_success_order_lines:
            if (
                int(dict_item_no.get(item["lineNumber"]))
                in sap_response_success_line_no
            ):
                sap_success_order_line.append(item)
            else:
                sap_fail_order_line.append(item)
    return sap_success_order_line, sap_fail_order_line


def update_status_po_file_log(file_log, status):
    file_log.status = status
    file_log.save()
    logging.info(
        f"[PO Upload] updated file log status id: '{file_log.id}' status: '{file_log.status}'"
    )


def _update_status_order_line(sap_fail_order_line, dict_order_lines, dict_item_no):
    for order_item in sap_fail_order_line:
        e_ordering_order_line = dict_order_lines.get(
            dict_item_no.get(order_item.get("lineNumber").lstrip("0"))
        )
        item_status_en = IPlanOrderItemStatus.FAILED.value
        e_ordering_order_line.item_status_en = item_status_en
        e_ordering_order_line.item_status_th = None
        e_ordering_order_line.save()


def get_po_upload_running():
    # check only date > 20/05/2023
    # delete this cond when you clean up data
    init_date_string = "2023-05-20"
    init_date = datetime.strptime(init_date_string, DateHelper.ISO_FORMAT).astimezone(
        pytz.timezone("Asia/Bangkok")
    )
    running_status = [
        SaveToSapStatus.IN_PROGRESS,
        SaveToSapStatus.CALL_IPLAN_REQUEST,
        SaveToSapStatus.CALL_SAP,
        SaveToSapStatus.CALL_IPLAN_CONFIRM,
    ]
    file_log = PoUploadFileLog.objects.filter(
        status__in=running_status,
        created_at__gte=init_date,
    ).first()
    return file_log


def convert_text_file_encoding(fp, encoding="utf-8"):
    blob = fp.read()
    fp.seek(0)
    m = magic.open(magic.MAGIC_MIME_ENCODING)
    m.load()
    detected_encoding = m.buffer(blob)
    if detected_encoding != encoding:
        if detected_encoding == "iso-8859-1":
            detected_encoding = "iso-8859-11"
        decoded_content = fp.read().decode(detected_encoding)
        content = decoded_content.encode(encoding)
        fp = io.BytesIO(content)
    return fp


def log_metric(order_id, start_time) -> None:
    for api_name in ["ES14", "ES15"]:
        force_update_attributes("function", api_name, {"orderId": order_id})
    diff_time = time.time() - start_time
    add_metric_process_order(
        settings.NEW_RELIC_CREATE_ORDER_METRIC_NAME,
        int(diff_time * 1000),
        start_time,
        "SaveOrder",
        order_type=OrderType.PO,
        order_id=order_id,
    )


def _segregate_failed_order_line_for_excel_upload(order_item_message, order_lines):
    sap_fail_order_line = []
    if order_item_message:
        for item in order_lines:
            if item.item_no in list(order_item_message.keys()):
                sap_fail_order_line.append(item)
    return sap_fail_order_line
