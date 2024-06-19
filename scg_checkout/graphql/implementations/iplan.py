# import json
import datetime
import logging
import re
import uuid
from copy import deepcopy

import pytz
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import transaction
from django.db.models import Q, F, IntegerField, Subquery
from django.db.models.functions import Cast
from django.utils import timezone
from math import floor

from common.enum import MulesoftServiceType
from common.helpers import format_sap_decimal_values_for_pdf
from common.iplan.item_level_helpers import get_product_code, get_product_and_ddq_alt_prod_of_order_line
from common.mulesoft_api import MulesoftApiRequest
from common.product_group import ProductGroup, SalesUnitEnum
from saleor.plugins.manager import get_plugins_manager
from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import OrderLines
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import (
    IPlanOrderSplitLogic,
    IPLanResponseStatus,
    IPLanConfirmStatus,
    MaterialType,
    ScgOrderStatus,
    IPlanTypeOfDelivery,
    ScgOrderStatusSAP,
    ProductionStatus,
    IPlanUpdateItemTime,
    IPlanUpdateOrderStatus,
    IPlanOrderItemStatus,
    AtpCtpStatus,
    IPlanReATPRequiredCode,
    SapUpdateFlag,
    AlternatedMaterialLogChangeError,
    ReasonForChangeRequestDateEnum, AltMaterialType, AlternatedMaterialProductGroupMatch,
)
from scg_checkout.graphql.helper import (
    PAYMENT_TERM_MAPPING,
    convert_date_time_to_timezone_asia,
    get_date_time_now_timezone_asia,
    get_name1_from_sold_to,
    update_order_lines_item_status_en_and_item_status_th,
    update_plant_for_container_order_lines,
    update_plant_for_container_order_lines_for_eo_upload,
    compute_confirm_and_request_date, compute_confirm_and_request_date_iplan_skipped, get_inquiry_method_params,
    update_mat_own, derive_and_compute_alt_mat_info,
    update_log_mat_os_quantity_details, perform_rounding_on_iplan_qty_with_decimals, get_summary_details_from_data,
    stamp_error_for_not_enough_qty_in_contract, map_variant_data_for_alt_mat, stamp_error_for_no_material_determination,
    stamp_error_for_no_material_in_contract, stamp_error_for_product_group_mismatch, log_alt_mat_errors,
    get_alternated_material_errors, get_alternated_material_related_data, get_mat_desc_from_master_for_alt_mat_old,
    delete_order_in_db_to_avoid_duplication, get_order_line_material_type,
    get_name_from_sold_to_partner_address_master, get_internal_emails_by_config, get_product_group_from_es_17
)
from scg_checkout.graphql.implementations.change_order import get_iplan_error_messages
from scg_checkout.graphql.implementations.sap import (
    request_create_order_sap,
    request_change_order_sap,
    sap_update_order,
    date_to_sap_date,
    get_sap_warning_messages,
    get_error_messages_from_sap_response_for_create_order
)
from scg_checkout.models import AlternatedMaterial
from scgp_eo_upload.implementations.helpers import eo_upload_send_email_when_call_api_fail
from scgp_export.graphql.enums import IPlanEndPoint, ItemCat
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text, resolve_sold_to_name
from scgp_po_upload.graphql.enums import (
    SapType,
    SapUpdateType,
    IPlanAcknowledge
)
from scgp_po_upload.graphql.helpers import (
    html_to_pdf,
    load_error_message,
    get_item_level_message,
    validate_order_msg,
)
from scgp_require_attention_items.graphql.enums import IPlanEndpoint
from scgp_require_attention_items.graphql.helper import (
    update_attention_type_r1,
    update_attention_type_r5,
)
from scgp_user_management.models import EmailConfigurationExternal, \
    EmailConfigurationFeatureChoices
from utils.enums import IPlanInquiryMethodCode

# XXX: iPlan want to make it shorter (temp order number)
LEN_OF_HEADER_CODE = 12
date_time_format = "%Y-%m-%d"


def update_domestic_cofirm_date_product_lines(order, ui_order_lines_info=None):
    """

    :param order:
    :param ui_order_lines_info:
    :return:
    This method is responsible for updating the confirm date in OrderLines Table from the confirm date given in UI
    """
    if (order.type == OrderType.DOMESTIC.value):
        cofirmed_date = []
        order_line_id = [k for k in ui_order_lines_info]
        tmp = []
        # for k,v in ui_order_lines_info.items():
        # cofirmed_date.append(v["request_date"])
        #   order_line_id.append(k)
        orderLines = {p.id: p for p in sap_migration_models.OrderLines.objects.filter(id__in=order_line_id)}
        for id in orderLines:
            orderLine = orderLines[id]
            ui_order_line = ui_order_lines_info[str(id)]
            orderLine.confirmed_date = ui_order_line.get("request_date")
            tmp.append(orderLine)
        sap_migration_models.OrderLines.objects.bulk_update(tmp, ["confirmed_date"])
        logging.debug(f"Updating confirmation date for order id {order.id} having lines id {order_line_id} success!! ")


def call_i_plan_create_order(order, manager, call_type=None, user=None, order_header_updated_data=None,
                             ui_order_lines_info=None):
    """
    Call i-plan to save domestic/export order
    :@param order: Order object
    :@param manager: Plugin manage
    :@param order_header_updated_data:to identify the updated fields
    :@param call_type: to identify EO upload, PO upload or normal create order
    :@return dict
    """
    order_status = order.status
    success = False
    sap_order_status = None
    sap_order_number = None
    sap_order_messages = []
    sap_item_messages = []
    i_plan_success = True
    i_plan_success_lines = []
    order_lines_iplan = []
    i_plan_messages = []
    i_plan_response = None
    sap_warning_messages = []
    order_type = order.type
    qs_order_lines = sap_migration_models.OrderLines.objects.annotate(
        item_no_int=Cast("item_no", output_field=IntegerField())).filter(order=order,
                                                                         order__status__in=[ScgOrderStatus.DRAFT.value,
                                                                                            ScgOrderStatus.PRE_DRAFT.
                                                                         value]) \
        .order_by("item_no_int")
    if not qs_order_lines:
        logging.error(f" [Create Order] DUPLICATE request for Order ID: {order.id} "
                      f" and So NO: {order.so_no} is found. Hence skipping further process")
        return {
            "success": success,
            "order_status": order_status,
            "i_plan_success": i_plan_success,
            "i_plan_response": i_plan_response,
            "sap_order_status": sap_order_status,
            "sap_order_number": sap_order_number,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
            "i_plan_messages": i_plan_messages,
            "warning_messages": sap_warning_messages,
        }
    dict_order_lines = {}
    container_order_lines = []

    need_invoke_iplan = ProductGroup.is_iplan_integration_required(order)

    for line in qs_order_lines:
        dict_order_lines[str(line.item_no)] = line
        # XXX: remove later
        if line.item_cat_eo != ItemCat.ZKC0.value:
            if need_invoke_iplan:
                order_lines_iplan.append(line)
            else:
                logging.info(f"skipping the iplan call for: {line}  as as group is not in K01/K09")
        else:
            container_order_lines.append(line)

    if order.type == OrderType.EXPORT.value:
        order_lines_iplan = filter_no_outsource_order_lines(
            order_lines=order_lines_iplan,
            order=order
        )

    try:
        if order_lines_iplan:
            logging.info(f"[{order_type} Create order] Calling... iplan")
            i_plan_response, alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors = \
                request_i_plan([order], manager, order_lines=order_lines_iplan)
            logging.info(f"[{order_type} Create order] Called iplan")
        else:
            """
            Assumption here is all the order lines will be from same group
            and it will be skipped causing the List ot be null to come to this block
            """
            logging.debug("Updating confirm date from UI dates for the ")
            update_domestic_cofirm_date_product_lines(order, ui_order_lines_info)
    except Exception as e:
        logging.exception("Call IPlan Exception:", e)
        if call_type == "eo_upload":
            eo_upload_send_email_when_call_api_fail(
                manager,
                order,
                action_type="Create",
                call_type="IPlan",
                error_response=e,
                request_type="iplan_request",
            )
        raise e
    if i_plan_response:
        i_plan_request_error_message = get_iplan_error_messages(i_plan_response)
        logging.info(f"[{order_type} Create order] iplan error messages:{i_plan_request_error_message}")
        i_plan_response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")
        if len(i_plan_response_header):
            i_plan_order = i_plan_response_header[0]
            i_plan_order_lines = i_plan_order.get("DDQResponseLine")
            c_iplan_order_lines = len(i_plan_order_lines)
            # If number of item from IPlan response is less than the number of item we send from our order
            # OR item from response IPlan is 0
            # IPlan request will be consider false
            # SEO-2458 SEO-2459
            if (
                    c_iplan_order_lines < len(order_lines_iplan) or
                    c_iplan_order_lines == 0
            ):
                i_plan_success = False
            else:
                for line in i_plan_order_lines:
                    if (
                            line.get("returnStatus").lower()
                            == IPLanResponseStatus.FAILURE.value.lower()
                    ):
                        i_plan_success = False
                        return_code = line.get("returnCode")
                        if return_code:
                            i_plan_messages.append(
                                {
                                    "item_no": line.get("lineNumber"),
                                    "first_code": return_code[18:24],
                                    "second_code": return_code[24:32],
                                    "message": line.get("returnCodeDescription"),
                                }
                            )
                        else:
                            i_plan_messages.append(
                                {
                                    "item_no": line.get("lineNumber"),
                                    "first_code": "0",
                                    "second_code": "0",
                                    "message": line.get("returnCodeDescription"),
                                }
                            )
                    else:
                        i_plan_success_lines.append(line)

            if not i_plan_success:
                # Update YT65156 - APT/CTP Response fail
                update_order_line_after_call_i_plan(dict_order_lines, i_plan_order_lines, order=order,
                                                    alt_mat_i_plan_dict=alt_mat_i_plan_dict,
                                                    alt_mat_variant_obj_dict=alt_mat_variant_obj_dict,
                                                    alt_mat_errors=alt_mat_errors)
                if call_type == "eo_upload":
                    if i_plan_success_lines:
                        tmp_iplan_response = deepcopy(i_plan_response)
                        tmp_iplan_response["DDQResponse"]["DDQResponseHeader"][0][
                            "DDQResponseLine"] = i_plan_success_lines
                        # XXX: if iplan success but some lines fail,
                        # we still need to call iplan for rollback success items
                        confirm_i_plan(
                            i_plan_response=tmp_iplan_response,
                            status=IPLanConfirmStatus.ROLLBACK.value,
                            manager=manager,
                            order=order,
                            require_attention=False
                        )

                    eo_upload_send_email_when_call_api_fail(
                        manager,
                        order,
                        action_type="Create",
                        call_type="IPlan",
                        error_response=i_plan_response,
                        request_type="iplan_request",
                    )
            else:
                order_lines = update_order_line_after_call_i_plan(dict_order_lines, i_plan_order_lines, order=order,
                                                                  alt_mat_i_plan_dict=alt_mat_i_plan_dict,
                                                                  alt_mat_variant_obj_dict=alt_mat_variant_obj_dict,
                                                                  alt_mat_errors=alt_mat_errors)
                if order.eo_upload_log:
                    '''
                        SEO-5006: After uploading EO with the mat container, system call ES-17 with plant that doesn't following the logic of plant for container.
                    '''
                    update_plant_for_container_order_lines_for_eo_upload(container_order_lines, qs_order_lines)
                else:
                    # update plant for container order lines
                    update_plant_for_container_order_lines(container_order_lines, qs_order_lines)

                try:
                    logging.info(f"[{order_type} create order] calling ES17")
                    sap_response = request_create_order_sap(need_invoke_iplan, order, manager,
                                                            order_header_updated_data,
                                                            ui_order_lines_info=ui_order_lines_info)
                    logging.info(f"[{order_type} create order] called ES17")
                except Exception as e:
                    logging.info(f"[{order_type} create order] Exception from ES17: {e}")
                    if call_type == "eo_upload":
                        confirm_i_plan(
                            i_plan_response=i_plan_response,
                            status=IPLanConfirmStatus.ROLLBACK.value,
                            manager=manager,
                            order=order,
                            order_lines=order_lines
                        )
                        eo_upload_send_email_when_call_api_fail(
                            manager,
                            order,
                            action_type="Create",
                            call_type="SAP",
                            error_response=e,
                            request_type="sap_save",
                        )
                    raise e

                sap_order_number = sap_response.get("salesdocument")
                (
                    sap_success,
                    sap_order_messages,
                    sap_item_messages,
                    sap_errors_code,
                    order_header_msg,
                    is_being_process,
                    is_items_error,
                    order_item_message
                ) = get_error_messages_from_sap_response_for_create_order(sap_response)
                logging.info(f"[{order_type} create order] sap_order_error_messages:{sap_order_messages},"
                             f" sap_item_error_messages: {sap_item_messages}")
                sap_warning_messages = get_sap_warning_messages(sap_response)
                if sap_success:
                    # Update Item Status
                    update_order_line_after_call_es_17(need_invoke_iplan, order, sap_response)
                    update_order_lines_item_status_en_and_item_status_th(
                        order,
                        order_lines
                        , IPlanOrderItemStatus.ITEM_CREATED.value,
                        IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                            IPlanOrderItemStatus.ITEM_CREATED.value
                        ),
                    )
                    try:
                        # Call i-plan confirm item when sap create order successfully
                        logging.info(f"[{order_type} create order] calling.... iplan_confirm")
                        i_plan_acknowledge = confirm_i_plan(
                            i_plan_response=i_plan_response,
                            status=IPLanConfirmStatus.COMMIT.value,
                            manager=manager,
                            sap_order_number=sap_order_number,
                            sap_response=sap_response,
                            order=order,
                            order_lines=order_lines
                        )
                        logging.info(f"[{order_type} create order] called iplan_confirm")
                        i_plan_confirm_error_message = get_iplan_error_messages(i_plan_acknowledge)
                        logging.info(
                            f"[{order_type} create order] iplan_confirm_errors : {i_plan_confirm_error_message}")
                        i_plan_acknowledge_headers = i_plan_acknowledge.get(
                            "DDQAcknowledge"
                        ).get("DDQAcknowledgeHeader")
                        if len(i_plan_acknowledge_headers):
                            # Check commit i-plan success or not to update order status
                            i_plan_acknowledge_header = i_plan_acknowledge_headers[0]
                            i_plan_acknowledge_line = i_plan_acknowledge_header.get(
                                "DDQAcknowledgeLine"
                            )
                            confirm_success = True
                            for acknowledge_line in i_plan_acknowledge_line:
                                if (
                                        acknowledge_line.get("returnStatus") or ""
                                ).lower() != IPlanAcknowledge.SUCCESS.value.lower():
                                    confirm_success = False

                                # if commit i-plan failure => order is flagged R5
                                if not confirm_success:
                                    update_attention_type_r5(qs_order_lines)
                                    i_plan_success = False
                                    return_code = acknowledge_line.get("returnCode")
                                    if return_code:
                                        i_plan_messages.append(
                                            {
                                                "item_no": acknowledge_line.get("lineNumber"),
                                                "first_code": return_code[18:24],
                                                "second_code": return_code[24:32],
                                                "message": acknowledge_line.get("returnCodeDescription"),
                                            }
                                        )
                                    else:
                                        i_plan_messages.append(
                                            {
                                                "item_no": acknowledge_line.get("lineNumber"),
                                                "first_code": "0",
                                                "second_code": "0",
                                                "message": acknowledge_line.get("returnCodeDescription"),
                                            }
                                        )
                    except Exception as e:
                        logging.info(f"[{order_type} create order] Exception from iplan_confirm: {e}")
                        update_attention_type_r5(qs_order_lines)
                        order.so_no = sap_order_number
                        order.eo_no = sap_order_number
                        order.saved_sap_at = timezone.now()
                        delete_order_in_db_to_avoid_duplication(sap_order_number)
                        order.save()
                        raise e
                    order_status = ScgOrderStatus.RECEIVED_ORDER.value
                    sap_order_status = ScgOrderStatusSAP.COMPLETE.value
                    sales_employee = get_sales_employee(sap_response.get("orderPartners", []))
                    payer_code, payer_name = get_sales_employee(sap_response.get("orderPartners", []))
                    sales_employee = f"{payer_code} - {payer_name}"
                    success = True
                    error_message_object = {
                        "order_header_msg": order_header_msg,
                        "order_item_message": order_item_message,
                        "i_plan_request_error_message": i_plan_request_error_message,
                        "i_plan_confirm_error_message": i_plan_confirm_error_message,
                    }
                    try:
                        # Need update order to send mail
                        item_no_latest = 0
                        if qs_order_lines:
                            item_no_latest = max(int(order_line.item_no) for order_line in qs_order_lines)
                        order.status = order_status
                        order.status_sap = sap_order_status
                        order.so_no = sap_order_number
                        order.eo_no = sap_order_number  # eo_no same so_no
                        order.item_no_latest = item_no_latest
                        order.sales_employee = sales_employee
                        order.saved_sap_at = timezone.now()
                        delete_order_in_db_to_avoid_duplication(sap_order_number)
                        order.save()
                        if order.type != OrderType.EXPORT.value:
                            partner_emails = get_partner_emails_from_es17_response(sap_response)
                            send_mail_customer_create_order(order, manager, user, partner_emails=partner_emails,
                                                            error_message_object=error_message_object)
                            try:
                                send_mail_customer_fail_alternate(order, manager)
                            except Exception as e:
                                logging.exception(f"[ALT MAT FEATURE] error while sending mail "
                                                  f"'Error: Alternated Material auto change':{e}")
                    except Exception as e:
                        logging.exception(e)
                else:
                    # Call i-plan rollback item when sap failed to create order
                    logging.info(f"[{order_type} create order] calling... iplan roll back as as ES17 failed")
                    confirm_i_plan(
                        i_plan_response=i_plan_response,
                        status=IPLanConfirmStatus.ROLLBACK.value,
                        manager=manager,
                        sap_order_number=sap_order_number,
                        order=order,
                        order_lines=order_lines
                    )
                    logging.info(f"[{order_type} create order] called iplan roll back")
                    sap_order_status = ScgOrderStatusSAP.BEING_PROCESS.value
                    if call_type == "eo_upload":
                        eo_upload_send_email_when_call_api_fail(
                            manager,
                            order,
                            action_type="Create",
                            call_type="SAP",
                            error_response=sap_response,
                            request_type="sap_save",
                        )
                    else:
                        transaction.set_rollback(True)

        return {
            "success": success,
            "order_status": order_status,
            "i_plan_success": i_plan_success,
            "i_plan_response": i_plan_response,
            "sap_order_status": sap_order_status,
            "sap_order_number": sap_order_number,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
            "i_plan_messages": i_plan_messages,
            "warning_messages": sap_warning_messages,
        }
    else:
        if order.eo_upload_log:
            '''
                SEO-5006: After uploading EO with the mat container, system call ES-17 with plant that doesn't following the logic of plant for container.
            '''
            update_plant_for_container_order_lines_for_eo_upload(container_order_lines, qs_order_lines)
        else:
            '''
            SEO-4359: update/set plant for container order items as per case2 in 
            wiki: https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/597721446/Default+Plant+for+Container
            get plant data from 1st item of order items post excluding container items and use that to set plant for container items
            '''
            update_plant_for_container_order_lines(container_order_lines, qs_order_lines)
            '''
               SEO-4335: for Orders with Order Items of only plant/container ES-17 should be called
            '''
        try:
            sap_response = request_create_order_sap(need_invoke_iplan, order, manager,
                                                    ui_order_lines_info=ui_order_lines_info)
            sap_success = True
        except Exception as e:
            if call_type == "eo_upload":
                eo_upload_send_email_when_call_api_fail(
                    manager,
                    order,
                    action_type="Create",
                    call_type="SAP",
                    error_response=e,
                    request_type="sap_save",
                )
            raise e
        sap_order_number = sap_response.get("salesdocument")

        (
            sap_success,
            sap_order_messages,
            sap_item_messages,
            sap_errors_code,
            order_header_msg,
            is_being_process,
            is_items_error,
            order_item_message
        ) = get_error_messages_from_sap_response_for_create_order(sap_response)

        sap_warning_messages = get_sap_warning_messages(sap_response)
        if sap_success:
            update_order_line_after_call_es_17(need_invoke_iplan, order, sap_response)
            # Update Item Status
            update_order_lines_item_status_en_and_item_status_th(
                order,
                qs_order_lines
                , IPlanOrderItemStatus.ITEM_CREATED.value,
                IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                    IPlanOrderItemStatus.ITEM_CREATED.value
                ),
            )
            order_status = ScgOrderStatus.RECEIVED_ORDER.value
            sap_order_status = ScgOrderStatusSAP.COMPLETE.value
            payer_code, payer_name = get_sales_employee(sap_response.get("orderPartners", []))
            sales_employee = f"{payer_code} - {payer_name}"
            success = True
            try:
                # Need update order to send mail
                item_no_latest = 0
                if qs_order_lines:
                    item_no_latest = max(int(order_line.item_no) for order_line in qs_order_lines)
                order.status = order_status
                order.status_sap = sap_order_status
                order.so_no = sap_order_number
                order.eo_no = sap_order_number  # eo_no same so_no
                order.item_no_latest = item_no_latest
                order.sales_employee = sales_employee
                order.saved_sap_at = timezone.now()
                delete_order_in_db_to_avoid_duplication(sap_order_number)
                order.save()

                error_message_object = {
                    "order_header_msg": order_header_msg,
                    "order_item_message": order_item_message,
                }

                if order.type != OrderType.EXPORT.value:
                    partner_emails = get_partner_emails_from_es17_response(sap_response)
                    send_mail_customer_create_order(order, manager, user, partner_emails=partner_emails,
                                                    error_message_object=error_message_object)
                    try:
                        send_mail_customer_fail_alternate(order, manager)
                    except Exception as e:
                        logging.exception(f"[ALT MAT FEATURE] error while sending mail "
                                          f"'Error: Alternated Material auto change':{e}")
            except Exception as e:
                pass
        else:
            sap_order_status = ScgOrderStatusSAP.BEING_PROCESS.value
            if call_type == "eo_upload":
                eo_upload_send_email_when_call_api_fail(
                    manager,
                    order,
                    action_type="Create",
                    call_type="SAP",
                    error_response=sap_response,
                    request_type="sap_save",
                )
    return {
        "success": success,
        "order_status": order_status,
        "i_plan_success": i_plan_success,
        "i_plan_response": i_plan_response,
        "sap_order_status": sap_order_status,
        "sap_order_number": sap_order_number,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "i_plan_messages": i_plan_messages,
        "warning_messages": sap_warning_messages,
    }


def fetch_alt_material_mappings_from_order_line(order_lines):
    query = Q()
    for line in order_lines:
        mat_input_code = line.material_variant.code
        grade_gram_code = mat_input_code[:10]
        query |= Q(alternate_material__material_own__material_code__in=[mat_input_code, grade_gram_code],
                   alternate_material__sold_to=line.order.sold_to,
                   alternate_material__sales_organization=line.order.sales_organization)
    alt_mat = sap_migration_models.AlternateMaterialOs.objects.filter(query) \
        .annotate(mat_input_code=F("alternate_material__material_own__material_code"),
                  alt_mat_code=F("material_os__material_code")) \
        .order_by("alternate_material__material_own", "priority")

    return alt_mat


def prepare_alt_mat_dict(alt_mat_dict: dict, key: str, mat_input_code: str, alt_mat_code: str,
                         alt_grade_gram_code: str):
    """
    alt_mat_dict = {
    '14088_10': {'mat_input': 'Z02CA-125D0980117N', 'alt_mat_codes': ['Z02CAA090M0980125N', 'Z02CA-125D0980117N'],
                 'alt_grade_gram_codes': ['Z02CAA090M', 'Z02CA-125D']},
    '14088_20': {'mat_input': 'Z02CA-125D1590117N', 'alt_mat_codes': ['Z02CA-125D1590117N'],
                 'alt_grade_gram_codes': ['Z02CA-125D']}}
    """
    if not alt_mat_dict.get(key):
        alt_mat_dict[key] = {'mat_input': mat_input_code, 'alt_mat_codes': [alt_mat_code],
                             'alt_grade_gram_codes': [alt_grade_gram_code]}
    else:
        alt_mat_codes = alt_mat_dict[key]["alt_mat_codes"]
        alt_grade_gram_codes = alt_mat_dict[key]["alt_grade_gram_codes"]
        if alt_mat_code not in alt_mat_codes:
            alt_mat_codes.append(alt_mat_code)
        if alt_grade_gram_code not in alt_grade_gram_codes:
            alt_grade_gram_codes.append(alt_grade_gram_code)


def generate_alt_mapping_dicts_for_order_lines(order_line_mat_to_grade_gram: dict, order_line_grade_gram_to_mat: dict,
                                               key: str,
                                               alt_mat_code: str,
                                               alt_grade_gram_code: str):
    """
    order_line_mat_to_grade_gram = {
    '14088_10': {'Z02CAA090M0980125N': ['Z02CAA090M'], 'Z02CA-125D0980117N': ['Z02CA-125D']},
    '14088_20': {'Z02CA-125D1590117N': ['Z02CA-125D'], 'Z02CA-125D1590125N': ['Z02CA-125D']}}
    order_line_grade_gram_to_mat = {
    '14088_10': {'Z02CAA090M': ['Z02CAA090M0980125N'], 'Z02CA-125D': ['Z02CA-125D0980117N']},
    '14088_20': {'Z02CA-125D': ['Z02CA-125D1590117N', 'Z02CA-125D1590125N']}}
    """
    if not order_line_mat_to_grade_gram.get(key):
        order_line_mat_to_grade_gram[key] = {alt_mat_code: [alt_grade_gram_code]}
    elif alt_mat_code not in order_line_mat_to_grade_gram.get(key):
        order_line_mat_to_grade_gram[key][alt_mat_code] = [alt_grade_gram_code]
    elif alt_grade_gram_code not in order_line_mat_to_grade_gram[key][alt_mat_code]:
        order_line_mat_to_grade_gram[key][alt_mat_code].append(alt_grade_gram_code)

    if not order_line_grade_gram_to_mat.get(key):
        order_line_grade_gram_to_mat[key] = {alt_grade_gram_code: [alt_mat_code]}
    elif alt_grade_gram_code not in order_line_grade_gram_to_mat.get(key):
        order_line_grade_gram_to_mat[key][alt_grade_gram_code] = [alt_mat_code]
    elif alt_mat_code not in order_line_grade_gram_to_mat[key][alt_grade_gram_code]:
        order_line_grade_gram_to_mat[key][alt_grade_gram_code].append(alt_mat_code)


def prepare_alt_mat_mappings_for_order_lines(order_lines, mat_os):
    order_line_alt_mat_dict, alt_mat_dict = {}, {}
    order_line_mat_to_grade_gram, order_line_grade_gram_to_mat = {}, {}
    for line in order_lines:
        material_variant = line.material_variant
        material_type = get_order_line_material_type(line, material_variant)
        if material_type and material_type not in AltMaterialType.MATERIAL.value and \
                material_type not in AltMaterialType.GRADE_GRAM.value:
            continue
        mat_input_code = material_variant.code
        grade_gram_mat_input_code = material_variant.code[:10]
        mat_input_size = material_variant.code[10:14]
        alt_mat_mapping = mat_os.filter(Q(Q(mat_input_code=mat_input_code)))
        if alt_mat_mapping:
            key = f"{line.order_id}_{line.item_no}"
            for alt_material in alt_mat_mapping:
                alt_mat_code = alt_material.alt_mat_code
                alt_mat_grade_gram_code = alt_mat_code[:10]
                prepare_alt_mat_dict(
                    alt_mat_dict, key, mat_input_code, alt_mat_code, alt_mat_grade_gram_code)
                generate_alt_mapping_dicts_for_order_lines(order_line_mat_to_grade_gram, order_line_grade_gram_to_mat,
                                                           key, alt_mat_code, alt_mat_grade_gram_code)

        else:
            alt_mat_mapping_grade_gram = mat_os.filter(Q(Q(mat_input_code=grade_gram_mat_input_code)))
            if alt_mat_mapping_grade_gram:
                key = f"{line.order_id}_{line.item_no}"
                for alt_mat_grade_gram in alt_mat_mapping_grade_gram:
                    alt_mat_code = f"{alt_mat_grade_gram.alt_mat_code}{mat_input_size}{alt_mat_grade_gram.diameter}N"
                    alt_mat_grade_gram_code = alt_mat_grade_gram.alt_mat_code
                    prepare_alt_mat_dict(
                        alt_mat_dict, key, mat_input_code, alt_mat_code, alt_mat_grade_gram_code)
                    generate_alt_mapping_dicts_for_order_lines(order_line_mat_to_grade_gram,
                                                               order_line_grade_gram_to_mat,
                                                               key, alt_mat_code, alt_mat_grade_gram_code)
    logging.info(
        f"[ALT MAT FEATURE] Step1: alt_mat_dict: {alt_mat_dict},"
        f" order_line_mat_to_grade_gram: {order_line_mat_to_grade_gram}, "
        f" order_line_grade_gram_to_mat: {order_line_grade_gram_to_mat}")
    return alt_mat_dict, order_line_mat_to_grade_gram, order_line_grade_gram_to_mat


def generate_alt_mat_es_14_dict(alt_mat_i_plan_dict, contract_material, key, mat_code, line, order_product_group,
                                **kwargs):
    """
    @param alt_mat_i_plan_dict:
    @param contract_material:
    @param key:
    @param mat_code: Alt Material code
    @param line:
    @param kwargs: key is_product_grp_check_required: False for PO Upload Flow alone. Rest cases it's True by default
    @param order_product_group:
        Will be set to
        1. NOT_MATCHED:
            if key:is_product_grp_check_required is True and Product group of alt mat
            doesn't match with Order's product group
        2. MATCHED:
            if key: is_product_grp_check_required is False or Product group of alt mat
            matches with Order product group

    @return:
    """
    is_product_grp_check_required = kwargs.get('is_product_grp_check_required', True)
    if not alt_mat_i_plan_dict.get(key):
        alt_mat_i_plan_dict[key] = {
            "order_line_obj": line,
            "alt_mat_codes": [],
            "alt_grade_gram_codes": [],
            "is_product_group_match": AlternatedMaterialProductGroupMatch.MATCHED
        }
        if is_product_grp_check_required and order_product_group != contract_material.mat_group_1:
            alt_mat_i_plan_dict[key]["is_product_group_match"] = AlternatedMaterialProductGroupMatch.NOT_MATCHED.value
        if AlternatedMaterialProductGroupMatch.MATCHED.value == alt_mat_i_plan_dict[key]["is_product_group_match"]:
            if contract_material.mat_type in AltMaterialType.GRADE_GRAM.value:
                alt_mat_i_plan_dict[key]["alt_grade_gram_codes"].append(mat_code)
            elif contract_material.mat_type in AltMaterialType.MATERIAL.value:
                alt_mat_i_plan_dict[key]["alt_mat_codes"].append(mat_code)
    else:
        if not is_product_grp_check_required or order_product_group == contract_material.mat_group_1:
            alt_mat_i_plan_dict[key]["is_product_group_match"] = AlternatedMaterialProductGroupMatch.MATCHED.value
        else:
            alt_mat_i_plan_dict[key]["is_product_group_match"] = AlternatedMaterialProductGroupMatch.NOT_MATCHED.value

        if AlternatedMaterialProductGroupMatch.MATCHED.value == alt_mat_i_plan_dict[key]["is_product_group_match"]:
            if contract_material.mat_type in AltMaterialType.GRADE_GRAM.value:
                alt_grade_gram_codes = alt_mat_i_plan_dict[key]["alt_grade_gram_codes"]
                if mat_code not in alt_grade_gram_codes:
                    alt_grade_gram_codes.append(mat_code)
            elif contract_material.mat_type in AltMaterialType.MATERIAL.value:
                alt_mat_codes = alt_mat_i_plan_dict[key]["alt_mat_codes"]
                if mat_code not in alt_mat_codes:
                    alt_mat_codes.append(mat_code)


def compare_and_filter_enough_qty_alt_mat(alt_mat_code, alt_mat_remaining_qty_dict, key, alt_mat_qty_in_ton,
                                          mat_code_to_pop, order_line_mat_to_grade_gram):
    alt_mat_remaining_qty = 0
    material_obj = None
    for data in alt_mat_remaining_qty_dict.get(key, {}):
        if data.get('mat_code') == alt_mat_code:
            alt_mat_remaining_qty = data.get('remaining_qty')
            material_obj = data.get('material_obj')
            break
        elif (
                order_line_mat_to_grade_gram.get(key, {}).get(alt_mat_code, [])
                and data.get('mat_code') == order_line_mat_to_grade_gram.get(key, {}).get(alt_mat_code, [])[0]
        ):
            alt_mat_remaining_qty = data.get('remaining_qty')
            material_obj = data.get('material_obj')
            break

    if alt_mat_remaining_qty < alt_mat_qty_in_ton:
        if alt_mat_code not in mat_code_to_pop:
            mat_code_to_pop.append(alt_mat_code)
    return material_obj


def check_remain_qty_and_filter_alt_mat(alt_mat_errors, alt_mat_i_plan_dict, alt_mat_remaining_qty_dict,
                                        order_line_mat_to_grade_gram, alt_mat_variant_obj_dict):
    alt_mat_codes_for_conversion = set()
    logging.info(f"[ALT MAT FEATURE] Step3: check if Alt Mat has enough qty in ref. contract - STARTED")
    for key, value in alt_mat_i_plan_dict.items():
        alt_mat_codes_for_conversion.update(set(value.get('alt_mat_codes')))
    conversions = sap_master_data_models.Conversion2Master.objects.filter(
        material_code__in=alt_mat_codes_for_conversion, to_unit='ROL'
    )
    material_variants = sap_migration_models.MaterialVariantMaster.objects.filter(
        code__in=alt_mat_codes_for_conversion).order_by("code", "-id").distinct("code")

    alt_mat_mappings_key_not_in_contract = []
    """
    NOTE: Alt Mat Feature is applicable for K01 and K09 materials only.
            Remaining Qty weight unit for K01 and K09 materials is always 'TON'
    1. Compute 1ROL of Alt mat in a TON  using a conversion factor
        a. 1ROL of Alt mat = X TON
    2. Based on the user-requested qty compute the overall QTY needed for the alt mat
        a. alt mat user requested qty in TON = OrderLine QTY * X
    3. Compare point#2a value against remaining qty
        a. Remaining QTY >= OrderLine QTY * X  → QTY of alt mat available
        b. Remaining QTY < OrderLine QTY * X  → QTY of alt mat NOT available
    """
    for key, value in alt_mat_i_plan_dict.items():
        line = value.get('order_line_obj')
        mat_code_to_pop = []
        for code in value.get('alt_mat_codes'):
            variant_conversion = conversions.filter(material_code=code).last()
            alt_mat_qty_in_ton = round(float(line.quantity) * float(variant_conversion.calculation) / 1000, 3)
            material_obj = compare_and_filter_enough_qty_alt_mat(code, alt_mat_remaining_qty_dict, key,
                                                                 alt_mat_qty_in_ton, mat_code_to_pop,
                                                                 order_line_mat_to_grade_gram)
            if code not in mat_code_to_pop:
                alt_mat_variant_obj_dict[code] = material_variants.filter(code=code, material=material_obj).first()
        if mat_code_to_pop:
            for code in mat_code_to_pop:
                if code in value.get('alt_mat_codes'):
                    value.get('alt_mat_codes').remove(code)
        stamp_error_for_not_enough_qty_in_contract(alt_mat_errors, alt_mat_mappings_key_not_in_contract, key, line,
                                                   value)
    for key in alt_mat_mappings_key_not_in_contract:
        alt_mat_i_plan_dict.pop(key)
    logging.info(
        f"[ALT MAT FEATURE] Step3: check Alt Mat has enough qty in ref. contract - COMPLETED. "
        f" Data is: {alt_mat_i_plan_dict}")


def process_alt_mat_es_14(alt_mat_dict, alt_mat_i_plan_dict, alt_mat_remaining_qty_dict, line, **kwargs):
    """
    alt_mat_remaining_qty_dict = {'14091_10': [
    {'mat_code': 'Z02CA-125D0980117N', 'type': '81', 'material_obj': '<MaterialMaster: MaterialMaster object (37219)>',
     'remaining_qty': 48688.53, 'weight_unit': 'TON'},
    {'mat_code': 'Z02CAA090M0980125N', 'type': '82', 'material_obj': '<MaterialMaster: MaterialMaster object (39643)>',
     'remaining_qty': 49639.88, 'weight_unit': 'TON'},
    {'mat_code': 'Z02CA-125D', 'type': '84', 'material_obj': '<MaterialMaster: MaterialMaster object (37162)>',
     'remaining_qty': 46983.67, 'weight_unit': 'TON'}],
    '14091_20': [
        {'mat_code': 'Z02CA-125D', 'type': '84', 'material_obj': '<MaterialMaster: MaterialMaster object (37162)>',
         'remaining_qty': 46983.67, 'weight_unit': 'TON'}]}
    alt_mat_i_plan_dict = {'14088_10': {'alt_mat_codes': ['Z02CA-125D0980117N', 'Z02CAA090M0980125N'],
                                       'alt_grade_gram_codes': ['Z02CA-125D'], 'is_product_group_match': 'MATCHED'},
                          '14088_20': {'alt_mat_codes': [], 'alt_grade_gram_codes': ['Z02CA-125D'], 'is_product_group_match': 'MATCHED'},
                          '14088_30': {'alt_mat_codes': [], 'alt_grade_gram_codes': [], 'is_product_group_match': 'NA'},
                          '14088_40': {'alt_mat_codes': [], 'alt_grade_gram_codes': [], 'is_product_group_match': 'NOT_MATCHED'}}
    """
    key = f"{line.order_id}_{line.item_no}"
    order = line.order
    contract = order.contract
    order_product_group = order.product_group
    if alt_mat_dict.get(key):
        mat_codes = set()
        alt_mat_codes = alt_mat_dict.get(key)["alt_mat_codes"]
        alt_grade_gram_codes = alt_mat_dict.get(key)["alt_grade_gram_codes"]
        mat_codes.update(alt_mat_codes)
        mat_codes.update(alt_grade_gram_codes)
        contract_materials = sap_migration_models.ContractMaterial.objects.filter(
            contract=contract,
            material__in=Subquery(sap_migration_models.MaterialMaster.objects.filter(material_code__in=mat_codes).
                                  values('id'))
        ).select_related('material').order_by("mat_type")
        logging.info(f"[ALT MAT FEATURE] materials found in contract: {contract} are: {contract_materials}")
        if not contract_materials:
            alt_mat_i_plan_dict[key] = {"order_line_obj": line, "alt_mat_codes": [], "alt_grade_gram_codes": [],
                                        "is_product_group_match": AlternatedMaterialProductGroupMatch.NA.value}
        for contract_material in contract_materials:
            mat_code = contract_material.material.material_code
            if not alt_mat_remaining_qty_dict.get(key):
                alt_mat_remaining_qty_dict[key] = [
                    {"mat_code": mat_code, "type": contract_material.mat_type,
                     "remaining_qty": contract_material.remaining_quantity,
                     "weight_unit": contract_material.weight_unit,
                     "material_obj": contract_material.material}]
            else:
                alt_mat_remaining_qty_dict[key].append(
                    {"mat_code": mat_code, "type": contract_material.mat_type,
                     "remaining_qty": contract_material.remaining_quantity,
                     "weight_unit": contract_material.weight_unit,
                     "material_obj": contract_material.material})
            generate_alt_mat_es_14_dict(alt_mat_i_plan_dict, contract_material, key, mat_code, line,
                                        order_product_group, **kwargs)


def get_material_variants_by_product_from_es15(sold_to_code: str, material_codes: set):
    # call es15 and format the response
    logging.info(
        f"[ALT MAT FEATURE] checking if Materials: {material_codes} belong to customer i.e.,sold to code: {sold_to_code}")
    param = {
        "piMessageId": str(uuid.uuid1().int),
        "date": datetime.datetime.now().strftime("%d/%m/%Y"),
        "customerNo": sold_to_code,
        "product": [
            {
                "productCode": material_code
            }
            for material_code in material_codes
        ]
    }
    uri = "sales/materials/search"
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        uri,
        param
    )
    if not response.get("data", []):
        logging.info(
            f"[ALT MAT FEATURE] Materials belong to customer i.e.,sold to code: {sold_to_code} are : NONE")
        return None

    es_15_variant_data = response.get("data")[0].get("productList", [])
    grade_gram_es_15_dict = map_variant_data_for_alt_mat(es_15_variant_data)
    logging.info(
        f"[ALT MAT FEATURE] Step2: Materials belong to customer i.e., "
        f"sold to code: {sold_to_code} are : {grade_gram_es_15_dict}")
    return grade_gram_es_15_dict


def process_alt_mat_es_15(alt_grade_gram_codes_for_es15, alt_mat_i_plan_dict,
                          alt_mat_mappings_key_not_in_contract, log_alt_mat_error, order_line_grade_gram_to_mat,
                          sold_to_code):
    logging.info(f"[ALT MAT FEATURE] Step2(a): check if Alt Mat belong to customer (ES-15) or not "
                 f"wherever required - STARTED")
    grade_gram_es_15_dict = get_material_variants_by_product_from_es15(sold_to_code, alt_grade_gram_codes_for_es15)
    for key, value in alt_mat_i_plan_dict.items():
        if value.get('is_es_15_required'):
            alt_grade_gram_codes = value.get('alt_grade_gram_codes', [])
            for alt_grade_gram_code in alt_grade_gram_codes:
                mat_code_from_es_15 = grade_gram_es_15_dict.get(alt_grade_gram_code, [])
                grade_gram_to_mat = order_line_grade_gram_to_mat.get(key, {}).get(alt_grade_gram_code, [])
                for mat in grade_gram_to_mat:
                    if mat in mat_code_from_es_15:
                        value.get('alt_mat_codes', []).append(mat)
            stamp_error_for_no_material_determination(alt_grade_gram_codes, alt_mat_mappings_key_not_in_contract, key,
                                                      log_alt_mat_error, value)
    logging.info(f"[ALT MAT FEATURE] Step2(a): check if Alt Mat belong to customer (ES-15) or not "
                 f"wherever required - COMPLETED.")


def check_if_es_15_required_or_not(alt_grade_gram_codes_es14, alt_grade_gram_codes_for_es15, alt_mat_codes_es14,
                                   alt_mat_dict, key, value, order_line_mat_to_grade_gram):
    if len(alt_mat_codes_es14) > 0:
        diff_set = (set(alt_mat_dict.get(key, {}).get("alt_mat_codes", []))).difference(set(alt_mat_codes_es14))
        if diff_set and len(alt_grade_gram_codes_es14) > 0:
            for alt_mat_code in alt_mat_codes_es14:
                mat_to_grade_grams = order_line_mat_to_grade_gram.get(key, {}).get(alt_mat_code, [])
                for mat_to_grade_gram in mat_to_grade_grams:
                    if mat_to_grade_gram in alt_grade_gram_codes_es14:
                        alt_grade_gram_codes_es14.remove(mat_to_grade_gram)
            value['is_es_15_required'] = True
            alt_grade_gram_codes_for_es15.update(alt_grade_gram_codes_es14)
        else:
            value['is_es_15_required'] = False
    elif len(alt_grade_gram_codes_es14) > 0:
        value['is_es_15_required'] = True
        alt_grade_gram_codes_for_es15.update(alt_grade_gram_codes_es14)
    else:
        value['is_es_15_required'] = False


def validate_and_filter_alt_mat_codes(alt_mat_i_plan_dict, alt_mat_errors, alt_mat_dict, sold_to_code,
                                      order_line_grade_gram_to_mat, order_line_mat_to_grade_gram):
    alt_mat_mappings_key_not_in_contract = []
    alt_grade_gram_codes_for_es15 = set()
    for key, value in alt_mat_i_plan_dict.items():
        alt_mat_codes_es14 = value.get('alt_mat_codes', [])
        alt_grade_gram_codes_es14 = value.get('alt_grade_gram_codes', [])
        is_product_group_match = value.get('is_product_group_match')
        stamp_error_for_no_material_in_contract(alt_grade_gram_codes_es14, alt_mat_codes_es14, is_product_group_match,
                                                alt_mat_mappings_key_not_in_contract, key, alt_mat_errors, value)
        stamp_error_for_product_group_mismatch(alt_grade_gram_codes_es14, alt_mat_codes_es14, is_product_group_match,
                                               alt_mat_mappings_key_not_in_contract, key, alt_mat_errors, value)
        check_if_es_15_required_or_not(alt_grade_gram_codes_es14, alt_grade_gram_codes_for_es15, alt_mat_codes_es14,
                                       alt_mat_dict, key, value, order_line_mat_to_grade_gram)

    if alt_grade_gram_codes_for_es15:
        process_alt_mat_es_15(alt_grade_gram_codes_for_es15, alt_mat_i_plan_dict,
                              alt_mat_mappings_key_not_in_contract, alt_mat_errors, order_line_grade_gram_to_mat,
                              sold_to_code)
    logging.info(f"[ALT MAT FEATURE] Step2 checks COMPLETED. "
                 f"Exclude item Nos from Alt Mat Flow: {alt_mat_mappings_key_not_in_contract}")
    for key in alt_mat_mappings_key_not_in_contract:
        alt_mat_i_plan_dict.pop(key)
    logging.info(f"[ALT MAT FEATURE] Step2: Summary of Materials found in contract: {alt_mat_i_plan_dict}")
    return alt_mat_i_plan_dict, alt_mat_errors


def update_alt_mat_codes_by_priority(alt_mat_dict, alt_mat_i_plan_dict):
    """
    Updates 'alt_mat_codes' in alt_mat_i_plan_dict with sorted values from alt_mat_dict.
    Args:
        alt_mat_dict (dict): The dictionary with alt_mat_codes data based on priority.
        alt_mat_i_plan_dict (dict): The dictionary to update.
    Returns:
        None
    """
    for key, value in alt_mat_i_plan_dict.items():
        alt_mat_codes_list = alt_mat_dict.get(key).get('alt_mat_codes', [])
        sorted_alt_mat_codes = []
        for code in alt_mat_codes_list:
            if code in value.get('alt_mat_codes', []):
                sorted_alt_mat_codes.append(code)
        alt_mat_i_plan_dict[key]['alt_mat_codes'] = sorted_alt_mat_codes


def process_and_validate_alt_mat_codes(order_lines: OrderLines, alt_mat_dict: dict, order_line_mat_to_grade_gram: dict,
                                       order_line_grade_gram_to_mat: dict, **kwargs):
    """
     Based on Alt Mat mapping per order line, perform below checks and filter data which doesn't satisfy criteria
     Step 2: Check for Full Alt Mat code and Grade Gram codes in Contract (check in contractMaterial table)
     Step 2B. If full alt mat code is not found in contract but Grade Gram code is found then use Alt Mat. Grade/gram
     and get all materials belong to customer (via ES-15). filter records in which full alt mat codes is found.
     If None found per order line stamp errors accordingly
     Step 3: compare for QTY of order ine mat against remaining QTY of Alt Mat Code
     Sort the Alt Mat codes based on priority using alt_mat_dict
     Args:
         order_lines (OrderLine) : Order Lines of an order
         alt_mat_dict (dict): for each order line we capture alt mat codes based on priority
         order_line_mat_to_grade_gram (dict): Per Each Order Line dictionary with key: Full Mat code
         whose value are respective Grade Gram codes
         order_line_grade_gram_to_mat (dict): Per Each Order Line dictionary with key: Grade Gram codes
         whose value are respective full mat codes
    Returns:
        alt_mat_i_plan_dict, alt_mat_errors, alt_mat_variant_obj_dict
        @param order_line_mat_to_grade_gram:
        @param order_line_grade_gram_to_mat:
        @param alt_mat_dict:
        @param order_lines:
        @param product_group_check:
    """
    alt_mat_remaining_qty_dict = {}
    alt_mat_i_plan_dict = {}
    alt_mat_errors = list()
    alt_mat_variant_obj_dict = {}
    sold_to_code = ""
    logging.info(f"[ALT MAT FEATURE] Step2: check if Alt Mat belong to contract or not - STARTED")
    for line in order_lines:
        order = line.order
        contract = order.contract
        if contract and contract.sold_to:
            sold_to_code = contract.sold_to.sold_to_code if contract and contract.sold_to else order.sold_to_code
        process_alt_mat_es_14(alt_mat_dict, alt_mat_i_plan_dict, alt_mat_remaining_qty_dict, line, **kwargs)
    logging.info(f"[ALT MAT FEATURE] Step2: check if Alt Mat belong to contract or not - COMPLETED"
                 f" ES14 call results: {alt_mat_remaining_qty_dict},"
                 f" alt_mat_i_plan_dict: {alt_mat_i_plan_dict}")

    alt_mat_i_plan_dict, alt_mat_errors = validate_and_filter_alt_mat_codes(alt_mat_i_plan_dict, alt_mat_errors,
                                                                            alt_mat_dict, sold_to_code,
                                                                            order_line_grade_gram_to_mat,
                                                                            order_line_mat_to_grade_gram)

    check_remain_qty_and_filter_alt_mat(alt_mat_errors, alt_mat_i_plan_dict, alt_mat_remaining_qty_dict,
                                        order_line_mat_to_grade_gram, alt_mat_variant_obj_dict)
    update_alt_mat_codes_by_priority(alt_mat_dict, alt_mat_i_plan_dict)
    logging.info(f"[ALT MAT FEATURE] Step4: Alt Mat Mappings will used in IPlan request per "
                 f" item no in order {alt_mat_i_plan_dict}")
    return alt_mat_i_plan_dict, alt_mat_errors, alt_mat_variant_obj_dict


def alternate_material_and_log_change(order_lines, **kwargs):
    mat_os = fetch_alt_material_mappings_from_order_line(order_lines)
    # if alternate materials are not available then no need to check further
    if not mat_os:
        return {}, {}, {}
    alt_mat_dict, order_line_mat_to_grade_gram, order_line_grade_gram_to_mat = \
        prepare_alt_mat_mappings_for_order_lines(order_lines, mat_os)
    alt_mat_i_plan_dict, alt_mat_errors, alt_mat_variant_obj_dict = \
        process_and_validate_alt_mat_codes(order_lines, alt_mat_dict, order_line_mat_to_grade_gram,
                                           order_line_grade_gram_to_mat, **kwargs)
    return alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors


def get_sales_employee(order_partners):
    partner_no = None
    for order_partner in order_partners:
        if order_partner.get("partnerRole", "") == "VE":
            partner_no = order_partner.get("partnerNo", "")
            break
    sales_employee = resolve_display_text(partner_no)
    return partner_no, sales_employee


def prepare_alternate_materials_list(alt_mat_i_plan_dict, alt_mat_variant_obj_dict, order, qs_order_lines,
                                     alt_mat_errors, **kwargs):
    # ALT MAT FEATURE logic is applicable only for Domestic orders (i.e., Domestic, PO Upload & Customer)
    """
    config.enable_alt_mat_outsource_feature will check the DB (table: plugins_pluginconfiguration) first for the value,
    If it doesn't have a value in the database, it will look for the default configuration value in the plugin.py file.
    If config.enable_alt_mat_outsource_feature is False, the system will immediately return from the function; otherwise
    (if config.enable_alt_mat_outsource_feature is True), it will prepare_alternate_materials_list.
    """
    manager = get_plugins_manager()
    _plugin = manager.get_plugin("scg.settings")
    config = _plugin.config
    if not config.enable_alt_mat_outsource_feature:
        return
    if OrderType.EXPORT.value != order.type:
        order_line_of_order = qs_order_lines.filter(order=order, material_variant__isnull=False) \
            .select_related('order', 'material_variant', 'material', 'order__sold_to')
        alt_mat_dict, alt_mat_variants, alt_mat_mapping_errors = alternate_material_and_log_change(
            order_line_of_order, **kwargs
        )
        alt_mat_i_plan_dict.update(alt_mat_dict)
        alt_mat_variant_obj_dict.update(alt_mat_variants)
        alt_mat_errors.extend(alt_mat_mapping_errors)


def request_i_plan(orders, manager, is_dummy_order="true", order_lines=None):
    """
    Call i-plan to request reserve orders
    :params orders: list e-ordering order
    :return: i-plan response
    """
    qs_order_lines = sap_migration_models.OrderLines.objects.filter(order__in=orders)
    dict_order_lines = {}
    # material_ids = []
    for line in qs_order_lines:
        if not dict_order_lines.get(line.order_id):
            dict_order_lines[line.order_id] = []
        dict_order_lines[line.order_id].append(line)
        # material_ids.append(line.material.id)

    alt_mat_i_plan_dict, alt_mat_variant_obj_dict = {}, {}
    alt_mat_errors = []
    for order in orders:
        prepare_alternate_materials_list(alt_mat_i_plan_dict, alt_mat_variant_obj_dict, order, qs_order_lines,
                                         alt_mat_errors)

    request_headers = []
    if order_lines:
        request_header, list_mat_os_and_mat_i_plan = prepare_request_header_ctp_ctp(
            orders[0],
            order_lines,
            alt_mat_i_plan_dict,
            is_dummy_order,
        )
        request_headers.append(request_header)
    else:
        for order in orders:
            order_lines = dict_order_lines.get(order.id) or []
            request_header, list_mat_os_and_mat_i_plan = prepare_request_header_ctp_ctp(
                order,
                order_lines,
                alt_mat_i_plan_dict,
                is_dummy_order,
            )
            request_headers.append(request_header)
    # XXX: add prefix 'DO' to prevent error 'existing order'
    request_id = 'DO' + str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE]
    request_params = {
        "DDQRequest": {
            "requestId": request_id,
            "sender": "e-ordering",
            "DDQRequestHeader": request_headers,
        }
    }
    log_val = {
        "orderid": orders[0].id,
        "order_number": orders[0].so_no,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value,
                                           **log_val).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_REQUEST.value,
        request_params
    )
    perform_rounding_on_iplan_qty_with_decimals(response)
    return response, alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors


# follow SEO-961: export => single_source True, customer/domestic => single_source False
def prepare_request_header_ctp_ctp(
        order, order_lines, alt_mat_i_plan_dict, is_dummy_order="true", require_attention=False,
):
    request_lines = []
    consignmentLocation = get_contract_consignment_location_from_order(order)
    for order_line in order_lines:
        alternate_products, product_code = get_product_and_ddq_alt_prod_of_order_line(alt_mat_i_plan_dict, order,
                                                                                      order_line)

        parameter = change_parameter_follow_inquiry_method(order_line, order)
        inquiry_method = parameter.get("inquiry_method")
        use_inventory = parameter.get("use_inventory")
        use_consignment_inventory = parameter.get("use_consignment_inventory")
        use_projected_inventory = parameter.get("use_projected_inventory")
        use_production = parameter.get("use_production")
        order_split_logic = parameter.get("order_split_logic").upper()
        single_source = parameter.get("single_source")
        re_atp_required = parameter.get("re_atp_required")

        # I-plan unique customer code
        fmt_sold_to_code = (
                                   order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
                           ).lstrip("0") or None
        request_line = {
            "inquiryMethod": inquiry_method,
            "useInventory": use_inventory,
            "useConsignmentInventory": use_consignment_inventory,
            "useProjectedInventory": use_projected_inventory,
            "useProduction": use_production,
            "orderSplitLogic": order_split_logic,
            "singleSourcing": single_source,
            "lineNumber": str(order_line.item_no),
            "locationCode": fmt_sold_to_code,
            "productCode": product_code
            if order_line.material_variant
            else (order_line.material_code or ""),
            "quantity": str(order_line.quantity) if order_line.quantity else "0",
            "typeOfDelivery": IPlanTypeOfDelivery.EX_MILL.value,
            "requestType": "NEW" if not require_attention else "AMENDMENT",
            "unit": "ROL",
            "transportMethod": "Truck",
            "reATPRequired": re_atp_required,
            "requestDate": order_line.request_date
                           and order_line.request_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                           or "",
            "consignmentOrder": False,
            "consignmentLocation": consignmentLocation,
            "fixSourceAssignment": order_line.plant or "",
            "DDQSourcingCategories": [
                {"categoryCode": order.sales_organization.code},
                {"categoryCode": order.sales_group.code}
            ]
        }
        if alternate_products and len(alternate_products):
            request_line["DDQAlternateProducts"] = alternate_products
        request_lines.append(request_line)
    params = {
        "headerCode": str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE] if not require_attention else order.so_no.lstrip("0"),
        "autoCreate": False,  # TRUE for dummy order FALSE for customer order
        "DDQRequestLine": request_lines,
    }
    return params, alt_mat_i_plan_dict


def confirm_i_plan(
        i_plan_response,
        status,
        manager,
        sap_order_number=None,
        sap_response=None,
        order=None,
        order_lines=None,
        require_attention=False,
):
    """
    Commit or Rollback iPlan response
    @param i_plan_response:
    @param status:
    @param manager:
    @param sap_order_number:
    @param sap_response:
    @param order: eOrdering order object
    @param order_lines: param for walking around issue SEO-2741
    @return:
    """
    confirm_headers = []
    response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")[0]
    dict_order_schedules_out = {}

    if sap_response:
        order_schedules_outs = sap_response.get("orderSchedulesOut", [])
        dict_order_schedules_out = {str(order_schedule["itemNo"]).lstrip("0"): order_schedule["confirmQty"] for
                                    order_schedule in order_schedules_outs}

    order_lines = order_lines or sap_migration_models.OrderLines.objects.filter(order=order, iplan__isnull=False)
    dict_order_lines = {str(o_line.original_item_no or o_line.item_no): o_line for o_line in order_lines}

    i_plan_order_lines = response_header.get("DDQResponseLine")
    confirm_lines = []
    for line in i_plan_order_lines:
        line_number = str(line.get("lineNumber")).lstrip("0")
        if line.get("returnStatus").lower() != IPLanResponseStatus.FAILURE.value.lower():

            order_line = dict_order_lines.get(line_number)
            on_hand_quantity_confirmed = handle_on_hand_quantity_confirmed(line, dict_order_schedules_out, order_line)
            order_information_type = handle_order_information_type(order, status)

            ddq_order_information_type = handle_ddq_order_information_type(require_attention, order_information_type)
            confirm_line = {
                "lineNumber": order_line.item_no,
                "originalLineNumber": line_number,
                "onHandQuantityConfirmed": str(on_hand_quantity_confirmed),
                "unit": line.get("unit"),
                "status": status,
                "DDQOrderInformationType": ddq_order_information_type
            }
        else:
            confirm_line = {
                "lineNumber": str(int(float(line_number))),
                "originalLineNumber": line_number,
                "status": status,
                "DDQOrderInformationType": []
            }

        confirm_lines.append(
            confirm_line
        )
    header_code = handle_header_code(status, sap_order_number, response_header)
    original_header_code = handle_original_header_code(response_header, require_attention, header_code)
    confirm_headers.append(
        {
            "headerCode": header_code,
            "originalHeaderCode": original_header_code,
            "DDQConfirmLine": sorted(confirm_lines, key=lambda x: float(x['lineNumber'])),
        }
    )

    confirm_params = {
        "DDQConfirm": {
            "requestId": "DO" + str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE],
            "sender": "e-ordering",
            "DDQConfirmHeader": confirm_headers,
        }
    }
    log_val = {
        "orderid": order.id,
        "order_number": order.so_no or sap_order_number or None,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value,
                                           **log_val).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_CONFIRM.value,
        confirm_params,
        encode=True
    )
    return response


def call_i_plan_update_order_eo_upload(order, manager):
    """
    Call i-plan to update order eo-upload
    :param order: Order object
    :param manager: Plugin manage
    :return E-ordering order status
    """
    try:
        i_plan_response, *_ = request_i_plan([order], manager)
    except Exception as e:
        eo_upload_send_email_when_call_api_fail(
            manager,
            order,
            action_type="Update",
            call_type="IPlan",
            error_response=e,
            request_type="iplan_request",
        )
        raise e

    i_plan_response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")
    if len(i_plan_response_header):
        i_plan_order = i_plan_response_header[0]
        i_plan_order_lines = i_plan_order.get("DDQResponseLine")
        i_plan_success = True
        for line in i_plan_order_lines:
            if (
                    line.get("returnStatus").lower()
                    == IPLanResponseStatus.FAILURE.value.lower()
            ):
                i_plan_success = False

        if not i_plan_success:
            # Call iPlan rollback if any item fail
            confirm_i_plan(
                i_plan_response=i_plan_response,
                status=IPLanConfirmStatus.ROLLBACK.value,
                manager=manager,
                order=order
            )
            eo_upload_send_email_when_call_api_fail(
                manager,
                order,
                action_type="Update",
                call_type="IPlan",
                error_response=i_plan_response,
                request_type="iplan_request",
            )
            return ScgOrderStatus.DRAFT.value, i_plan_response
        else:
            # Call SAP to save order
            try:
                sap_response = request_change_order_sap(order, i_plan_order_lines, manager)
            except Exception as e:
                eo_upload_send_email_when_call_api_fail(
                    manager,
                    order,
                    action_type="Update",
                    call_type="SAP",
                    error_response=e,
                    request_type="sap_update",
                )
                raise e
            sap_success = True
            sap_order_number = order.so_no
            if sap_response.get("return"):
                for data in sap_response.get("return"):
                    if data.get("type") != SapUpdateType.SUCCESS.value:
                        sap_success = False
            if sap_success:
                # Call i-plan confirm item when sap create order successfully
                confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.COMMIT.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order
                )
                return ScgOrderStatus.RECEIVED_ORDER.value, i_plan_response
            else:
                # Call i-plan rollback item when sap failed to create order
                confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.ROLLBACK.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order
                )
                eo_upload_send_email_when_call_api_fail(
                    manager,
                    order,
                    action_type="Update",
                    call_type="SAP",
                    error_response=sap_response,
                    request_type="sap_update",
                )
                return ScgOrderStatus.RECEIVED_ORDER.value, i_plan_response


def get_po_number_from_order(order):
    if order.type == "domestic" or order.type == "customer":
        po_number = order.po_number
    else:
        po_number = order.po_no
    return po_number if po_number else ""


def get_order_remark_order_info(order):
    if order.type == "domestic" or order.type == "export":
        return order.internal_comments_to_logistic or ""
    if order.type == "customer":
        return order.internal_comments_to_logistic or order.remark_for_logistic or ""


def get_order_remark_order_info_for_print_preview_order(order):
    if order.type == "domestic" or order.type == "export":
        return order.internal_comments_to_logistic or ""
    if order.type == "customer":
        return order.remark_for_invoice or order.remark_for_logistic or ""


def send_mail_customer_create_order(order, manager, user, partner_emails=None, error_message_object=None):
    order_lines = list(sap_migration_models.OrderLines.objects.filter(order=order))
    order_lines.sort(key=lambda line: int(line.item_no))

    sold_to_code = order.contract.sold_to.sold_to_code
    date_now = timezone.now().astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d%m%Y")
    file_name_pdf = f"{order.so_no}{sold_to_code}{date_now}"
    [_, *_ship_to_list] = order.ship_to and order.ship_to.split(" - ") or []
    sold_to_name_list = get_name1_from_sold_to(sold_to_code).split(" - ")  # TODO: improve this
    note = order.item_note or get_order_remark_order_info(order)
    if len(note) == 0:
        note = None

    order_item_message = error_message_object.get("order_item_message")
    i_plan_request_error_message = error_message_object.get(
        "i_plan_request_error_message"
    )
    i_plan_confirm_error_message = error_message_object.get(
        "i_plan_confirm_error_message"
    )
    order_header_message = error_message_object.get("order_header_msg")

    template_data = {
        "order_number": order.so_no,
        "customer_po_number": get_po_number_from_order(order),
        "file_name": "",
        "record_date": convert_date_time_to_timezone_asia(order.saved_sap_at),
        "customer_name": sold_to_name_list[1],
        "place_of_delivery": (" - ".join(_ship_to_list)).strip(),
        "payment_terms": PAYMENT_TERM_MAPPING.get(order.contract.payment_term_key, order.contract.payment_term),
        "shipping": "ส่งให้",
        "contract_number": get_contract_no_name_from_order(order),
        "note": note,
        "alt_mat_errors": get_alternated_material_errors(order)
    }
    data = [
        {
            "item_no": order_line.item_no,
            "material_description": get_alternated_material_related_data(
                order_line,
                get_material_desc_from_material_master_using_order_line(order_line)),
            "qty": (f"{order_line.quantity:.3f}" if order_line.quantity and
                                                    SalesUnitEnum.is_qty_conversion_to_decimal(order_line.sales_unit)
                    else int(order_line.quantity) if order_line.quantity
            else 0),  # TODO add helper on handlebars
            "sales_unit": order_line.sales_unit,
            "qty_ton": format_sap_decimal_values_for_pdf(order_line.net_weight_ton),
            "request_delivery_date": order_line.original_request_date.strftime("%d.%m.%Y")
            if order_line.original_request_date
            else "",
            "iplan_confirm_date": order_line.request_date.strftime("%d.%m.%Y")
            if order_line.request_date
            else "",
            "message": get_item_level_message(
                order_item_message,
                i_plan_request_error_message,
                i_plan_confirm_error_message,
                order_line,
            ),
            "material_code": order_line.material.material_code
        }
        for order_line in order_lines
    ]
    sales_unit, total_qty, total_qty_ton = get_summary_details_from_data(data)
    ship_to = order.ship_to and order.ship_to.split("\n")
    remark_order_info = get_order_remark_order_info(order)
    if len(remark_order_info) == 0:
        remark_order_info = None
    created_by = order.created_by
    template_pdf_data = {
        "po_no": get_po_number_from_order(order),
        "sale_org_name": get_sale_org_name_from_order(order),
        "so_no": order.so_no,
        "file_name": "",
        "date_time": convert_date_time_to_timezone_asia(order.saved_sap_at),
        "sold_to_no_name": " - ".join(sold_to_name_list),
        "sold_to_address": get_address_from_order(order, "AG"),
        "ship_to_no_name": ship_to and ship_to[0] or "",
        "ship_to_address": ship_to[1] if ship_to and len(ship_to) == 2 else "",
        "payment_method_name": get_payment_method_name_from_order(order),
        "contract_no_name": get_contract_no_name_from_order(order),
        "remark_order_info": remark_order_info,
        "created_by": f"{created_by.first_name if created_by else ''} {created_by.last_name if created_by else ''}",
        "errors": [],
        "data": data,
        "total_qty": total_qty,
        "total_qty_ton": total_qty_ton,
        "sales_unit": sales_unit,
        "file_name_pdf": file_name_pdf,
        'print_date_time': get_date_time_now_timezone_asia(),
        "message": "\n".join(order_header_message)
        if len(order_header_message) > 0
        else "",
    }
    pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")

    internal_emails = get_internal_emails_by_config(EmailConfigurationFeatureChoices.CREATE_ORDER,
                                                    order.sales_organization.code,
                                                    order.product_group)
    external_email_to_list, external_cc_to_list = get_external_emails_by_config(
        EmailConfigurationFeatureChoices.CREATE_ORDER,
        sold_to_code,
        order.product_group)
    if partner_emails is None:
        partner_emails = []

    mail_to = list(set(external_email_to_list + [user.email]))
    cc_list = list(set(partner_emails + internal_emails + external_cc_to_list))

    manager.scgp_po_upload_send_mail(
        "scg.email",
        mail_to,
        template_data,
        f"{get_stands_for_company(order)} Order submitted : {get_sold_to_no_name(sold_to_code, True)}",
        "index.html",
        pdf,
        file_name_pdf,
        cc_list=cc_list
    )
    return mail_to, cc_list


def get_external_emails_by_config(feature_name, sold_to_code, product_group):
    product_group_query = Q()
    if type(product_group) == list:
        for pg in product_group:
            product_group_query |= Q(product_group__iexact=pg.strip())
    elif type(product_group) == str:
        product_group_query |= Q(product_group__iexact=product_group.strip())

    product_group_query |= Q(product_group__isnull=True)
    product_group_query |= Q(product_group__regex=r'^\s*$')
    product_group_query |= Q(product_group__regex=r'^"\s*"$')
    product_group_query |= Q(product_group__iexact='All')
    email_configs = EmailConfigurationExternal.objects.filter(
        product_group_query,
        sold_to_code__regex=r'^0*' + sold_to_code.lstrip('0') + '$',
        feature__iexact=feature_name.strip(),
    )

    mail_to_list = []
    cc_to_list = []

    for email_config in email_configs:
        if email_config.mail_to and email_config.mail_to.strip() != '':
            mail_to = email_config.mail_to.split(',')
            mail_to_list.extend(mail_to)
        if email_config.cc_to and email_config.cc_to.strip() != '':
            cc_to = email_config.cc_to.split(',')
            cc_to_list.extend(cc_to)

    return mail_to_list, cc_to_list


def get_material_description_from_order_line(order_line):
    try:
        material = sap_master_data_models.MaterialMaster.objects.filter(
            Q(material_code=order_line.material_variant.code) | Q(
                material_code=order_line.material_variant.material.material_code)).first()
        return material.description_en or material.name
    except Exception:
        return ""


def get_material_desc_from_material_master_using_order_line(order_line):
    try:
        material = sap_master_data_models.MaterialMaster.objects.filter(
            material_code=order_line.material_variant.code
        ).first()
        return material.description_en
    except Exception:
        return ""


def get_material_variant_description_en_from_order_line(order_line):
    try:
        material = sap_migration_models.MaterialVariantMaster.objects.filter(
            code=order_line.material_variant.code).first()
        return material.description_en
    except Exception:
        return ""


def get_sales_unit_from_order_line(order_line):
    try:
        return order_line.material_variant.sales_unit
    except Exception:
        return ""


def get_qty_ton_from_order_line(order_line):
    try:
        quantity = order_line.quantity
        material_code = order_line.material_variant.code
        conversion = sap_master_data_models.Conversion2Master.objects.filter(
            material_code=material_code, to_unit="ROL"
        ).last()
        calculation = conversion.calculation
        order_quantity_ton = float(quantity) * float(calculation) / 1000
        return f"{order_quantity_ton:.3f}"
    except Exception:
        return f"{order_line.quantity:.3f}"


def get_address_by_sold_to_code_and_partner_code(sold_to_code, partner_code, partner_role):
    try:
        address = ""
        sold_to_channel_partner = (
            sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
                sold_to_code=sold_to_code,
                partner_code=partner_code,
                partner_role=partner_role,
            ).first()
        )
        if sold_to_channel_partner:
            address_link = sold_to_channel_partner.address_link
            partner_code = sold_to_channel_partner.partner_code
            sold_to_partner_address = (
                sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
                    sold_to_code=sold_to_code,
                    address_code=address_link,
                    partner_code=partner_code,
                ).first()
            )

            address = (
                f"{sold_to_partner_address.street} {sold_to_partner_address.district} "
                f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"
            )

        return address

    except Exception:
        return None


def get_address_from_order(order, partner_role):
    try:
        address = ""
        sold_to_code = order.contract.sold_to.sold_to_code
        sold_to_channel_partner = (
            sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
                sold_to_code=sold_to_code,
                partner_code=sold_to_code,
                partner_role=partner_role,
            ).first()
        )
        if sold_to_channel_partner:
            address_link = sold_to_channel_partner.address_link
            partner_code = sold_to_channel_partner.partner_code
            sold_to_partner_address = (
                sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
                    sold_to_code=sold_to_code,
                    address_code=address_link,
                    partner_code=partner_code,
                ).first()
            )

            address = (
                f"{sold_to_partner_address.street} {sold_to_partner_address.district} "
                f"{sold_to_partner_address.city} {sold_to_partner_address.postal_code}"
            )

        return address

    except Exception:
        return None


def get_payment_method_name_from_order(order):
    try:
        return f"{order.contract.payment_term_key} - {PAYMENT_TERM_MAPPING.get(order.contract.payment_term_key, order.contract.payment_term)}"
    except Exception:
        return ""


def get_contract_no_name_from_order(order):
    try:
        contract_no = order.contract.code
        contract_name = order.contract.project_name
        if not contract_name:
            return contract_no
        return contract_no + " - " + contract_name
    except Exception:
        return ""


def get_sale_org_name_from_order(order):
    try:
        return order.sales_organization.full_name
    except Exception:
        return ""


def get_sold_to_no_name_from_order(order):
    try:
        return f"{order.contract.sold_to.sold_to_code} {order.contract.sold_to.sold_to_name}"
    except Exception:
        return ""


def get_sold_to_no_name(sold_to_code, subject=False, return_only_name=False):
    try:
        sold_to_name = resolve_sold_to_name(sold_to_code)
        if return_only_name:
            return sold_to_name

        s = ":" if subject else "-"
        return f"{sold_to_code} {s} {sold_to_name}"
    except Exception:
        return ""


def get_sold_to_name(sold_to_code, show_code=False):
    try:
        val = sap_master_data_models.SoldToMaster.objects.filter(sold_to_code=sold_to_code).first().sold_to_name
        if show_code:
            val = f"{sold_to_code} - {val}"
        return val
    except Exception:
        return ""


def get_stands_for_company(order):
    try:
        return "TCP" if order.sales_organization.code == "7540" else "SKIC"
    except Exception:
        return "TCP"


def update_remark_order_line(order_line_remark, remark):
    if not order_line_remark:
        return remark
    if remark not in order_line_remark:
        return ', '.join(sorted(map(lambda x: x.strip(), f"{order_line_remark}, {remark}".split(","))))
    return order_line_remark


def request_api_change_order(
        order,
        manager,
        origin_order_lines,
        updated_order_lines,
        call_type=None,
        sap_update_flag=None,
        original_order=None,
        updated_data=None,
        pre_update_lines={},
        export_delete_flag=True,
        only_update=False,
        require_attention=False
):
    """
    Call i-plan and SAP to update order
    If call SAP error then rollback order
    If call i-plan error then update required attention is R5
    @param order:
    @param manager:
    @param origin_order_lines: order line before update
    @param updated_order_lines: order line after updated
    @param call_type: use for send mail from eo upload feature.
    @param sap_update_flag:
    @param original_order:
    @return:
    """
    # mark order line change request date
    mapping_origin_order_line = {}
    for order_line in origin_order_lines:
        mapping_origin_order_line[str(order_line.item_no)] = order_line
    order_lines_change_request_date = {}
    order_lines_update_remark = []
    for order_line in updated_order_lines:
        if (
                str(order_line.item_no) in mapping_origin_order_line
                and mapping_origin_order_line[str(order_line.item_no)].request_date
                != order_line.request_date
        ):
            order_lines_change_request_date[order_line.item_no] = order_line.request_date_change_reason

            # stamp remark C3 C4 for order line
            # UI is passing only value as either C4 or C3
            remark = "C4" if order_line.request_date_change_reason == ReasonForChangeRequestDateEnum.C4.value else "C3"
            order_line.remark = update_remark_order_line(order_line.remark, remark)
            order_lines_update_remark.append(order_line)

    # update remark C3 C4 for order line when change order line request date
    sap_migration_models.OrderLines.objects.bulk_update(order_lines_update_remark, ["remark"])

    # Validation order data after change
    success = True
    sap_order_messages = []
    sap_item_messages = []
    i_plan_messages = []
    logging.info(f"For Order id: {order.id},Calling check_recall_i_plan method")
    result = check_recall_i_plan(order, origin_order_lines, updated_order_lines, sap_update_flag)
    i_plan_update_items = result.get("i_plan_update_items")
    new_items = result.get("new_items", [])
    delete_items = result.get("delete_items", [])
    updated_items = result.get("update_items", []) if only_update else []

    # Call ES27 to update order item which are changed quantity, plant, request date
    if len(
            update_items := i_plan_update_items.get(
                IPlanUpdateItemTime.BEFORE_PRODUCTION.value
            )
    ):
        # Set flag for update item
        update_items_flag = {}
        for item in update_items:
            update_items_flag[str(item.item_no)] = SapUpdateFlag.UPDATE.value

        # Call i-plan to get new solution
        # and call SAP to update order
        logging.info(f"For Order id: {order.id},Calling recall_i_plan_atp_ctp method")
        response = recall_i_plan_atp_ctp(
            order,
            update_items,
            manager,
            call_type=call_type,
            sap_update_flag=update_items_flag,
            original_order=original_order,
            original_order_lines=origin_order_lines,
            pre_update_lines=pre_update_lines,
            export_delete_flag=export_delete_flag,
            updated_items=update_items,
            require_attention=False
        )
        if not response.get("success"):
            success = False
        sap_order_messages += response.get("sap_order_messages")
        sap_item_messages += response.get("sap_item_messages")
        i_plan_messages += response.get("i_plan_messages")
    else:
        if len(
                update_items := i_plan_update_items.get(
                    IPlanUpdateItemTime.DURING_PRODUCTION.value
                )
        ):
            call_i_plan_update_order(order, update_items, manager, call_type=call_type)
            # Update attention for items that have changed request_date before confirmed_date
            update_attention_r1_items = result.get("update_attention_r1_items")
            if update_attention_r1_items and len(update_attention_r1_items):
                update_attention_type_r1(update_attention_r1_items)

        if len(
                update_items := i_plan_update_items.get(
                    IPlanUpdateItemTime.AFTER_PRODUCTION.value
                )
        ):
            # Call SAP to update order
            # and call i-plan after SAP success
            # Call ES21 to update order items which are inserted or aren't changed plant, quantity, request date
            call_i_plan_update_order(order, update_items, manager, call_type=call_type)
    es21_items_flag = {}
    for new_item in new_items:
        es21_items_flag[str(new_item.item_no)] = SapUpdateFlag.INSERT.value
    for delete_item in delete_items:
        es21_items_flag[str(delete_item.item_no)] = SapUpdateFlag.DELETE.value

    if success:
        # only call es21 when iplan return success for all lines
        (
            es_21_sap_response_success,
            es_21_sap_order_messages,
            es_21_sap_item_messages,
            *_
        ) = sap_update_order(order, manager, es21_items_flag, order_lines_change_request_date, origin_order_lines,
                             original_order, updated_data=updated_data, pre_update_lines=pre_update_lines,
                             export_delete_flag=export_delete_flag, updated_items=updated_items)
        sap_order_messages += es_21_sap_order_messages
        sap_item_messages += es_21_sap_item_messages
        if not es_21_sap_response_success:
            success = False

    return {
        "success": success,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "i_plan_messages": i_plan_messages,
    }


def check_recall_i_plan(order, origin_order_lines, updated_order_lines, sap_update_flag):
    """
    Validation updatable field
    and compare original order lines vs updated order line
    to check re-call i-plan
    @param order: order object
    @param origin_order_lines: list order line before update
    @param updated_order_lines: list order line after update
    @param sap_update_flag: status to call SAP for each item
    @return: dict: {
        update_attention_r1_items: Item need update attention
        i_plan_update_items: Item need call i-plan to update
    }
    """
    order_status = order.status
    order_status_rank = ScgOrderStatus.STATUS_RANK.value
    if order_status in order_status_rank and order_status_rank.index(
            order_status
    ) == order_status_rank.index(ScgOrderStatus.COMPLETED_ORDER.value):
        raise ValidationError(
            {
                "order": ValidationError(
                    "Cannot update the completed order.",
                    code=ContractCheckoutErrorCode.NOT_FOUND.value,
                )
            }
        )

    dict_origin_order_lines = {}
    for ol in origin_order_lines:
        dict_origin_order_lines[ol.item_no] = ol

    production_status_rank = ProductionStatus.STATUS_RANK.value
    item_status_rank = IPlanOrderItemStatus.IPLAN_ORDER_LINE_RANK.value
    new_items = []
    delete_items = []
    update_items = []

    update_attention_r1_items = []

    i_plan_update_items = {
        IPlanUpdateItemTime.BEFORE_PRODUCTION.value: [],
        IPlanUpdateItemTime.DURING_PRODUCTION.value: [],
        IPlanUpdateItemTime.AFTER_PRODUCTION.value: [],
    }

    for updated_line in updated_order_lines:
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.INSERT.value:
            # Case create new item
            new_items.append(
                updated_line
            )
            continue
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.DELETE.value:
            # Case delete item
            delete_items.append(
                updated_line
            )
            continue
        if sap_update_flag.get(updated_line.item_no, "") == SapUpdateFlag.UPDATE.value:
            # Case update item
            update_items.append(
                updated_line
            )
        production_status = updated_line.production_status
        origin_line = dict_origin_order_lines.get(updated_line.item_no)

        is_line_updated = False
        es27_updatable_field = [
            "quantity",
            "request_date",
            "plant",
        ]
        for attr in es27_updatable_field:
            if getattr(updated_line, attr) != getattr(origin_line, attr):
                is_line_updated = True

        # Only call iplan if order line was updated and has NOT special plant(SEO-3361)
        if not (is_line_updated and not has_special_plant(updated_line)):
            continue

        # If item status is complete => raise error
        # If item status >= partial delivery => not allow change plant, qty, request date
        item_status = updated_line.item_status_en
        if item_status == IPlanOrderItemStatus.COMPLETE_DELIVERY.value:
            raise ValidationError(
                {
                    "order_item": ValidationError(
                        "Cannot update the Completed Delivery item.",
                        code=ContractCheckoutErrorCode.NOT_FOUND.value,
                    )
                }
            )

        if item_status in item_status_rank and item_status_rank.index(
                item_status
        ) >= item_status_rank.index(IPlanOrderItemStatus.PARTIAL_DELIVERY.value):
            if (
                    origin_line.request_date != updated_line.request_date
                    or origin_line.quantity != updated_line.quantity
                    or origin_line.plant != updated_line.plant
            ):
                raise ValidationError(
                    {
                        "order_item": ValidationError(
                            "Cannot update the Partial Delivery item.",
                            code=ContractCheckoutErrorCode.NOT_FOUND.value,
                        )
                    }
                )

        # Check i-plan is ATP or CTP
        # If ‘ATP': On hand stock = 'True’ AND All operation fields is Blank field
        # If ‘ATP Future': On hand stock = 'False’ AND All operation fields is blank field
        # If ‘CTP': On hand stock = 'False’ AND one of operation fields is not blank field
        is_ctp_status = False
        if not updated_line.i_plan_on_hand_stock and updated_line.i_plan_operations:
            is_ctp_status = True

        if not is_ctp_status:
            i_plan_update_items[IPlanUpdateItemTime.BEFORE_PRODUCTION.value].append(
                updated_line
            )
            continue

        if production_status in production_status_rank:
            if (
                    production_status_rank.index(production_status)
                    < production_status_rank.index(ProductionStatus.CLOSE_RUN.value)
            ):
                # Scenario 1
                # Change item before production [Production Status < Close Run]
                # Plant [Allow to change]
                # Request Delivery Date  [Allow to change]
                # Order QTY [Allow to change]
                # Call i-plan for new solution
                if (
                        origin_line.request_date != updated_line.request_date
                        or origin_line.quantity != updated_line.quantity
                        or origin_line.plant != updated_line.plant
                ):
                    i_plan_update_items[
                        IPlanUpdateItemTime.BEFORE_PRODUCTION.value
                    ].append(updated_line)
            elif production_status_rank.index(
                    production_status
            ) < production_status_rank.index(ProductionStatus.COMPLETED.value):
                # Scenario 2
                # Change item during production [Production Status < Completed]
                # Plant [Not Allow to change]
                # Request Delivery Date [Allow to change]
                # Order QTY [Allow to decrease]
                if origin_line.plant != updated_line.plant:
                    raise ValidationError(
                        {
                            "plant": ValidationError(
                                "Cannot update plant for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.quantity < updated_line.quantity:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "Cannot increase quantity for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if (
                        origin_line.request_date != updated_line.request_date
                        or origin_line.quantity != updated_line.quantity
                ):
                    if updated_line.request_date < updated_line.confirmed_date:
                        update_attention_r1_items.append(updated_line)
                    i_plan_update_items[
                        IPlanUpdateItemTime.DURING_PRODUCTION.value
                    ].append(updated_line)
            elif production_status_rank.index(
                    production_status
            ) == production_status_rank.index(ProductionStatus.COMPLETED.value):
                # Scenario 3
                # Change item after production [Production Status = Completed]
                # Plant [Not Allow to change]
                # Request Delivery Date [Allow to change if after confirm date]
                # Order QTY [Allow to decrease]
                if origin_line.plant != updated_line.plant:
                    raise ValidationError(
                        {
                            "plant": ValidationError(
                                "Cannot update plant for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.quantity < updated_line.quantity:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "Cannot increase quantity for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if origin_line.confirmed_date < updated_line.request_date:
                    raise ValidationError(
                        {
                            "request_date": ValidationError(
                                "Cannot update request date before confirmed date for this order",
                                code=ContractCheckoutErrorCode.NOT_FOUND.value,
                            )
                        }
                    )

                if (
                        origin_line.request_date != updated_line.request_date
                        or origin_line.quantity != updated_line.quantity
                ):
                    i_plan_update_items[
                        IPlanUpdateItemTime.AFTER_PRODUCTION.value
                    ].append(updated_line)
        elif (
                origin_line.request_date != updated_line.request_date
                or origin_line.quantity != updated_line.quantity
                or origin_line.plant != updated_line.plant
        ):
            # Case production status is None or not in production_status_rank anhht
            i_plan_update_items[
                IPlanUpdateItemTime.BEFORE_PRODUCTION.value
            ].append(updated_line)
    return {
        "update_attention_r1_items": update_attention_r1_items,
        "i_plan_update_items": i_plan_update_items,
        "new_items": new_items,
        "delete_items": delete_items,
        "update_items": update_items
    }


def recall_i_plan_atp_ctp(order, update_items, manager, call_type=None, sap_update_flag=None, original_order=None,
                          original_order_lines=None, pre_update_lines={}, export_delete_flag=True, updated_items=[],
                          require_attention=False):
    """
    Re-call i-plan to get new solution
    and call SAP to update order when i-plan response new solution
    @param order:
    @param update_items:
    @param manager:
    @param sap_update_flag:
    @param call_type: use for send mail from eo upload feature
    @return:
    """
    success = True
    sap_order_messages = []
    sap_item_messages = []
    i_plan_messages = []
    order_lines_iplan = []
    dummy_order = "false"

    qs_order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    dict_order_lines = {}
    container_order_lines = []
    for line in qs_order_lines:
        dict_order_lines[line.item_no] = line
        # [SEO-3929] Not call Iplan with special plant
        if line.item_cat_eo != ItemCat.ZKC0.value and not has_special_plant(line):
            order_lines_iplan.append(line)
        else:
            container_order_lines.append(line)
    if call_type == "eo_upload":
        order_lines_iplan = filter_no_outsource_order_lines(order_lines_iplan)

    i_plan_response = request_i_plan_to_get_new_solution(
        order, update_items, manager, dummy_order, order_lines_iplan, require_attention
    )
    i_plan_response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")

    if len(i_plan_response_header):
        i_plan_order = i_plan_response_header[0]
        i_plan_order_lines = i_plan_order.get("DDQResponseLine")
        for i_plan_line in i_plan_order_lines:
            if i_plan_line.get("returnStatus", "").lower() == IPLanResponseStatus.FAILURE.value.lower():
                # If call i-plan fail then rollback order
                success = False
                return_code = i_plan_line.get("returnCode")
                if return_code:
                    i_plan_messages.append(
                        {
                            "item_no": i_plan_line.get("lineNumber"),
                            "first_code": return_code[24:32],
                            "second_code": return_code[18:24],
                            "message": i_plan_line.get("returnCodeDescription")
                        }
                    )
                else:
                    i_plan_messages.append(
                        {
                            "item_no": i_plan_line.get("lineNumber"),
                            "first_code": "0",
                            "second_code": "0",
                            "message": ""
                        }
                    )

        # update plant for container order lines
        update_plant_for_container_order_lines(container_order_lines, qs_order_lines)

        if not success:
            # Call iPlan rollback if any item fail
            confirm_i_plan(
                i_plan_response=i_plan_response,
                status=IPLanConfirmStatus.ROLLBACK.value,
                manager=manager,
                order=order,
                require_attention=False
            )
            if call_type == "eo_upload":
                eo_upload_send_email_when_call_api_fail(
                    manager, order, "Update", "IPlan", i_plan_response, "iplan_request")
        else:
            # If SAP success, update i-plan operation to order line, update atc_ctp status to order line i_plan
            e_ordering_order_lines = []
            e_ordering_order_lines_i_plan = []
            for i_plan_line in i_plan_order_lines:
                line_id = i_plan_line.get("lineNumber")
                e_ordering_order_line = dict_order_lines.get(line_id)
                if not e_ordering_order_line:
                    continue

                i_plan_on_hand_stock = i_plan_line.get("onHandStock")
                i_plan_operations = i_plan_line.get("DDQResponseOperation") or None

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
                    e_ordering_order_line_i_plan = (
                        sap_migration_models.OrderLineIPlan.objects.create(
                            atp_ctp=atp_ctp_status
                        )
                    )
                    e_ordering_order_line.iplan = e_ordering_order_line_i_plan
                else:
                    e_ordering_order_line_i_plan.atp_ctp_detail = atp_ctp_status
                    e_ordering_order_lines_i_plan.append(e_ordering_order_line_i_plan)

                # Update order line table
                e_ordering_order_line.i_plan_on_hand_stock = i_plan_on_hand_stock
                e_ordering_order_line.i_plan_operations = i_plan_operations
                # save return status for mock confirmed date
                e_ordering_order_line.return_status = i_plan_line.get("status", "")
                e_ordering_order_lines.append(e_ordering_order_line)

            sap_migration_models.OrderLines.objects.bulk_update(
                e_ordering_order_lines,
                fields=[
                    "i_plan_on_hand_stock",
                    "i_plan_operations",
                    "iplan",
                    "return_status",
                ],
            )

            if len(e_ordering_order_lines_i_plan):
                sap_migration_models.OrderLineIPlan.objects.bulk_update(
                    e_ordering_order_lines_i_plan,
                    fields=[
                        "atp_ctp",
                    ],
                )

            # Call sap to update
            (
                sap_response_success,
                sap_order_messages,
                sap_item_messages,
                sap_warning_messages
            ) = sap_update_order(
                order,
                manager,
                sap_update_flag=sap_update_flag,
                original_order=original_order,
                origin_order_lines=original_order_lines,
                updated_data=original_order,
                pre_update_lines=pre_update_lines,
                export_delete_flag=export_delete_flag,
                updated_items=updated_items
            )
            sap_order_number = order.so_no
            if sap_response_success:
                # Call i-plan confirm item when sap update order successfully
                i_plan_acknowledge = confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.COMMIT.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order
                )
                i_plan_acknowledge_headers = i_plan_acknowledge.get(
                    "DDQAcknowledge"
                ).get("DDQAcknowledgeHeader")

                # Check commit i-plan success or not to update R5 flag for e-ordering line
                update_attention_r5_items = []
                if len(i_plan_acknowledge_headers):
                    i_plan_acknowledge_header = i_plan_acknowledge_headers[0]
                    i_plan_acknowledge_line = i_plan_acknowledge_header.get(
                        "DDQAcknowledgeLine"
                    )

                    confirm_success_line_ids = []
                    for acknowledge_line in i_plan_acknowledge_line:
                        so_no = i_plan_acknowledge_header.get("headerCode").zfill(10)
                        if (
                                acknowledge_line.get("returnStatus").lower()
                                == IPlanAcknowledge.SUCCESS.value
                        ):
                            item = sap_migration_models.OrderLines.objects.filter(order__so_no=so_no,
                                                                                  item_no=acknowledge_line.get(
                                                                                      "lineNumber")).first()
                            confirm_success_line_ids.append(item.id)

                    for update_item in update_items:
                        if update_item.id not in confirm_success_line_ids:
                            update_attention_r5_items.append(update_item)

                if len(update_attention_r5_items):
                    update_attention_type_r5(update_attention_r5_items)
            else:
                success = False
                # Call i-plan rollback item when sap failed to create order
                confirm_i_plan(
                    i_plan_response=i_plan_response,
                    status=IPLanConfirmStatus.ROLLBACK.value,
                    manager=manager,
                    sap_order_number=sap_order_number,
                    order=order
                )
    else:
        success = False

    return {
        "success": success,
        "i_plan_response": i_plan_response,
        "sap_order_messages": sap_order_messages,
        "sap_item_messages": sap_item_messages,
        "i_plan_messages": i_plan_messages,
    }


def call_i_plan_update_order(order, update_items, manager, call_type=None):
    """
    call i-plan to update order
    @param order: list e-ordering order
    @param update_items:
    @param manager:
    @param call_type: use for send mail eo upload feature
    @return:
    """
    i_plan_response = request_i_plan_to_update_order(order, update_items, manager)
    i_plan_response_lines = i_plan_response.get("OrderUpdateResponse").get(
        "OrderUpdateResponseLine"
    )

    response_success = True
    # Check commit i-plan success or not to update R5 flag
    update_attention_r5_items = []
    if len(i_plan_response_lines):
        for line in i_plan_response_lines:
            confirm_success_line_ids = []
            if line.get("returnStatus") == IPlanUpdateOrderStatus.SUCCESS.value:
                confirm_success_line_ids.append(line.get("lineCode"))
            else:
                response_success = False

            if len(confirm_success_line_ids):
                for update_item in update_items:
                    if update_item.id in confirm_success_line_ids:
                        update_attention_r5_items.append(update_item)

    if len(update_attention_r5_items):
        update_attention_type_r5(update_attention_r5_items)

    if (not response_success) and call_type == "eo_upload":
        eo_upload_send_email_when_call_api_fail(manager, order, "Update", "IPlan", i_plan_response, "iplan_update")


def request_i_plan_to_update_order(order, update_items, manager):
    """
    Call API Order Update i-plan
    @param order:
    @param update_items:
    @param manager:
    @return:
    """
    update_lines = []
    order_number = order.so_no
    for item in update_items:
        # Need update with split spec
        # if {Check order has split item}:
        #     split_lines.append({
        #         "newOrderNumber": item,
        #         "newLineCode": "10",
        #         "deliveryDate": "date",
        #         "quantity": "number",
        #         "unit": "string"
        #     })
        update_line = {
            "orderNumber": order_number.lstrip("0"),
            "lineCode": item.item_no,
            "requestDate": item.request_date and item.request_date.strftime('%Y-%m-%dT%H:%M:%SZ') or "",
            "quantity": item.quantity,
            "unit": item.sales_unit,
            "deliveryDate": item.confirmed_date and item.confirmed_date.strftime('%Y-%m-%dT%H:%M:%SZ') or ""
        }
        update_lines.append(update_line)

    request_params = {
        "OrderUpdateRequest": {
            "updateId": str(uuid.uuid1().int),
            "OrderUpdateRequestLine": update_lines,
        }
    }
    log_val = {
        "order_number": order_number,
        "orderid": order.id,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value,
                                           **log_val).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_UPDATE_ORDER.value,
        request_params,
        encode=True
    )
    return response


def request_i_plan_to_get_new_solution(
        order, update_items, manager, is_dummy_order="false", order_lines=None, require_attention=False
):
    """
    Call i-plan to request reserve orders
    :params orders: list e-ordering order
    :return: i-plan response
    """
    list_alternate_materials = {}
    request_headers = []
    if update_items or require_attention:
        request_header, *_ = prepare_request_header_ctp_ctp(
            order, update_items, list_alternate_materials, is_dummy_order, require_attention=True
        )
        request_headers.append(request_header)
    elif order_lines:
        request_header, *_ = prepare_request_header_ctp_ctp(
            order, order_lines, list_alternate_materials, is_dummy_order
        )
        request_headers.append(request_header)

    request_id = 'DO' + str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE]
    request_params = {
        "DDQRequest": {
            "requestId": request_id,
            "sender": "e-ordering",
            "DDQRequestHeader": request_headers,
        }
    }

    # Hard code response
    # TODO: remove after i-plan is ready
    # Start hard code response
    response_headers = []
    response_lines = []
    for line in update_items:
        response_lines.append(
            {
                "lineNumber": str(line.item_no),
                "productCode": "productCodeA01",
                "status": "Confirmed",
                "deliveryDate": "2022-09-12T09:11:49.661Z",
                "dispatchDate": "2022-09-12T09:11:49.661Z",
                "quantity": 444,
                "unit": "BU_SaleUnitA01",
                "onHandStock": True,
                "warehouseCode": "WareHouseCodeA01",
                "returnStatus": "Partial Success",
                "returnCode": "Only X Tonnes available",
                "returnCodeDescription": "returnCodeDescriptionA01",
                "DDQResponseOperation": [],
            }
        )
    response_headers.append(
        {
            "headerCode": "AA112233",
            "DDQResponseLine": response_lines,
        }
    )

    # End hard code response
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_REQUEST.value,
        request_params,
        encode=True
    )

    return response


def change_parameter_inquiry_method(order_line_inquiry_method, order_type, flag=None):
    inquiry_method_params = get_inquiry_method_params(order_line_inquiry_method)
    if InquiryMethodType.ASAP.value == order_line_inquiry_method and OrderType.EXPORT.value == order_type:
        inquiry_method_params["re_atp_required"] = IPlanReATPRequiredCode.FALSE.value
    if flag == "NEW":
        inquiry_method_params["order_split_logic"] = IPlanOrderSplitLogic.NO_SPLIT.value
    return inquiry_method_params


def change_parameter_follow_inquiry_method(order_line, order, flag=None):
    return change_parameter_inquiry_method(order_line.inquiry_method, order.type, flag)


def po_upload_request_i_plan(order, manager, order_data_from_file=None):
    """
    Call i-plan to request reserve orders
    :params order: e-ordering order
    :return: i-plan response
    """
    qs_order_lines = sap_migration_models.OrderLines.objects.filter(order=order)

    alt_mat_i_plan_dict, alt_mat_variant_obj_dict = {}, {}
    alt_mat_errors = []
    prepare_alternate_materials_list(alt_mat_i_plan_dict, alt_mat_variant_obj_dict, order, qs_order_lines,
                                     alt_mat_errors, is_product_grp_check_required=False)

    request_headers = []
    request_header, list_mat_os_and_mat_i_plan = po_request_header_atp_ctp(order, qs_order_lines,
                                                                           alt_mat_i_plan_dict,
                                                                           order_data_from_file=order_data_from_file)
    request_headers.append(request_header)

    request_id = 'DO' + str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE]
    request_params = {
        "DDQRequest": {
            "requestId": request_id,
            "sender": "e-ordering",
            "DDQRequestHeader": request_headers
        }
    }
    if not request_headers[0]["DDQRequestLine"]:
        return None
    log_val = {
        "orderid": order.id
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value,
                                           **log_val).request_mulesoft_post(
        IPlanEndPoint.I_PLAN_REQUEST.value,
        request_params
    )
    perform_rounding_on_iplan_qty_with_decimals(response)
    return response, alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors


def po_request_header_atp_ctp(
        order, order_lines, alt_mat_i_plan_dict, header_code=None, order_data_from_file=None
):
    request_lines = []
    consignment_location = get_contract_consignment_location_from_order(order)
    for order_line in order_lines:
        item_data_from_file = None
        for item in order_data_from_file['items']:
            if int(item["po_item_no"]) == int(order_line.item_no):
                item_data_from_file = item
                break
        alternate_products, product_code = get_product_and_ddq_alt_prod_of_order_line(alt_mat_i_plan_dict, order,
                                                                                      order_line, True,
                                                                                      item_data_from_file)

        parameter = change_parameter_follow_inquiry_method(order_line, order)
        inquiry_method = parameter.get("inquiry_method")
        use_inventory = parameter.get("use_inventory")
        use_consignment_inventory = parameter.get("use_consignment_inventory")
        use_projected_inventory = parameter.get("use_projected_inventory")
        use_production = parameter.get("use_production")
        order_split_logic = parameter.get("order_split_logic").upper()
        single_source = parameter.get("single_source")
        re_atp_required = parameter.get("re_atp_required")
        # I-plan unique customer code
        fmt_sold_to_code = (
                                   order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
                           ).lstrip("0") or None
        request_line = {
            "lineNumber": str(order_line.item_no),
            "locationCode": fmt_sold_to_code,
            "productCode": product_code,
            "consignmentOrder": False,
            "consignmentLocation": consignment_location,
            "requestDate": order_line.request_date and order_line.request_date.strftime('%Y-%m-%dT%H:%M:%SZ') or "",
            "inquiryMethod": inquiry_method,
            "quantity": str(order_line.quantity) if order_line.quantity else "0",
            "unit": "" if not order_line.sales_unit else (
                "ROL" if order_line.sales_unit == "ม้วน"
                else order_line.sales_unit
            ),
            "transportMethod": "Truck",
            "typeOfDelivery": IPlanTypeOfDelivery.EX_MILL.value,
            "useInventory": use_inventory,
            "useConsignmentInventory": use_consignment_inventory,
            "useProjectedInventory": use_projected_inventory,
            "useProduction": use_production,
            "orderSplitLogic": order_split_logic,
            "singleSourcing": single_source,
            "reATPRequired": re_atp_required,
            "requestType": "NEW",
        }
        if alternate_products and len(alternate_products):
            request_line["DDQAlternateProducts"] = alternate_products

        request_line["DDQSourcingCategories"] = [{"categoryCode": order.sales_organization.code},
                                                 {"categoryCode": order.sales_group.code}]
        request_lines.append(request_line)

    params = {
        "headerCode": header_code or str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE],
        "autoCreate": False,  # TRUE for dummy order FALSE for customer order
        "DDQRequestLine": sorted(request_lines, key=lambda x: float(x['lineNumber'])),

    }
    return params, alt_mat_i_plan_dict


def update_order_line_after_call_i_plan(dict_order_lines, i_plan_order_lines, order=None,
                                        alt_mat_i_plan_dict=None, alt_mat_variant_obj_dict=None,
                                        alt_mat_errors=None):
    """
    @param dict_order_lines: dict eOrdering order lines with item no as key
    @param i_plan_order_lines: Response line from i_plan
    @param order: order in db
    @param alt_mat_i_plan_dict
    @param alt_mat_variant_obj_dict
    @param alt_mat_errors
    alt_mat_i_plan_dict = {'14088_10': {'order_line_obj': '<OrderLines: OrderLines object (30774)>',
                                    'alt_mat_codes': ['Z02CA-125D0980117N', 'Z02CAA090M0980125N'],
                                    'alt_grade_gram_codes': ['Z02CA-125D'], 'is_es_15_required': False},
                       '14088_20': {'order_line_obj': '<OrderLines: OrderLines object (30775)>',
                                    'alt_mat_codes': ['Z02CA-125D0930117N'],
                                    'alt_grade_gram_codes': ['Z02CA-125D'], 'is_es_15_required': True}}
    alt_mat_variant_obj_dict = {'Z02CA-125D0980117N': '<MaterialVariantMaster: MaterialVariantMaster object (35966)>',
                            'Z02CAA090M0980125N': '<MaterialVariantMaster: MaterialVariantMaster object (5359)>',
                            'Z02CA-125D0930117N': '<MaterialVariantMaster: MaterialVariantMaster object (35931)>'}
    @return:
    """
    # Call SAP to save order
    e_ordering_order_lines = []
    new_order_lines = []
    order_id = order.id if order else ''
    if not dict_order_lines:
        return []

    max_item_no = max([int(item.item_no or item.eo_item_no) for _k, item in dict_order_lines.items()])

    e_ordering_order_lines_i_plan = []
    i_plan_order_lines = sorted(i_plan_order_lines, key=lambda x: x["lineNumber"])
    for i_plan_line in i_plan_order_lines:
        is_split_item = False
        line_id = i_plan_line.get("lineNumber").lstrip("0")
        line_id_original_item = line_id.split('.')[0]
        key = f"{order_id}_{line_id_original_item}"

        update_mat_own(i_plan_line, key, alt_mat_i_plan_dict)
        e_ordering_order_line = dict_order_lines.get(line_id)
        if not e_ordering_order_line:
            is_split_item = True
            max_item_no += 10
            e_ordering_order_line = deepcopy(dict_order_lines.get(str(floor(float(line_id)))))
            e_ordering_order_line.material_code = i_plan_line.get("productCode")
            e_ordering_order_line.pk = None
            e_ordering_order_line.iplan = None
            e_ordering_order_line.item_no = str(max_item_no)

        i_plan_on_hand_stock = i_plan_line.get("onHandStock")
        assigned_quantity = 0
        i_plan_operation = {}
        if i_plan_operations := (i_plan_line.get("DDQResponseOperation") or None):
            i_plan_operation = i_plan_operations[0]

        i_plan_confirm_quantity = i_plan_line.get("quantity", 0)
        i_plan_confirmed_date = i_plan_line.get("dispatchDate") if i_plan_line.get("dispatchDate") else None
        i_plan_plant = i_plan_line.get("warehouseCode", None)
        block = i_plan_operation.get("blockCode", None)
        run = i_plan_operation.get("runCode", None)
        item_status = i_plan_line.get("status", None)
        original_date = i_plan_line.get("dispatchDate") if i_plan_line.get("dispatchDate") else None
        paper_machine = i_plan_operation.get("workCentreCode", None)
        order_type = i_plan_line.get("orderType", None)
        plant = i_plan_line.get("warehouseCode", None)
        item_no = i_plan_line.get("lineNumber", None)
        on_hand_stock = i_plan_line.get("onHandStock", None)
        # Update order line i-plan table
        e_ordering_order_line_i_plan = e_ordering_order_line.iplan
        atp_ctp_status = None
        if i_plan_on_hand_stock is True and not i_plan_operations:
            atp_ctp_status = AtpCtpStatus.ATP.value
        elif i_plan_on_hand_stock is False and not i_plan_operations:
            atp_ctp_status = AtpCtpStatus.ATP_FUTURE.value
        elif i_plan_on_hand_stock is False and i_plan_operations:
            atp_ctp_status = AtpCtpStatus.CTP.value

        atp_ctp = handle_atp_ctp(i_plan_operations, i_plan_on_hand_stock)

        parameter = change_parameter_follow_inquiry_method(e_ordering_order_line, order)
        if i_plan_on_hand_stock and order_type != AtpCtpStatus.CTP.value:
            assigned_quantity = i_plan_line.get("quantity", 0)
        if not e_ordering_order_line_i_plan:
            e_ordering_order_line_i_plan = (
                sap_migration_models.OrderLineIPlan.objects.create(
                    atp_ctp=atp_ctp_status,
                    iplant_confirm_quantity=i_plan_confirm_quantity,
                )
            )
            e_ordering_order_line.iplan = e_ordering_order_line_i_plan

        e_ordering_order_line_i_plan.atp_ctp = atp_ctp
        e_ordering_order_line_i_plan.iplant_confirm_quantity = i_plan_confirm_quantity
        e_ordering_order_line_i_plan.atp_ctp_detail = atp_ctp_status
        e_ordering_order_line_i_plan.block = block
        e_ordering_order_line_i_plan.run = run
        e_ordering_order_line_i_plan.item_status = item_status
        e_ordering_order_line_i_plan.original_date = original_date
        e_ordering_order_line_i_plan.partial_delivery = "false"
        e_ordering_order_line_i_plan.paper_machine = paper_machine
        e_ordering_order_line_i_plan.inquiry_method_code = parameter.get("inquiry_method")
        e_ordering_order_line_i_plan.transportation_method = "Truck"
        e_ordering_order_line_i_plan.type_of_delivery = IPlanTypeOfDelivery.EX_MILL.value
        e_ordering_order_line_i_plan.fix_source_assignment = e_ordering_order_line.plant or ""
        e_ordering_order_line_i_plan.split_order_item = parameter.get("order_split_logic")
        e_ordering_order_line_i_plan.iplant_confirm_date = i_plan_confirmed_date
        e_ordering_order_line_i_plan.consignment = "false"
        e_ordering_order_line_i_plan.use_inventory = parameter.get("use_inventory")
        e_ordering_order_line_i_plan.use_consignment_inventory = parameter.get("use_consignment_inventory")
        e_ordering_order_line_i_plan.use_projected_inventory = parameter.get("use_projected_inventory")
        e_ordering_order_line_i_plan.use_production = parameter.get("use_production")
        e_ordering_order_line_i_plan.single_source = parameter.get("single_source")
        e_ordering_order_line_i_plan.re_atp_required = parameter.get("re_atp_required")
        e_ordering_order_line_i_plan.request_type = "NEW"
        e_ordering_order_line_i_plan.order_type = order_type
        e_ordering_order_line_i_plan.plant = plant
        e_ordering_order_line_i_plan.item_no = item_no
        e_ordering_order_line_i_plan.on_hand_stock = on_hand_stock

        e_ordering_order_lines_i_plan.append(e_ordering_order_line_i_plan)

        # Update order line table
        e_ordering_order_line.material_code = i_plan_line.get("productCode")
        e_ordering_order_line.i_plan_on_hand_stock = i_plan_on_hand_stock
        e_ordering_order_line.i_plan_operations = i_plan_operations
        e_ordering_order_line.confirmed_date = i_plan_confirmed_date
        e_ordering_order_line.quantity = i_plan_line.get("quantity")
        e_ordering_order_line.plant = i_plan_plant
        e_ordering_order_line.original_item_no = line_id
        e_ordering_order_line.return_status = item_status
        e_ordering_order_line.assigned_quantity = assigned_quantity
        e_ordering_order_line.request_date = i_plan_confirmed_date or e_ordering_order_line.request_date
        if is_split_item:
            new_order_lines.append(e_ordering_order_line)
        else:
            e_ordering_order_lines.append(e_ordering_order_line)

    derive_and_compute_alt_mat_info(e_ordering_order_lines, alt_mat_variant_obj_dict, alt_mat_i_plan_dict,
                                    alt_mat_errors)
    # TODO: IPLAN comparision & error
    sap_migration_models.OrderLines.objects.bulk_update(
        e_ordering_order_lines,
        fields=[
            "material_code",
            "material_id",
            "material_variant_id",
            "contract_material_id",
            "i_plan_on_hand_stock",
            "i_plan_operations",
            "iplan",
            "plant",
            "confirmed_date",
            "quantity",
            "original_item_no",
            "return_status",
            "assigned_quantity",
            "request_date"
        ],
    )
    created_order_lines = []
    if len(new_order_lines) > 0:
        created_order_lines = sap_migration_models.OrderLines.objects.bulk_create(
            new_order_lines
        )
        derive_and_compute_alt_mat_info(created_order_lines, alt_mat_variant_obj_dict, alt_mat_i_plan_dict,
                                        alt_mat_errors,
                                        True)
        sap_migration_models.OrderLines.objects.bulk_update(
            created_order_lines,
            fields=[
                "material_code",
                "material_id",
                "material_variant_id",
                "contract_material_id",
                "ref_doc_it",
            ],
        )
    log_alt_mat_errors(alt_mat_errors)
    if len(e_ordering_order_lines_i_plan):
        sap_migration_models.OrderLineIPlan.objects.bulk_update(
            e_ordering_order_lines_i_plan,
            fields=[
                "atp_ctp",
                "iplant_confirm_quantity",
                "atp_ctp_detail",
                "block",
                "run",
                "item_status",
                "original_date",
                "partial_delivery",
                "paper_machine",
                "inquiry_method_code",
                "transportation_method",
                "type_of_delivery",
                "fix_source_assignment",
                "split_order_item",
                "consignment",
                "use_inventory",
                "use_consignment_inventory",
                "use_projected_inventory",
                "single_source",
                "use_production",
                "re_atp_required",
                "request_type",
                "order_type",
                "iplant_confirm_date",
                "plant",
                "on_hand_stock",
                "item_no",
            ],
        )

    return created_order_lines + e_ordering_order_lines


def filter_no_outsource_order_lines(order_lines=[], order=None):
    """Filter out outsource order lines
    Args:
        order_lines (list, optional): order lines. Defaults to [].
    Returns:
        list: no outsource order lines
    """
    os_plant_list = MaterialType.MATERIAL_OS_PLANT.value

    def _filter(line):
        item_cat_eo = line.item_cat_eo or ""
        material_plant = line.contract_material and line.contract_material.plant or ""
        plant = line.plant or ""
        if plant in os_plant_list and (material_plant in os_plant_list):
            return False

        if (
                item_cat_eo == ItemCat.ZKC0.value or
                (plant in os_plant_list)
        ):
            return False
        return True

    filter_lines = []
    material_os_lines = []
    for line in order_lines:
        if _filter(line):
            filter_lines.append(line)
        else:
            material_os_lines.append(line)

    if order and len(material_os_lines) > 0:
        # in EOUpload, etd is string (original)
        _confirmed_date = order.etd if order.etd else None
        confirmed_date = date_to_sap_date(_confirmed_date, date_time_format)
        for line in material_os_lines:
            line.confirmed_date = confirmed_date
        sap_migration_models.OrderLines.objects.bulk_update(
            material_os_lines,
            ["confirmed_date"]
        )
    return filter_lines


def update_confirmed_date_for_no_outsource_order_lines(qs_order_lines, order):
    if order and len(qs_order_lines) > 0:
        order_lines = list(filter(lambda x: (x.plant in MaterialType.MATERIAL_OS_PLANT.value), qs_order_lines))

        for line in order_lines:
            line.confirmed_date = line.request_date
        sap_migration_models.OrderLines.objects.bulk_update(
            order_lines,
            ["confirmed_date"]
        )


@transaction.atomic
def request_i_plan_delete_cancel_order(order_lines, manager):
    try:
        params = prepare_param_i_plan_request_delete_cancel(order_lines)
        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value).request_mulesoft_post(
            IPlanEndpoint.REQUEST_URL.value,
            params
        )
        return response
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def prepare_param_i_plan_request_delete_cancel(order_lines):
    ddq_request_header = []
    for so_no, lines in order_lines.items():
        request_line = []
        for item in lines:
            request_line.append(
                {
                    "lineNumber": item.item_no,
                    "locationCode": item.order.sold_to.sold_to_code,
                    "productCode": get_product_code(item),
                    "requestDate": item.request_date.strftime("%Y-%m-%dT00:00:00.000Z") if item.request_date else "",
                    "inquiryMethod": IPlanInquiryMethodCode.JITCP.value,
                    "quantity": str(item.quantity),
                    "unit": "ROL",
                    "transportMethod": "Truck",
                    "typeOfDelivery": "E",
                    "singleSourcing": False,
                    "requestType": "DELETE"
                }
            )
        request_header = {
            "headerCode": so_no.lstrip("0"),
            "autoCreate": False,
            "DDQRequestLine": request_line
        }
        ddq_request_header.append(request_header)
    param = {
        "DDQRequest": {
            "requestId": 'DO' + str(uuid.uuid1().int)[:LEN_OF_HEADER_CODE],
            "sender": "e-ordering",
            "DDQRequestHeader": ddq_request_header
        }
    }
    return param


def handle_sap_response(sap_response):
    error_msg_order_header = load_error_message()
    sap_order_messages = []
    sap_item_messages = []
    sap_success = True
    order_header_msg = []
    if sap_response.get("data"):
        # Get message for order
        for data in sap_response.get("data"):
            item_id = data.get("id", "")
            item_no = data.get("itemNo").lstrip("0") if data.get("itemNo") else None
            if data.get("type", "").lower() == SapType.ERROR.value.lower():
                sap_success = False
                validate_order_msg(data, error_msg_order_header, order_header_msg)
                if item_no and not re.match("^V\\d+$", item_id):
                    sap_item_messages.append(
                        {
                            "item_no": item_no,
                            "error_code": f"{data.get('id', '')}{data.get('number', '')}",
                            "error_message": data.get("message")
                        }
                    )
                else:
                    sap_order_messages.append(
                        {
                            "id": item_id,
                            "number": data.get("number"),
                            "so_no": sap_response.get("salesdocument"),
                            "message": data.get("message")
                        }
                    )
    return sap_order_messages, sap_item_messages, sap_success, order_header_msg


def handle_atp_ctp(i_plan_operations, i_plan_on_hand_stock):
    if not i_plan_operations:
        return AtpCtpStatus.ATP.value
    if not i_plan_on_hand_stock:
        return AtpCtpStatus.CTP.value
    return ""


def get_contract_consignment_location_from_order(order):
    contract = getattr(order, "contract", None)
    sales_group = getattr(contract, "sales_group", None)
    return getattr(sales_group, "code", "")


def get_contract_no_from_order(order):
    contract = getattr(order, "contract", None)
    return getattr(contract, "code", "")


def get_ship_to_country_from_order(order):
    contract = getattr(order, "contract", None)
    return getattr(contract, "ship_to_country", "")


def get_sold_to_name_es14_partneraddress_from_order(order):
    contract = getattr(order, "contract", None)
    sold_to_code = getattr(contract, "sold_to_code", "")
    return get_name_from_sold_to_partner_address_master(sold_to_code)


def get_shipping_remark_from_order(order):
    contract = getattr(order, "contract", None)
    return getattr(contract, "shipping_mark", None)


def send_mail_customer_fail_alternate(order, manager, alt_mat_errors: list = None,
                                      is_change_add_new_flow: bool = False):
    alternate_fails = None
    if is_change_add_new_flow and not alt_mat_errors:
        return
    if alt_mat_errors:
        alternate_fails = sorted(alt_mat_errors, key=lambda x: x.order_line.item_no)

    if not alternate_fails and order.id:
        alternate_fails = AlternatedMaterial.objects.filter(
            order=order,
            error_type__in=[
                AlternatedMaterialLogChangeError.NO_MATERIAL_CONTRACT.value,
                AlternatedMaterialLogChangeError.NOT_FOUND_SAME_PRODUCT_GROUP.value,
                AlternatedMaterialLogChangeError.NOT_FOUND_MATERIAL_DETERMINATION.value,
                AlternatedMaterialLogChangeError.NOT_ENOUGH_QTY_IN_CONTRACT.value]). \
            order_by('order_line')

    if not alternate_fails:
        return

    data = [
        {
            "item_no": line.order_line.item_no,
            "material_description": get_mat_desc_from_master_for_alt_mat_old(line.old_product),
            "error": line.error_type
        }
        for line in alternate_fails
    ]

    po_number = get_po_number_from_order(order)
    sold_to_code = order.contract.sold_to.sold_to_code
    [_, *_ship_to_list] = order.ship_to and order.ship_to.split(" - ") or []
    sold_to_name = get_name1_from_sold_to(sold_to_code)

    ship_to = order.ship_to and order.ship_to.split("\n")
    product_group = order.product_group if order else ""
    sale_org = order.sales_organization.code if order.sales_organization else ""
    sale_orgs = []
    if sale_org:
        if sale_org[0] == "0":
            sale_orgs.append(sale_org.lstrip("0"))
        sale_orgs.append(sale_org)

    internal_emails = get_internal_emails_by_config(
        EmailConfigurationFeatureChoices.ALTERNATED_MATERIAL, sale_orgs, product_group.split(",")
    )
    template_data = {
        "order_no": order.so_no,
        "po_no": po_number,
        "sold_to_code_name": sold_to_name,
        "ship_to_code_name": ship_to and ship_to[0] or "",
        "contract_no": get_contract_no_name_from_order(order),
        "request_delivery_date": order.request_date,
        "total_no_of_items": len(alternate_fails),
        "item_errors": data
    }
    manager.scgp_po_upload_send_mail_when_call_api_fail(
        "scg.email",
        recipient_list=internal_emails,
        subject=f"[Error Change Alternated Material] [{order.so_no}] [{po_number}] [{sold_to_name}]",
        template="alternative_outsource_failed_change.html",
        template_data=template_data,
        cc_list=[],
    )


def has_special_plant(order_line):
    # SEO-3361
    if order_line.plant in ["754F", "7531", "7533"]:
        return True
    return False


def update_order_line_after_call_es_17(need_invoke_iplan, order, response):
    order_line_updates = []
    order_schedule_out = response.get("orderSchedulesOut")
    order_header_out = response.get("orderHeaderOut")
    order_lines = sap_migration_models.OrderLines.objects.filter(order=order).distinct("item_no").in_bulk(
        field_name="item_no")
    order_items_out = response.get("orderItemsOut")
    # Create a dictionary to store the fields to update for each item_no
    fields_to_update_dict = {}
    if order_items_out:
        for item in order_items_out:
            order_line = order_lines.get(item["itemNo"].lstrip("0"))
            if order_line:
                fields_to_update = {
                    'weight_unit_ton': item.get("weightUnitTon"),
                    'weight_unit': item.get("weightUnit"),
                    'net_weight_ton': item.get("netWeightTon"),
                    'gross_weight_ton': item.get("grossWeightTon")
                }

                # Bulk update the fields for the order_line object
                fields_to_update_dict[order_line.item_no] = fields_to_update

    if order_schedule_out:
        for item in order_schedule_out:
            order_line = order_lines.get(item["itemNo"].lstrip("0"))
            if order_line:
                # SEO-4710 new logic to update assigned quantity
                i_plan_response = order_line.iplan
                if not i_plan_response.on_hand_stock:
                    order_line.assigned_quantity = 0
                if i_plan_response.on_hand_stock and i_plan_response.order_type != "CTP":
                    order_line.assigned_quantity = item.get("confirmQty", None)
                order_line.sap_confirm_qty = item.get("confirmQty", None)
                fields_to_update = fields_to_update_dict.get(order_line.item_no, {})
                order_line.weight_unit_ton = fields_to_update.get('weight_unit_ton')
                order_line.weight_unit = fields_to_update.get('weight_unit')
                order_line.net_weight_ton = fields_to_update.get('net_weight_ton')
                order_line.gross_weight_ton = fields_to_update.get('gross_weight_ton')
                if need_invoke_iplan:
                    compute_confirm_and_request_date(order_line, order_line_updates, order.type)
                else:
                    compute_confirm_and_request_date_iplan_skipped(order_line, order_line_updates, order.type)
        if OrderType.CUSTOMER.value == order.type:
            sap_migration_models.OrderLines.objects.bulk_update(order_line_updates,
                                                                ["sap_confirm_qty", "assigned_quantity", "request_date",
                                                                 "confirmed_date", "remark", "weight_unit_ton",
                                                                 "weight_unit", "net_weight_ton", "gross_weight_ton",
                                                                 "class_mark"])
        else:
            sap_migration_models.OrderLines.objects.bulk_update(order_line_updates,
                                                                ["sap_confirm_qty", "assigned_quantity", "request_date",
                                                                 "confirmed_date", "weight_unit_ton", "weight_unit",
                                                                 "net_weight_ton", "gross_weight_ton"])

    update_order_required = False
    if order_header_out:
        order.total_price = order_header_out.get("orderAmtBeforeVat", order.total_price)
        order.total_price_inc_tax = order_header_out.get("orderAmtAfterVat", order.total_price_inc_tax)
        order.tax_amount = order_header_out.get("orderAmtVat", order.tax_amount)
        update_order_required = True

    if not order.product_group:
        update_order_required = True
        order.product_group = get_product_group_from_es_17(response)
        logging.info(
            f"Using ES17 response Order {order.so_no} product group updated to {order.product_group}")
    if update_order_required:
        order.save()
    update_log_mat_os_quantity_details(order, response)


def get_partner_emails_from_es17_response(sap_response):
    order_partners_list = sap_response.get("orderPartners", [])
    partner_no_list = [partner_data["partnerNo"] for partner_data in order_partners_list
                       if partner_data.get("partnerRole") == "VE"]
    partner_emails = sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(partner_code__in=partner_no_list,
                                                                                      email__isnull=False).values_list(
        'email', flat=True)
    return list(partner_emails)


def handle_header_code(status, sap_order_number, response_header):
    if status == IPLanConfirmStatus.COMMIT.value and sap_order_number:
        header_code = sap_order_number.lstrip("0")
    else:
        header_code = response_header.get("headerCode").lstrip("0")
    return header_code


def handle_original_header_code(response_header, require_attention, header_code):
    return response_header.get("headerCode").lstrip("0") if not require_attention else header_code


def handle_ddq_order_information_type(require_attention, order_information_type):
    return [] if require_attention else order_information_type


def handle_on_hand_quantity_confirmed(line, dict_order_schedules_out, order_line):
    on_hand_stock = line.get("onHandStock", False)
    on_hand_quantity_confirmed = 0
    if on_hand_stock:
        on_hand_quantity_confirmed = dict_order_schedules_out.get(str(order_line.item_no), 0)
    return on_hand_quantity_confirmed


def handle_value(contract_no):
    return contract_no or ""


def handle_order_information_type(order, status):
    order_information_type = []
    if order.type == OrderType.EXPORT.value and status == IPLanConfirmStatus.COMMIT.value:
        contract_no = get_contract_no_from_order(order)
        country = get_ship_to_country_from_order(order)
        sold_to_name = get_sold_to_name_es14_partneraddress_from_order(
            order
        )
        shipping_remark = get_shipping_remark_from_order(order)
        order_information_item = []
        if order.eo_upload_log:
            shipping_remark = order.shipping_mark

        if shipping_remark:
            order_information_item.append({
                "valueType": "ShippingMarks",
                "value": shipping_remark,
            })
        value = handle_value(contract_no)
        if value:
            order_information_item.append({
                "valueType": "ProformaInvoice",
                "value": value,
            })
        if sold_to_name:
            order_information_item.append({"valueType": "SoldTo", "value": sold_to_name})

        if country:
            order_information_item.append({"valueType": "Country", "value": country})

        order_information_type.append(
            {
                "type": "CustomInfo",
                "DDQOrderInformationItem": order_information_item
            }
        )
    return order_information_type
