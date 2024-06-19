import json
import logging
import os
from http import HTTPStatus

import requests
from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone

import saleor.account.models
from common.helpers import save_mulesoft_api_log_entry
from saleor.plugins.manager import get_plugins_manager
from sap_migration.models import Order, OrderExtension, OrderLines
from scg_checkout.graphql.enums import IPlanOrderStatus, ScgOrderStatus
from scg_checkout.graphql.helper import get_date_time_now_timezone_asia
from scg_checkout.graphql.implementations.iplan import (
    call_i_plan_create_order,
    call_i_plan_update_order_eo_upload,
)
from scgp_eo_upload.constants import EO_UPLOAD_STATE_ERROR, EO_UPLOAD_STATE_IN_PROGRESS
from scgp_eo_upload.implementations.eo_upload import (
    eo_log_state,
    get_data_path,
    validate_product_group_for_export,
)
from scgp_eo_upload.models import EoUploadLog
from scgp_eo_upload.tasks import task_sync_eo_upload
from scgp_export.implementations.mapping_data_object import MappingDataToObject
from scgp_export.sns_helper.sns_connect import setup_client_sns
from scgp_po_upload.graphql.helpers import html_to_pdf

from .. import settings
from .auth import get_token_from_request
from .jwt import get_user_from_access_token
from .jwt_manager import get_jwt_manager


def home(request):
    storefront_url = os.environ.get("STOREFRONT_URL", "")
    dashboard_url = os.environ.get("DASHBOARD_URL", "")
    return TemplateResponse(
        request,
        "home/index.html",
        {"storefront_url": storefront_url, "dashboard_url": dashboard_url},
    )


def jwks(request):
    return JsonResponse(get_jwt_manager().get_jwks())


def validate_with_ctp_atp(order, order_line, request, order_type):
    return True


def call_sap_api_save(request, order, order_line):
    manager = request.plugins
    response = call_i_plan_create_order(order, manager, call_type="eo_upload")

    template_data = {"order_number": order, "status": ""}
    order_line_data = {"order_line": order_line}
    created_by = order.created_by
    template_pdf_data = {
        "order": order.eo_no,
        "status": "success update SAP",
        "order_line": order_line_data,
        "created_by": f"{created_by.first_name} {created_by.last_name}",
        "file_name_pdf": "Example",
        "print_date_time": get_date_time_now_timezone_asia(),
    }
    pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")

    if not response.get("success"):
        template_data["status"] = "rejected save SAP"
    if response.get("success") == True:
        template_data["status"] = "confirmed save SAP"

    # Set order status
    order.status = response.get("order_status")
    order.status_thai = IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order.status)
    order.save()

    manager.scgp_po_upload_send_mail(
        "scg.email",
        "ducdm1@smartosc.com",
        template_data,
        "TCP Order submitted : 0000002141 - บจก.โอเรียนท์คอนเทนเนอร์",
        "index.html",
        pdf,
        None,
    )
    return response.get("success")


def call_sap_api_update(request, order, order_line):
    manager = request.plugins

    order_status, response = call_i_plan_update_order_eo_upload(order, manager)

    template_data = {"order_number": order, "status": ""}
    order_line_data = {"order_line": order_line}
    created_by = order.created_by
    template_pdf_data = {
        "order": order.eo_no,
        "status": "success update SAP",
        "order_line": order_line_data,
        "created_by": f"{created_by.first_name} {created_by.last_name}",
        "file_name_pdf": "Example",
        "print_date_time": get_date_time_now_timezone_asia(),
    }
    pdf = html_to_pdf(template_pdf_data, "header.html", "content.html")

    if order_status != ScgOrderStatus.RECEIVED_ORDER.value:
        template_data["status"] = "rejected save SAP"
    if order_status == ScgOrderStatus.RECEIVED_ORDER.value:
        template_data["status"] = "confirmed save SAP"
    # Set order status
    order.status = order_status
    order.status_thai = IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order.status)
    order.save()

    manager.scgp_po_upload_send_mail(
        "scg.email",
        "ducdm1@smartosc.com",
        template_data,
        "TCP Order submitted : 0000002141 - บจก.โอเรียนท์คอนเทนเนอร์",
        "index.html",
        pdf,
        None,
    )
    return order_status == ScgOrderStatus.RECEIVED_ORDER.value


def call_iplan_and_sap_eo_data(request, order_type, order_object, order_line_object):
    if validate_with_ctp_atp(order_object, order_line_object, request, order_type):
        order_object.status_sap = "confirmed ctp/atp"

        order_type = order_type.lower()
        if order_type == "new":
            if call_sap_api_save(request, order_object, order_line_object):
                order_object.status_sap = "confirm save sap"
            else:
                order_object.status_sap = "reject save sap"
        elif order_type == "change" or order_type == "split":
            if call_sap_api_update(request, order_object, order_line_object):
                order_object.status_sap = "confirm update sap"
            else:
                order_object.status_sap = "reject update sap"
    else:
        order_object.status_sap = "reject iplan"

    return order_object


def eo_data_trigger(request):
    try:
        body = request.body
        body = body.decode("ascii")
        body = json.loads(body)
        message_type = body.get("Type")
        if message_type == "SubscriptionConfirmation":
            # Confirm Subscription for http
            confirm_url = body.get("SubscribeURL")
            response = requests.get(confirm_url)
            print(response.status_code)

        elif message_type == "Notification":
            print(body.get("MessageAttributes"))
            order_id = int(body.get("MessageAttributes").get("order_id").get("Value"))
            order_type = body.get("MessageAttributes").get("order_type").get("Value")
            order_object = Order.objects.filter(id=order_id).first()
            order_line_object = OrderLines.objects.filter(order_id=order_id)
            order_object = call_iplan_and_sap_eo_data(
                request, order_type, order_object, order_line_object
            )
            order_object.save()
            return JsonResponse({"status": True})

    except Exception as e:
        raise e


def middleware_check_user_from_header(request):
    auth_token = get_token_from_request(request)
    if auth_token == settings.FOREVER_TOKEN_FOR_EO_UPLOAD:
        return saleor.account.models.User.objects.first()
    if not auth_token:
        raise ValueError("Authorization require")
    user = get_user_from_access_token(auth_token)
    return user


def middleware_check_token(request, default_res):
    auth_token = get_token_from_request(request)
    if not auth_token:
        msg = "Authorization token missing in the request"
        default_res["error"] = msg
        raise ValueError(msg)
    if auth_token == settings.CP_TOKEN_FOR_EOR:
        logging.debug("Token is valid")
    else:
        msg = "Authorization token is not valid in the request"
        default_res["error"] = msg
        logging.error(f"Token passed in invalid {auth_token}")
        raise ValueError(msg)


def get_check_internal_token(request):
    token = request.headers.get(settings.INTERNAL_TOKEN_NAME, None)
    if not token or token != settings.INTERNAL_TOKEN:
        return JsonResponse(
            {
                "message": "Internal token missing or mismatch from request",
                "success": False,
            }
        )


def get_check_header_method(request: HttpResponse, method: str) -> JsonResponse:
    if request.method.upper() != method.upper():
        return JsonResponse(data={"message": "Method not allowed", "success": False})
    return None


def validate_payload_data(payload, eo_upload_log_id, log_key):
    header = payload.get("header")
    initial = payload.get("initial")
    items = payload.get("items")
    mapping_data_to_object = MappingDataToObject()
    initial_parts = mapping_data_to_object.map_inital_part(
        initial=initial, header=header
    )
    header_parts = mapping_data_to_object.map_header_part(header)

    order_object_dict = {**initial_parts, **header_parts}
    try:
        validate_product_group_for_export(order_object_dict, items)
    except Exception as e:
        logging.error(
            f"[EO Upload] Failed as the Order Contains Materials with different Product Group : {eo_upload_log_id}"
        )
        eo_log_state(
            log_key, EO_UPLOAD_STATE_ERROR, "Fail to create order (%s)" % str(e)
        )
        raise e


def receive_eo_data(request):
    eo_upload_log = None
    try:
        user = middleware_check_user_from_header(request)
        if user:
            payload = json.loads(request.body.decode("utf-8"))
            eo_no = get_data_path(payload, "initial.eoNo") or ""
            log_key = "%s|%s|%s" % (
                get_data_path(payload, "initial.contract"),
                get_data_path(payload, "header.poNo"),
                get_data_path(payload, "initial.lotNo"),
            )
            eo_upload_log = EoUploadLog.objects.create(
                eo_no=eo_no,
                log_key=log_key,
                payload=payload,
                updated_at=timezone.now(),
                state=EO_UPLOAD_STATE_IN_PROGRESS,
            )
            logging.info(f"[EOUpload] Uploading logID {eo_upload_log.id}")
            validate_payload_data(payload, eo_upload_log.id, log_key)

            manager = get_plugins_manager()
            _plugin = manager.get_plugin("scg.sns_eo_upload")
            config = _plugin.config
            setup_client_sns(
                region_name=config.region_name,
                access_key=config.client_id,
                secret_key=config.client_secret,
                topic_arn=config.topic_arn,
                # message=str(order_object.id),
                message=str(eo_upload_log.id),
                subject="eo_data",
                message_attribute={},
                message_group_id=str(eo_upload_log.id),
                message_deduplication_id=str(eo_upload_log.id),
            )
            logging.info(f"[EOUpload] Upload successfully logID {eo_upload_log.id}")
            return HttpResponse(status=204)

    except Exception as e:
        if eo_upload_log:
            logging.exception(
                "[EO Upload] Upload failed logID "
                + str(eo_upload_log.id)
                + " with exception "
                + str(e)
            )
        else:
            logging.exception(
                "[EO Upload] Upload failed logID with exception " + str(e)
            )
    return HttpResponse(status=204)


class HttpStatus:
    pass


def get_so_number(request, id):

    default_res = {"soNo": "", "error": "", "tempOrder": id, "message": "success"}
    status = HTTPStatus.OK
    try:
        if id:
            middleware_check_token(request, default_res)
            order_extension = OrderExtension.objects.filter(temp_order_no=id).first()
            if order_extension:
                default_res["soNo"] = order_extension.order.so_no
            else:
                default_res["error"] = "temp order no not found in db"
                default_res["message"] = "success,Not found"
        else:
            default_res["error"] = "tempOrderNo: Parameter not found in the request"
            status = HTTPStatus.BAD_REQUEST
    except Exception as e:
        logging.exception(f"Error during getting so no from temp no {id} " + str(e))

        status = HTTPStatus.INTERNAL_SERVER_ERROR
    return JsonResponse(default_res, status=status)


def get_eo_number(request):
    user = middleware_check_user_from_header(request)
    payload = request.GET
    default_res = {
        "eoNo": "",
        "contract": payload.get("contract").zfill(10),
        "poNo": payload.get("poNo"),
        "lotNo": payload.get("lotNo"),
        "status": "Error",
    }
    # XXX: check required
    for k in ["contract", "poNo", "lotNo"]:
        if not payload.get(k):
            default_res["errorMessage"] = "Missing %s" % k
            return JsonResponse(default_res)
    if not user:
        default_res["errorMessage"] = "Invalid token"
        return JsonResponse(default_res)
    log_key = "%s|%s|%s" % (
        payload.get("contract").zfill(10),
        payload.get("poNo"),
        payload.get("lotNo"),
    )
    log_key_no_pad = "%s|%s|%s" % (
        payload.get("contract"),
        payload.get("poNo"),
        payload.get("lotNo"),
    )
    eo_log_obj = EoUploadLog.objects.filter(log_key=log_key).last()
    if not eo_log_obj:
        eo_log_obj = EoUploadLog.objects.filter(log_key=log_key_no_pad).last()
    if eo_log_obj:
        default_res["eoNo"] = eo_log_obj.eo_no or ""
        default_res["status"] = eo_log_obj.state
        if eo_log_obj.error_message:
            default_res["errorMessage"] = eo_log_obj.error_message
    try:
        # finding the latest one
        order_object = (
            Order.objects.filter(
                contract__code=payload["contract"],
                po_number=payload["poNo"],
                lot_no=payload["lotNo"],
            )
            .values()
            .last()
        )
        # TODO: remove later
        if not order_object:
            raise Exception("Cannot find EO Number")
        default_res.update(
            {
                "eoNo": order_object.get("so_no") or eo_log_obj.eo_no or "",
                "status": eo_log_obj.state or "Error",
            }
        )
    except Exception:
        if not eo_log_obj:
            default_res["errorMessage"] = "Cannot find EO Number"
    return JsonResponse(default_res)


def test_process_eo_upload(request):
    task_sync_eo_upload()
    return HttpResponse("test")


def log_mulesoft_api(request: HttpResponse) -> JsonResponse:
    try:
        res_check_method = get_check_header_method(request, "POST")
        if res_check_method:
            return res_check_method
        res_check_token = get_check_internal_token(request)
        if res_check_token:
            return res_check_token
        params = json.loads(request.body.decode("utf-8"))
        filter_values = params.get("filter") and params.pop("filter")
        log, json_response = save_mulesoft_api_log_entry(filter_values, params)
        if json_response:
            return json_response
        return JsonResponse({"id": log.id})
    except Exception as e:
        logging.exception("Error log mulesoft api: " + str(e))
        content_length = int(request.META.get("CONTENT_LENGTH", 0))
        logging.error(
            f"DATA_UPLOAD_MAX_MEMORY_SIZE error as Request body size: {content_length} bytes, "
            f"and complete request: {request.body}"
        )
    return JsonResponse({"error": "Error log mulesoft api"})
