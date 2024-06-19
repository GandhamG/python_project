import datetime
import uuid

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction

from common.enum import MulesoftFeatureType, MulesoftServiceType
from common.iplan.item_level_helpers import get_product_code
from common.mulesoft_api import MulesoftApiRequest
from sap_migration.graphql.enums import OrderType
from sap_migration.models import OrderLineIPlan, OrderLines
from scg_checkout.graphql.implementations.iplan import (
    change_parameter_follow_inquiry_method,
    get_contract_no_from_order,
    get_ship_to_country_from_order,
    get_shipping_remark_from_order,
    get_sold_to_name_es14_partneraddress_from_order,
)
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_change_order,
)
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import ATPCTPActionType, IPlanEndPoint, SapEnpoint
from scgp_export.graphql.helper import sync_export_order_from_es26
from scgp_po_upload.graphql.enums import SAP21, BeingProcessConstants
from scgp_require_attention_items.graphql.helper import update_attention_type_r5


@transaction.atomic
def get_order_lines_from_so_no_and_item_no(order_lines_input, select_related_fields):
    try:
        list_so_no_input = [d.get("order_no") for d in order_lines_input]
        prepare_order_lines = OrderLines.objects.select_related(
            *select_related_fields
        ).filter(order__so_no__in=list_so_no_input)

        list_so_no_in_db = set(obj.order.so_no for obj in prepare_order_lines)

        for so_no in list_so_no_input:
            if so_no not in list_so_no_in_db:
                raise ValueError(
                    f"order with so no = {so_no} not exists in e-ordering system"
                )

        order_lines = []
        for input_item in order_lines_input:
            for order_line in prepare_order_lines:
                if order_line.order.so_no == input_item.get(
                    "order_no"
                ) and order_line.item_no == input_item.get("item_no", "").lstrip("0"):
                    order_lines.append(order_line)
        if order_lines:
            OrderLines.objects.bulk_update(
                order_lines,
                fields=[
                    "call_atp_ctp",
                ],
            )
        return order_lines
    except Exception as e:
        transaction.set_rollback(True)
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def get_atp_ctp_response(order_lines, plugins):
    rs_items, items_failed, i_plan_messages, order_lines_that_have_response = (
        [],
        [],
        [],
        [],
    )
    order_group = _group_order_items(order_lines)
    response_headers = _call_api_iplan_request(plugins, order_group)

    for header in response_headers:
        response_lines = header.get("DDQResponseLine", [])
        for line in response_lines:
            line_number = line.get("lineNumber", "")
            order_line = _get_order_line_instance(
                order_lines, line_number, header.get("headerCode")
            )
            block_code = run_code = work_centre_code = ""
            items_rs = map_item_rs(
                order_line, line_number, line, block_code, run_code, work_centre_code
            )
            items_rs["header_code"] = order_line.order.so_no
            if line["returnStatus"].lower() == "failure":
                i_plan_messages.append(_get_iplan_error_message(line))
                items_fail = map_item_fail(order_line)
                items_rs.update(items_fail)
                items_failed.append(items_rs)
                order_lines_that_have_response.append(order_line)
                continue

            response_operation = line["DDQResponseOperation"]
            if response_operation:
                block_code = response_operation[0]["blockCode"]
                run_code = response_operation[0]["runCode"]
                work_centre_code = response_operation[0]["workCentreCode"]
                items_success = map_item_success(
                    line,
                    block_code,
                    run_code,
                    work_centre_code,
                    order_line,
                    order_line.order,
                )
                items_rs.update(items_success)
            rs_items.append(items_rs)
            order_lines_that_have_response.append(order_line)

    _save_request_response_to_db(order_lines_that_have_response, response_headers)

    success = _handle_success_fail_items(rs_items)
    failed = _handle_success_fail_items(items_failed)

    return success, i_plan_messages, failed


def _handle_success_fail_items(rs_items):
    grouped_items = {}
    for item in rs_items:
        key = item["order_no"] + item["original_item_no"]
        if key in grouped_items:
            grouped_items[key]["list_items"].append(_map_items(item))
        else:
            grouped_items[key] = {
                "order_no": item["order_no"],
                "original_item_no": item["original_item_no"],
                "line_id": item["line_id"],
                "material_variant_code": item["material_variant_code"],
                "material_variant_description": item["material_variant_description"],
                "original_quantity": item["original_quantity"],
                "original_request_date": item["original_request_date"],
                "original_plant": item["original_plant"],
                "unique_id": key,
                "list_items": [_map_items(item)],
            }

    result = sorted(
        list(grouped_items.values()),
        key=lambda x: (x["order_no"], x["original_item_no"]),
    )
    return result


def _map_items(item):
    item = {
        "item_no": item.get("item_no"),
        "quantity": item.get("quantity"),
        "confirm_date": item.get("confirm_date"),
        "plant": item.get("plant"),
        "atp_ctp": item.get("atp_ctp"),
        "atp_ctp_detail": item.get("atp_ctp_detail"),
        "block_code": item.get("block_code"),
        "run_code": item.get("run_code"),
        "paper_machine": item.get("paper_machine"),
        "unit": item.get("unit"),
        "on_hand_stock": item.get("on_hand_stock"),
        "order_type": item.get("order_type"),
    }
    return item


def call_atp_ctp_request(plugins, order_lines_input):
    order_lines = get_order_lines_from_so_no_and_item_no(
        order_lines_input, ["material_variant", "order", "iplan"]
    )

    called_atp_ctp_request_items = [
        line for line in order_lines if line.iplan.request_iplan_response
    ]
    if called_atp_ctp_request_items:
        line_object = {}
        items_failed, i_plan_messages, order_lines_object = [], [], []
        for line in called_atp_ctp_request_items:
            so_no = line.order.so_no
            if so_no in line_object:
                line_object[so_no].append(line)
            else:
                line_object[so_no] = [line]
        order_lines_object.append(line_object)
        response_headers = _call_api_i_plan_confirm(
            plugins, order_lines_object, ATPCTPActionType.ROLLBACK.value.upper()
        )
        for response in response_headers:
            header_code = response.get("headerCode")
            for line in response.get("DDQAcknowledgeLine"):
                if line.get("returnStatus").lower() == "failure":
                    line_number = line.get("lineNumber")
                    i_plan_messages.append(
                        _get_iplan_atp_ctp_error_message(line, header_code)
                    )
                    order_line = _get_order_line_instance(
                        order_lines, line_number, header_code.zfill(10)
                    )
                    block_code = run_code = work_centre_code = ""
                    items_rs = map_item_rs(
                        order_line,
                        line_number,
                        line,
                        block_code,
                        run_code,
                        work_centre_code,
                    )
                    items_fail = map_item_fail(order_line)
                    items_rs.update(items_fail)
                    items_failed.append(items_rs)
                    return [], i_plan_messages, items_failed

                if line.get("returnStatus").lower() == "success":
                    continue

    return get_atp_ctp_response(order_lines, plugins)


def change_order_call_atp_ctp_request(plugins, order_lines_input):
    mapping_id_with_item_no = {
        line.get("line_id"): line.get("item_no").lstrip("0")
        for line in order_lines_input
    }
    order_lines = OrderLines.objects.select_related("material_variant", "order").filter(
        id__in=list(map(lambda x: x.get("line_id"), order_lines_input))
    )
    for line in order_lines:
        line.item_no = mapping_id_with_item_no.get(str(line.id))
    return get_atp_ctp_response(order_lines, plugins)


def update_i_plan_field(i_plan, items, item):
    i_plan.item_no = item.get("item_no")
    i_plan.iplant_confirm_quantity = item.get("quantity")
    i_plan.iplant_confirm_date = (
        datetime.datetime.strptime(item.get("confirm_date"), "%Y-%m-%d").date()
        if item.get("confirm_date")
        else None
    )
    i_plan.plant = item.get("plant")
    i_plan.block = item.get("block_code")
    i_plan.run = item.get("run_code")
    i_plan.paper_machine = item.get("paper_machine")
    i_plan.order_type = item.get("order_type")
    line_params = items.get("iplan_request_params")
    if line_params:
        i_plan.inquiry_method_code = line_params.get("inquiry_method_code")
        i_plan.use_inventory = line_params.get("use_inventory")
        i_plan.use_consignment_inventory = line_params.get("use_consignment_inventory")
        i_plan.use_projected_inventory = line_params.get("use_projected_inventory")
        i_plan.use_production = line_params.get("use_production")
        i_plan.split_order_item = line_params.get("split_order_item")
        i_plan.single_source = line_params.get("single_source")
        i_plan.re_atp_required = line_params.get("re_atp_required")
        i_plan.fix_source_assignment = line_params.get("fix_source_assignment", "")
        i_plan.request_type = line_params.get("request_type")
        i_plan.type_of_delivery = line_params.get("type_of_delivery", "")
        i_plan.transportation_method = line_params.get("transportation_method", "")


def update_line_field(line, item):
    line.quantity = item.get("quantity")
    line.confirmed_date = (
        datetime.datetime.strptime(item.get("confirm_date"), "%Y-%m-%d").date()
        if item.get("confirm_date")
        else None
    )
    line.plant = item.get("plant")
    line.assigned_quantity = item.get("quantity") if item.get("on_hand_stock") else 0


@transaction.atomic
def call_atp_ctp_confirm(plugins, input_data):
    input_items = input_data.get("items")
    rollback_input_items = list(
        filter(
            lambda item: item.get("action") == ATPCTPActionType.ROLLBACK, input_items
        )
    )
    accept_input_items = list(
        filter(lambda item: item.get("action") == ATPCTPActionType.COMMIT, input_items)
    )
    status_commit = ATPCTPActionType.COMMIT.value.upper()
    status_rollback = ATPCTPActionType.ROLLBACK.value.upper()

    order_lines_dict = {}
    item_call_es_21_success, item_call_es_21_fail = [], []
    es_21_sap_order_messages, es_21_sap_item_messages = [], []
    sap_order_messages, sap_item_messages, i_plan_messages = [], [], []
    atp_ctp_confirm_fail_items, atp_ctp_confirm_success_items, items_call_rollback = (
        [],
        [],
        [],
    )

    if accept_input_items:
        for item in accept_input_items:
            so_no = item.get("order_no")
            item_no = item.get("original_item_no")
            if so_no in order_lines_dict:
                order_lines_dict[so_no].append(item_no)
            else:
                order_lines_dict[so_no] = [item_no]
        for so_no, item_no in order_lines_dict.items():
            order_lines = OrderLines.objects.filter(
                order__so_no=so_no, item_no__in=item_no
            )
            response_es_21 = _call_es_21_to_accept(
                so_no, order_lines, input_items, plugins
            )
            (
                es_21_sap_order_messages,
                es_21_sap_item_messages,
                is_being_process,
                es_21_sap_response_success,
            ) = get_error_messages_from_sap_response_for_change_order(response_es_21)

            if es_21_sap_response_success:
                item_call_es_21_success.append({so_no: order_lines})
            else:
                item_call_es_21_fail.append({so_no: order_lines})

    sap_order_messages += es_21_sap_order_messages
    sap_item_messages += es_21_sap_item_messages

    if item_call_es_21_success:
        item_success_call_confirm = [
            item
            for item in accept_input_items
            if item.get("order_no")
            in [list(line.keys())[0] for line in item_call_es_21_success]
        ]
        response_atp_ctp_confirm = _call_api_i_plan_confirm(
            plugins, item_call_es_21_success, status_commit, item_success_call_confirm
        )
        for response in response_atp_ctp_confirm:
            header_code = response.get("headerCode")
            for line in response.get("DDQAcknowledgeLine"):
                if line.get("returnStatus").lower() == "failure":
                    i_plan_messages.append(
                        _get_iplan_atp_ctp_error_message(line, header_code)
                    )
                    order_lines_fail = OrderLines.objects.filter(
                        order__so_no=header_code.zfill(10),
                        item_no=line.get("lineNumber"),
                    ).first()
                    atp_ctp_confirm_fail_items.append(order_lines_fail)

                if line.get("returnStatus").lower() == "success":
                    order_lines_success = OrderLines.objects.filter(
                        order__so_no=header_code.zfill(10),
                        item_no=line.get("lineNumber"),
                    ).first()
                    atp_ctp_confirm_success_items.append(order_lines_success)
                    _sync_order_from_es_26(atp_ctp_confirm_success_items, plugins)
                    _save_items_after_confirm_success(
                        accept_input_items, atp_ctp_confirm_success_items
                    )

    if atp_ctp_confirm_fail_items:
        update_attention_type_r5(atp_ctp_confirm_fail_items)

    if item_call_es_21_fail:
        response_atp_ctp_roll_back = _call_api_i_plan_confirm(
            plugins, item_call_es_21_fail, status_rollback
        )
        _handle_case_rollback(response_atp_ctp_roll_back, i_plan_messages)

    if rollback_input_items:
        items_call_rollback = _handle_input_items(
            rollback_input_items, order_lines_dict, items_call_rollback
        )
        response_headers = _call_api_i_plan_confirm(
            plugins, items_call_rollback, status_rollback
        )
        _handle_case_rollback(response_headers, i_plan_messages)

    return i_plan_messages, sap_order_messages, sap_item_messages


def _call_api_i_plan_confirm(
    plugins, order_lines, status, item_success_call_confirm=None
):
    request_body = _prepare_param_atp_ctp_require_attention(
        order_lines, status, item_success_call_confirm
    )
    order = order_lines and order_lines[0].order or None
    log_val = {
        "orderid": order and order.id or None,
        "order_number": order and order.so_no or None,
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value, **log_val
    ).request_mulesoft_post(IPlanEndPoint.I_PLAN_CONFIRM.value, request_body)
    response_headers = response.get("DDQAcknowledge").get("DDQAcknowledgeHeader")
    return response_headers


def _call_api_iplan_request(plugins, order_group):
    headers = []
    for _, group_data in order_group.items():
        order = group_data.get("order")
        order_lines = group_data.get("order_lines")
        header = {
            "headerCode": getattr(order, "so_no", "").lstrip("0"),
            "autoCreate": False,
        }
        lines_body = []
        for order_line in order_lines:
            line_params = _get_some_param_for_iplan(order_line, order)
            line_params.update(
                {
                    "lineNumber": order_line.item_no,
                    "locationCode": order.contract.sold_to.sold_to_code.lstrip("0"),
                    "consignmentOrder": False,
                    "productCode": get_product_code(order_line),
                    "quantity": str(order_line.quantity),
                    "typeOfDelivery": "E",
                    "requestType": "AMENDMENT",
                    "unit": _get_unit_param(order_line.sales_unit),
                    "transportMethod": "Truck",
                    "requestDate": order_line.request_date.strftime(
                        "%Y-%m-%dT00:00:00.000Z"
                    ),
                    "consignmentLocation": order_line.order.sales_group.code,
                    "fixSourceAssignment": order_line.plant or "",
                    "DDQSourcingCategories": [
                        {"categoryCode": order.sales_organization.code},
                        {"categoryCode": order.sales_group.code},
                    ],
                }
            )
            lines_body.append(line_params)
        header["DDQRequestLine"] = lines_body
        headers.append(header)

    request_body = {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": headers,
        }
    }

    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value
    ).request_mulesoft_post(IPlanEndPoint.I_PLAN_REQUEST.value, request_body)

    response_headers = response.get("DDQResponse", {}).get("DDQResponseHeader", [])
    return response_headers


def _get_item_no_from_line_number(line_number):
    return line_number.split(".")[0]


def _get_order_line_instance(order_lines, line_number, so_no):
    for order_line in order_lines:
        if order_line.order.so_no.lstrip(
            "0"
        ) == so_no and order_line.item_no == _get_item_no_from_line_number(line_number):
            return order_line

    raise ValidationError(
        f"iplan not return data for {line_number}",
        code=ScgpExportErrorCode.IPLAN_ERROR.value,
    )


def _get_response_confirm_item(response_items, item_no):
    for item in response_items:
        if item.get("lineNumber") == item_no:
            return item

    raise ValidationError(
        f"IPlan-Confirm api not return data for {item_no}",
        code=ScgpExportErrorCode.IPLAN_ERROR.value,
    )


def _get_some_param_for_iplan(order_line, order):
    params = change_parameter_follow_inquiry_method(order_line, order)
    return {
        "inquiryMethod": params["inquiry_method"],
        "useInventory": params["use_inventory"],
        "useConsignmentInventory": params["use_consignment_inventory"],
        "useProjectedInventory": params["use_projected_inventory"],
        "useProduction": params["use_production"],
        "singleSourcing": params["single_source"],
        "orderSplitLogic": params["order_split_logic"],
        "reATPRequired": params["re_atp_required"],
    }


def _get_request_param_for_iplan(order_line, order):
    params = change_parameter_follow_inquiry_method(order_line, order)
    return {
        "inquiry_method_code": params["inquiry_method"],
        "use_inventory": params["use_inventory"],
        "use_consignment_inventory": params["use_consignment_inventory"],
        "use_projected_inventory": params["use_projected_inventory"],
        "use_production": params["use_production"],
        "single_source": params["single_source"],
        "split_order_item": params["order_split_logic"],
        "re_atp_required": params["re_atp_required"],
        "fix_source_assignment": order_line.plant,
        "request_type": "AMENDMENT",
        "type_of_delivery": "E",
        "transportation_method": "Truck",
    }


def _get_unit_param(sales_unit):
    if not sales_unit:
        return ""
    if sales_unit == "ม้วน":
        return "ROL"
    return sales_unit


def _get_iplan_error_message(line):
    return_code = line.get("returnCode")
    if not return_code:
        return {
            "item_no": line.get("lineNumber", "").lstrip("0"),
            "first_code": "0",
            "second_code": "0",
        }

    return {
        "item_no": line.get("lineNumber", "").lstrip("0"),
        "first_code": return_code[18:24],
        "second_code": return_code[24:32],
    }


def map_item_rs(order_line, line_number, line, block_code, run_code, work_centre_code):
    items_rs = {
        "original_item_no": order_line.item_no,
        "item_no": line_number,
        "material_variant_code": line.get("productCode", ""),
        "material_variant_description": order_line.material_variant.description_th,
        "quantity": line.get("quantity", ""),
        "confirm_date": line.get("dispatchDate", "") or order_line.confirmed_date,
        "plant": line.get("warehouseCode", ""),
        "atp_ctp": line.get("orderType", ""),
        "atp_ctp_detail": line.get("status", ""),
        "block_code": block_code,
        "run_code": run_code,
        "paper_machine": work_centre_code,
        "order_no": order_line.order.so_no,
        "original_quantity": order_line.quantity,
        "original_request_date": order_line.request_date,
        "original_plant": order_line.plant,
        "unit": _get_unit_param(order_line.sales_unit),
        "on_hand_stock": "",
        "order_type": line.get("orderType", ""),
        "iplan_request_params": {},
        "line_id": order_line.id,
    }
    return items_rs


def map_item_success(
    line, block_code, run_code, work_centre_code, order_line=None, order=None
):
    item_success = {
        "block_code": block_code,
        "run_code": run_code,
        "paper_machine": work_centre_code,
        "on_hand_stock": line.get("onHandStock", ""),
        "iplan_request_params": _get_request_param_for_iplan(order_line, order)
        if order_line and order
        else {},
    }
    return item_success


def map_item_fail(order_line):
    items_fail = {
        "material_variant_code": order_line.material_variant.code,
        "quantity": "-",
        "confirm_date": "-",
        "plant": "-",
        "atp_ctp": "fail",
        "block_code": "-",
        "run_code": "-",
        "paper_machine": "-",
    }
    return items_fail


def _map_header_code_and_order_lines(order_lines, response_header, input_items):
    mapping = {}
    for order_line in order_lines:
        header_code = order_line.order.so_no
        mapping.setdefault(header_code, []).append(
            {
                "order_line": order_line,
                "response_item": _get_response_item_by(
                    response_header, header_code, order_line.item_no
                ),
                "input_item": _get_input_item_by(
                    input_items, header_code, order_line.item_no
                ),
            }
        )

    return mapping


def _get_response_item_by(response_header, header_code, item_no):
    for header in response_header:
        if not header.get("headerCode") == header_code:
            continue

        for item in header.get("DDQAcknowledgeLine"):
            if item.get("lineNumber", "").lstrip("0") == item_no:
                return item
    return None


def _get_input_item_by(input_items, header_code, item_no):
    for item in input_items:
        if item.get("header_code") == header_code and item_no == item.get("item_no"):
            return item
    return None


def get_max_item_no(order_lines):
    return max(int(order_line.item_no) for order_line in order_lines)


def _call_es_21_to_accept(so_no, order_lines, input_item, plugins):
    try:
        params = _prepare_param_es_21_atp_ctp(so_no, order_lines, input_item)
        log_val = {
            "order_number": so_no,
            "feature": MulesoftFeatureType.CHANGE_ORDER.value,
        }
        response = MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.SAP.value, **log_val
        ).request_mulesoft_post(
            SapEnpoint.ES_21.value,
            params,
            encode=True,
        )
        return response
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def _prepare_param_es_21_atp_ctp(so_no, order_lines, input_item):
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []

    line_ids = [str(line.id) for line in order_lines]
    filtered_items = [item for item in input_item if item.get("line_id") in line_ids]
    latest_item_no = int(max(line.item_no for line in order_lines))
    order_lines_map = {
        line_id: OrderLines.objects.filter(id=line_id).first() for line_id in line_ids
    }

    for item in filtered_items:
        line = order_lines_map[item.get("line_id")]
        plant = item.get("original_plant")
        material = item.get("material_variant_code")
        target_quantity = item.get("original_quantity")
        request_date = item.get("original_request_date")
        for i in item.get("list_items"):
            delivery_block = (
                "09" if line.iplan and request_date != i.get("confirm_date") else ""
            )
            if i.get("item_no") != f"{item.get('original_item_no')}.001":
                new_item_no = str(latest_item_no + 10)
            else:
                new_item_no = item.get("original_item_no")

            item_in = {
                "itemNo": new_item_no.zfill(6),
                "material": material,
                "targetQty": target_quantity,
                "plant": plant,
                "refDoc": line.order.contract.code,
                "refDocIt": line.contract_material.item_no,
            }
            items_inx = {
                "itemNo": new_item_no.zfill(6),
                "updateflag": "I"
                if new_item_no != item.get("original_item_no")
                else "U",
                "targetQty": True,
                "plant": True,
            }
            schedules_in = {
                "itemNo": new_item_no.zfill(6),
                "scheduleLine": "0001",
                "reqDate": request_date.strftime("%d/%m/%Y"),
                "reqQty": target_quantity,
                "confirmQty": float(i.get("quantity")),
                "deliveryBlock": delivery_block,
            }
            schedules_inx = {
                "itemNo": new_item_no.zfill(6),
                "updateflag": "I"
                if new_item_no != item.get("original_item_no")
                else "U",
                "requestDate": True,
                "requestQuantity": True,
                "confirmQuantity": True,
                "deliveryBlock": True,
            }
            order_items_in.append(item_in)
            order_items_inx.append(items_inx)
            order_schedules_in.append(schedules_in)
            order_schedules_inx.append(schedules_inx)

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderItemsIn": sorted(order_items_in, key=lambda x: x["itemNo"]),
        "orderItemsInx": sorted(order_items_inx, key=lambda x: x["itemNo"]),
        "orderSchedulesIn": sorted(order_schedules_in, key=lambda x: x["itemNo"]),
        "orderSchedulesInx": sorted(order_schedules_inx, key=lambda x: x["itemNo"]),
    }

    return params


def _prepare_param_atp_ctp_require_attention(
    order_lines_object, status, item_success_call_confirm=None
):
    list_order_lines = []
    for dictionary in order_lines_object:
        for key, value in dictionary.items():
            list_order_lines.append({key: value})

    confirm_header = []
    if status == "ROLLBACK":
        confirm_header = _handle_param_when_rollback(list_order_lines)
    if status == "COMMIT":
        confirm_header = _handle_param_when_commit(item_success_call_confirm)

    request_body = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": confirm_header,
        }
    }
    return request_body


def _handle_param_when_rollback(list_order_lines):
    confirm_header = [
        {
            "headerCode": list(line.keys())[0].lstrip("0"),
            "originalHeaderCode": list(line.keys())[0].lstrip("0"),
            "DDQConfirmLine": [
                {
                    "lineNumber": item.item_no,
                    "originalLineNumber": item.item_no,
                    "status": "ROLLBACK",
                    "DDQOrderInformationType": [],
                }
                for item in line[list(line.keys())[0]]
            ],
        }
        for line in list_order_lines
    ]
    return confirm_header


def _handle_param_when_commit(item_success_call_confirm):
    item_rs, ddq_confirm_header = [], []
    item_rs = _handle_data_param_commit(item_success_call_confirm, item_rs)
    for order in item_rs:
        order_no = order.get("order_no")
        order_lines = OrderLines.objects.filter(order__so_no=order_no)
        latest_item_no = max(
            map(lambda line: int(line.item_no), order_lines), default=0
        )
        ddq_confirm_line = []
        for item in order.get("items"):
            for i in item.get("item"):
                line_number = (
                    str(latest_item_no + 10)
                    if not i.get("item_no").endswith(".001")
                    else item.get("original_item_no")
                )
                confirm_line = {
                    "lineNumber": line_number,
                    "originalLineNumber": i.get("item_no"),
                    "onHandQuantityConfirmed": "0"
                    if not i.get("on_hand_stock")
                    else i.get("quantity"),
                    "unit": "ROL",
                    "status": "COMMIT",
                    "DDQOrderInformationType": [],
                }
                ddq_confirm_line.append(confirm_line)
        confirm_header = {
            "headerCode": order_no.lstrip("0"),
            "originalHeaderCode": order_no.lstrip("0"),
            "DDQConfirmLine": ddq_confirm_line,
        }
        ddq_confirm_header.append(confirm_header)

    return ddq_confirm_header


def _get_order_information_type(order, status):
    order_information_type = []
    if order.type == OrderType.EXPORT.value and status == status:
        contract_no = get_contract_no_from_order(order)
        country = get_ship_to_country_from_order(order)
        sold_to_name = get_sold_to_name_es14_partneraddress_from_order(order)
        shipping_remark = get_shipping_remark_from_order(order)
        order_information_item = []

        if shipping_remark:
            order_information_item.append(
                {
                    "valueType": "ShippingMarks",
                    "value": shipping_remark,
                }
            )
        if contract_no:
            order_information_item.append(
                {
                    "valueType": "ProformaInvoice",
                    "value": str(int(contract_no))
                    if contract_no.isdigit()
                    else contract_no,
                }
            )
        if sold_to_name:
            order_information_item.append(
                {"valueType": "SoldTo", "value": sold_to_name}
            )
        if not order.eo_upload_log:
            if country:
                order_information_item.append(
                    {"valueType": "Country", "value": country}
                )
        order_information_type.append(
            {"type": "CustomInfo", "DDQOrderInformationItem": order_information_item}
        )
    return order_information_type


def _get_iplan_atp_ctp_error_message(line, so_no):
    return_code = line.get("returnCode")
    if not return_code:
        return {
            "so_no": so_no,
            "item_no": line.get("lineNumber", "").lstrip("0"),
            "first_code": "0",
            "second_code": "0",
            "message": line.get("returnCodeDescription"),
        }
    return {
        "so_no": so_no,
        "item_no": line.get("lineNumber", "").lstrip("0"),
        "first_code": return_code[18:24],
        "second_code": return_code[24:32],
        "message": line.get("returnCodeDescription"),
    }


def _save_items_after_confirm_success(input_items, order_lines):
    update_line = []
    update_i_plan_line = []
    i_plan_fields_to_update = [
        "item_no",
        "iplant_confirm_quantity",
        "iplant_confirm_date",
        "plant",
        "block",
        "run",
        "paper_machine",
        "order_type",
        "inquiry_method_code",
        "use_inventory",
        "use_consignment_inventory",
        "use_projected_inventory",
        "use_production",
        "split_order_item",
        "single_source",
        "re_atp_required",
        "fix_source_assignment",
        "request_type",
        "type_of_delivery",
        "transportation_method",
    ]
    for item in input_items:
        order_line = OrderLines.objects.filter(order__so_no=item.get("order_no"))
        latest_item_no = max(
            map(lambda line: int(line.item_no), order_lines), default=0
        )
        for line in order_line:
            for i in item.get("list_items"):
                if i.get("item_no") == f"{line.item_no}.001":
                    update_line_field(line, i)
                    i_plan = line.iplan
                    update_i_plan_field(i_plan, item, i)
                    update_line.append(line)
                    update_i_plan_line.append(i_plan)
                else:
                    new_line = line.objects.filter(
                        item_no=str(latest_item_no + 10)
                    ).first()
                    update_line_field(new_line, i)
                    new_i_plan = new_line.iplan
                    update_i_plan_field(new_i_plan, item, i)
                    update_line.append(new_line)
                    update_i_plan_line.append(new_i_plan)

    OrderLines.objects.bulk_update(
        update_line, fields=["confirmed_date", "quantity", "plant"]
    )
    OrderLineIPlan.objects.bulk_update(
        update_i_plan_line, fields=i_plan_fields_to_update
    )


def _handle_input_items(input_items, order_lines_dict, result_item_to_call_api):
    for item in input_items:
        so_no = item.get("order_no")
        item_no = item.get("original_item_no")
        if so_no in order_lines_dict:
            order_lines_dict[so_no].append(item_no)
        else:
            order_lines_dict[so_no] = [item_no]
    for so_no, item_no in order_lines_dict.items():
        order_lines = OrderLines.objects.filter(order__so_no=so_no, item_no__in=item_no)
        result_item_to_call_api.append({so_no: order_lines})
    return result_item_to_call_api


def _group_order_items(order_lines):
    order_group = {}
    for order_line in order_lines:
        order_id = order_line.order.id
        if order_id not in order_group:
            order_group[order_id] = {
                "order": order_line.order,
                "order_lines": [order_line],
            }
        else:
            order_group[order_id]["order_lines"].append(order_line)
    return order_group


def _save_request_response_to_db(list_order_lines, response):
    response_dict = {}
    unique_order_lines_list = list(set(list_order_lines))
    for header in response:
        header_code = header["headerCode"].zfill(10)
        for line in header["DDQResponseLine"]:
            line_number = line["lineNumber"]
            if line["returnStatus"] == "SUCCESS":
                response_dict[(header_code, line_number)] = line
    output = _handle_request_response_to_save_db(response_dict)
    update_objs = []
    if response_dict:
        for line in unique_order_lines_list:
            response_line = output.get((line.order.so_no, line.item_no))
            if response_line:
                line.iplan.request_iplan_response = response_line
                update_objs.append(line.iplan)
        OrderLineIPlan.objects.bulk_update(update_objs, ["request_iplan_response"])


def _handle_request_response_to_save_db(response_dict):
    output = {}
    for key, value in response_dict.items():
        new_key = (key[0], key[1].split(".")[0])
        if new_key not in output:
            output[new_key] = []
        output[new_key].append(value)
    return output


def _delete_i_plan_response(i_plans):
    for i_plan in i_plans:
        i_plan.request_iplan_response = None

    OrderLineIPlan.objects.bulk_update(i_plans, fields=["request_iplan_response"])


def _handle_case_rollback(response_headers, i_plan_messages):
    delete_item_response = []
    for response in response_headers:
        header_code = response.get("headerCode")
        for line in response.get("DDQAcknowledgeLine"):
            if line.get("returnStatus").lower() == "failure":
                i_plan_messages.append(
                    _get_iplan_atp_ctp_error_message(line, header_code)
                )
            if line.get("returnStatus").lower() == "success":
                order_lines_fail = (
                    OrderLines.objects.filter(
                        order__so_no=header_code.zfill(10),
                        item_no=line.get("lineNumber"),
                    )
                    .select_related("iplan")
                    .first()
                )
                delete_item_response.append(order_lines_fail)
                _delete_i_plan_response([line.iplan for line in delete_item_response])


def _handle_data_param_commit(item_success_call_confirm, item_rs):
    order_nos = set(item["order_no"] for item in item_success_call_confirm)
    for order_no in order_nos:
        items = []
        for item in item_success_call_confirm:
            if item["order_no"] == order_no:
                items.append(
                    {
                        "original_item_no": item["original_item_no"],
                        "item": [
                            {"item_no": list_item["item_no"]}
                            for list_item in item.get("list_items", [])
                        ],
                    }
                )
        item_rs.append({"order_no": order_no, "items": items})
    return item_rs


def _sync_order_from_es_26(order_lines, plugins):
    for line in order_lines:
        so_no = line.order.so_no
        response = call_sap_es26(so_no=so_no, sap_fn=plugins.call_api_sap_client)
        sync_export_order_from_es26(response)


def handle_case_being_process_sap(response, so_no):
    being_process_id = BeingProcessConstants.BEING_PROCESS_CODE_ID.lower()
    being_process_number = BeingProcessConstants.BEING_PROCESS_CODE
    sap_order_messages = []
    if response.get("data"):
        sap_order_messages = [
            {
                "id": data.get("id"),
                "number": data.get("number"),
                "so_no": "",
                "message": f"SAP - {so_no} - {data.get('number')} - {data.get('message')}",
            }
            for data in response.get("data")
            if data.get("type") == SAP21.FAILED.value
            and data.get("id", "").lower() == being_process_id
            and data.get("number") == being_process_number
        ]
    is_being_process = True if sap_order_messages else False
    return sap_order_messages, is_being_process
