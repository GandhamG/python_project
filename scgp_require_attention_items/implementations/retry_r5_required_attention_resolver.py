import ast
import logging
import uuid

from django.conf import settings
from django.utils import timezone

from common.enum import MulesoftServiceType
from common.helpers import parse_json_if_possible
from common.models import MulesoftLog
from common.mulesoft_api import MulesoftApiRequest
from sap_migration.models import OrderLines
from scg_checkout.graphql.helper import get_iplan_error_messages
from scgp_export.graphql.enums import SapEnpoint
from scgp_po_upload.graphql.enums import IPlanAcknowledge
from scgp_require_attention_items.graphql.enums import IPlanEndpoint

RETRY_COUNT = settings.RETRY_COUNT
BATCH_SIZE = settings.BATCH_SIZE
FEATURE_SPLIT_ITEM = "SplitItem"


def cancel_retry_and_reset_required_atttn(api_log):
    # identify order line ids against which R5 flag will be reset
    order_lines = OrderLines.objects.filter(order_id=api_log.orderid).all()
    for order_line in order_lines:
        tmp = order_line.attention_type.split(", ")
        if "R5" in tmp:
            tmp.remove("R5")
        order_line.attention_type = ", ".join(tmp)
        order_line.save()

    # update retry count to 0 in mulesoft api log table
    api_log.retry = False
    api_log.save()
    logging.info(f"Successfully reset retry as false for api log entry : {api_log}")
    logging.info(
        f"Successfully reset retry as false for api log entry : {api_log.orderid}"
    )


def increment_retry_count(api_log):
    logging.info(f"Incrementing logging count for api log : {api_log}")
    logging.info(f"Incrementing logging count for api log : {api_log.orderid}")
    api_log.retry_count = api_log.retry_count + 1
    api_log.updated_at = timezone.now()
    api_log.save()


def retry_iplan_update_order_split(api_log):
    data = __deserialize_data(api_log.request)

    order_line_split_request = data.get("OrderLineSplitRequest", {})
    logging.info("OrderLineSplitRequest data: %s", order_line_split_request)

    split_elements = order_line_split_request.get("OrderLineSplitPart", [])
    if not split_elements:
        logging.warning(
            f"[R5-Retry][YT-65838 split order] skipping call to Yt-65838 as split_items is empty:{split_elements}"
        )
        return
    order_line_split_request["updateId"] = str(uuid.uuid1().int)
    split_items_request = {"OrderLineSplitRequest": order_line_split_request}
    try:
        logging.info(
            f"[R5-Retry][YT-65838 split order] split item Yt-65838 request : {split_items_request}"
        )
        iplan_response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value
        ).request_mulesoft_post(
            IPlanEndpoint.I_PLAN_SPLIT_ORDER.value,
            data=split_items_request,
            log_request=False,
            encode=True,
        )
        logging.info(
            f"[R5-Retry][YT-65838 split order] split item Yt-65838 response : {iplan_response}"
        )
        i_plan_error_messages = get_iplan_split_error_messages(iplan_response)

        if i_plan_error_messages:
            logging.error(
                "[R5-Retry][YT-65838 split order]  Failed to retry API request for Yt-65838."
            )
            increment_retry_count(api_log)
        else:
            cancel_retry_and_reset_required_atttn(api_log)

    except Exception as e:
        logging.exception(
            f"[R5-Retry][YT-65838 split order]  Exception while split: {e}"
        )
        increment_retry_count(api_log)


def get_iplan_split_error_messages(iplan_response):
    i_plan_response_lines = iplan_response.get("OrderLineSplitResponse", None)
    response_failure = False
    if (
        i_plan_response_lines
        and i_plan_response_lines.get("returnStatus").lower()
        == IPlanAcknowledge.FAILURE.value.lower()
    ):
        response_failure = True
    return response_failure


def retry_iplan_confirm(api_log):
    try:
        request = populate_new_request_id(api_log, "requestId")
        iplan_response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value
        ).request_mulesoft_post(
            IPlanEndpoint.IPLAN_CONFIRM_URL.value,
            data=request,
            log_request=False,
            encode=True,
        )
        logging.info(iplan_response)
        _, i_plan_error_messages = get_iplan_error_messages(iplan_response)
        if i_plan_error_messages:
            logging.error(
                f"iplan_confirm retry api failed because of : {i_plan_error_messages}"
            )
            increment_retry_count(api_log)
            return
        cancel_retry_and_reset_required_atttn(api_log)
    except Exception:
        logging.exception(
            "Some error has occurred while invoking call_iplan_confirm_update_order api"
        )
        increment_retry_count(api_log)


def retry_es_21(api_log):
    """
    This method invokes ES21 api back as the item being marked for R5 incase of yt65838
    """
    request = populate_new_request_id(api_log, "piMessageId")
    try:
        # invoke es21 api manually using the payload available in mulesoft api log table
        response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.SAP.value
        ).request_mulesoft_post(
            SapEnpoint.ES_21.value,
            data=request,
            log_request=False,
            encode=True,
        )
        return_item_message = response.get("return", [])
        return_messages = {"fail": [], "success": [], "warning": []}
        for message_obj in return_item_message:
            __type = message_obj.get("type", None)
            if __type:
                return_messages[__type].append(message_obj)
        error_messages = return_messages.get("fail", [])
        if error_messages:
            logging.error("ES21 retry api failed because of ", error_messages)
            increment_retry_count(api_log)
            return
        cancel_retry_and_reset_required_atttn(api_log)
    except Exception:
        logging.exception(
            "Some error has occurred while invoking call_es_21_update_order api "
        )
        increment_retry_count(api_log)


def populate_new_request_id(api_log, param_name):
    data = __deserialize_data(api_log.request)
    request = data
    new_uuid = str(uuid.uuid1().int)
    if param_name == "piMessageId":
        request[param_name] = new_uuid
    elif param_name == "requestId":
        if request.get("DDQConfirm"):
            request["DDQConfirm"][param_name] = new_uuid
        elif request.get("DDQRequest"):
            request["DDQRequest"][param_name] = new_uuid

    return request


def __deserialize_data(str_json_data):
    json_data = parse_json_if_possible(str_json_data)
    if not isinstance(json_data, str):
        return json_data
    return ast.literal_eval(str_json_data)


def retry_iplan_update_order(api_log):
    """
    This will call iplan YT-65217 with the pay load available in mulesoft log table
    :param api_log:
    :return:
    """
    try:
        request = populate_new_request_id(api_log, "requestId")
        iplan_response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.IPLAN.value
        ).request_mulesoft_post(
            IPlanEndpoint.I_PLAN_UPDATE_ORDER.value,
            data=request,
            log_request=False,
            encode=True,
        )
        logging.info(iplan_response)
        _, i_plan_error_messages = get_iplan_error_messages(iplan_response)
        if i_plan_error_messages:
            logging.error(
                f"I_PLAN_UPDATE_ORDER retry api failed because of : {i_plan_error_messages}"
            )
            increment_retry_count(api_log)
            return
        cancel_retry_and_reset_required_atttn(api_log)
    except Exception:
        logging.exception(
            "Some error has occurred while invoking call_I_PLAN_UPDATE_ORDER_update_order api"
        )
        increment_retry_count(api_log)


def retry_r5_required_attention_resolver():
    try:
        logging.info("Going to start retrying process!")

        log_count = MulesoftLog.objects.filter(
            retry=True, retry_count__lte=RETRY_COUNT
        ).count()

        for i in range(0, log_count, BATCH_SIZE):
            api_log_list_batch = MulesoftLog.objects.filter(
                retry=True, retry_count__lte=RETRY_COUNT
            ).order_by("updated_at")[i : i + BATCH_SIZE]

            for api_log in api_log_list_batch:

                if SapEnpoint.ES_21.value in api_log.url:
                    retry_es_21(api_log)
                elif IPlanEndpoint.IPLAN_CONFIRM_URL.value in api_log.url:
                    retry_iplan_confirm(api_log)
                elif IPlanEndpoint.I_PLAN_UPDATE_ORDER.value in api_log.url:
                    retry_iplan_update_order(api_log)
                elif IPlanEndpoint.I_PLAN_SPLIT.value in api_log.url:
                    retry_iplan_update_order_split(api_log)
    except Exception as e:
        logging.exception("An error occurred while processing: %s", str(e))
