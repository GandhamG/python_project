import logging

import pytz
from django.template import Context, Template
from django.utils import timezone

from scgp_user_management.models import EmailConfigurationFeatureChoices

logger = logging.getLogger(__name__)
from scg_checkout.graphql.helper import (
    get_internal_emails_by_config,
    get_name_from_sold_to_partner_address_master,
)


def eo_upload_send_email_when_call_api_fail(
    manager,
    order,
    action_type,
    call_type,
    error_response,
    request_type,
):
    """
    When call api iplan/sap, If system raise exception or return error response, \n
    then we need to call this function to send email notification for emails which have configured

    Args:
        manager: plugins
        order: order
        action_type: "Create" or "Update"
        call_type: "IPlan" or "SAP"
        error_response: exception or response from iplan/sap
        request_type: "iplan_request","iplan_confirm","iplan_update","sap_save","sap_update"
                        It used for get error info from response
    """
    try:
        error_messages = []
        # case error response is exception ex ConnectionError,...
        if isinstance(error_response, Exception):
            error_messages.append("IPlan/SAP - Process Timeout")
        else:
            if error := error_response.get("error"):
                # case iplan return 500
                status = error_response.get("status")
                error_messages.append(f"{call_type} {status} {error}")
            else:
                # case iplan/sap return failure for some item
                if request_type == "iplan_request":
                    lines = (
                        error_response.get("DDQResponse", {})
                        .get("DDQResponseHeader", [{}])[0]
                        .get("DDQResponseLine")
                    )
                    for line in lines:
                        if line.get("returnStatus", "").lower() == "failure":
                            error_messages.append(
                                f"{line['lineNumber']} {call_type} {line['returnCode']} {line['returnCodeDescription']}"
                            )
                elif request_type in ["sap_update", "sap_save"]:
                    lines = error_response.get("return", []) or error_response.get(
                        "data", []
                    )
                    for line in lines:
                        if line.get("type", "").lower() == "fail":
                            item_no = (
                                line.get("itemNo").lstrip("0")
                                if line.get("itemNo")
                                else ""
                            )
                            error_messages.append(
                                f"{item_no} {call_type} {line.get('number')} {line.get('message')}"
                            )
                elif request_type == "iplan_update":
                    lines = error_response.get("OrderUpdateResponse", {}).get(
                        "OrderUpdateResponseLine", []
                    )
                    for line in lines:
                        if line.get("returnStatus", "").lower() != "success":
                            error_messages.append(
                                f"{line.get('lineCode')} {call_type} {line.get('returnCode')} {line.get('returnCodeDescription')}"
                            )

        sold_to = order.sold_to
        customer_name = _get_sold_to_name_from_order(order)
        context = {
            "call_type_iplan": "IPlan",
            "call_type_sap": "SAP",
            "action_type": action_type,
            "pi_no": order.contract.code if order.contract else "",
            "customer_name": customer_name,
            "lot_no": order.lot_no or "",
            "processing_datetime_str": order.eo_upload_log.created_at.astimezone(
                pytz.timezone("Asia/Bangkok")
            ).strftime("%d/%m/%Y %H:%M:%S")
            if order.eo_upload_log
            else timezone.now()
            .astimezone(pytz.timezone("Asia/Bangkok"))
            .strftime("%d/%m/%Y %H:%M:%S"),
            "eo_no": (order.eo_no if action_type == "Update" else None) or "",
            "sold_to_code": sold_to.sold_to_code if sold_to else "",
            "error_messages": error_messages,
        }

        subject = Template(
            "[{{action_type}} EO] Failed Pi{{pi_no}}_{{customer_name|safe}}_[{{lot_no}}]"
        ).render(Context(context))
        sale_org = order.sales_organization.code if order.sales_organization else None
        order_prod_group = order.product_group if order else None
        logging.info(
            "[EO Upload] eo_upload_send_email_when_call_api_fail: email from config will be retrieved"
            " for EO NO:{order.eo_no} with product group:{order_prod_group}, sale_org:{sale_org}"
        )
        recipient_list = get_internal_emails_by_config(
            EmailConfigurationFeatureChoices.EO_UPLOAD,
            sale_org,
            order_prod_group,
        )
        if order.created_by:
            recipient_list.append(order.created_by.email)
        manager.scgp_po_upload_send_mail_when_call_api_fail(
            "scg.email",
            recipient_list=recipient_list,
            subject=subject,
            template="eo_upload_fail.html",
            template_data=context,
            cc_list=[],
        )
    except Exception as e:
        logger.error(str(e))


def _get_sold_to_name_from_order(order):
    contract = getattr(order, "contract", None)
    sold_to_code = getattr(contract, "sold_to_code", "")
    return get_name_from_sold_to_partner_address_master(sold_to_code)
