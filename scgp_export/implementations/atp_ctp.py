import logging
import uuid
from copy import deepcopy

from django.db import transaction
from django.db.models import F

from common.atp_ctp.atp_ctp_button import (
    set_status_for_order_line,
    update_field_item_no_latest_for_order,
    update_status_for_order,
)
from common.helpers import DateHelper, mock_confirm_date
from common.iplan.item_level_helpers import get_product_code
from sap_migration.models import Order, OrderLineIPlan, OrderLines
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.helper import (
    call_es21_get_response,
    call_i_plan_confirm,
    call_i_plan_request_get_response,
    get_iplan_error_messages,
)
from scg_checkout.graphql.implementations.iplan import (
    change_parameter_follow_inquiry_method,
)
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_change_order,
)
from scgp_export.graphql.enums import ATPCTPActionType
from scgp_require_attention_items.graphql.helper import (
    update_attention_type_r1,
    update_attention_type_r5,
)


def change_order_call_atp_ctp_request(manager, lines_input):
    order_lines = OrderLines.all_objects.select_related(
        "material_variant", "order", "iplan"
    ).filter(id__in=[line.get("line_id") for line in lines_input])
    order = Order.objects.annotate(
        sale_org_code=F("sales_organization__code"),
        sale_group_code=F("sales_group__code"),
        sold_to__sold_to_code=F("sold_to__sold_to_code"),
    ).get(id=order_lines[0].order.id)

    # call rollback first
    (
        is_full_iplan_success,
        i_plan_error_messages,
        iplan_response,
    ) = _call_iplan_rollback_if_exists_response(manager, order, order_lines)
    if not is_full_iplan_success:
        return [], i_plan_error_messages, []

    # call iplan request
    line_inputs = _insert_iplan_response_lines_to_line_input(
        manager, order, order_lines, lines_input
    )

    success_items = []
    failed_items = []
    i_plan_messages = []
    for line_input in line_inputs:
        success_response_lines = []
        order_line = line_input["line_instance"]

        # one input maybe has many response line due to split case
        for response_line in line_input["iplan_response_lines"]:
            rs_item = {
                "original_item_no": line_input.get("item_no"),
                "material_variant_code": order_line.material_variant.code
                if order_line.material_variant
                else order_line.material_code,
                "material_variant_description": order_line.material_variant.description_en
                if order_line.material_variant
                else "",
                "original_quantity": line_input.get("quantity"),
                "original_request_date": line_input.get("request_date"),
                "original_plant": line_input.get("plant"),
                "line_id": order_line.id,
                "order_no": order_line.order.so_no,
                # data from response
                "item_no": "-",
                "quantity": "-",
                "confirm_date": "-",
                "plant": "-",
                "atp_ctp": "fail",
                "atp_ctp_detail": "-",
                "block_code": "-",
                "run_code": "-",
                "paper_machine": "-",
                "on_hand_stock": "-",
                "unit": "-",
                "order_type": "-",
            }

            if response_line["returnStatus"].lower() == "success":
                operation = {}
                if operations := response_line.get("DDQResponseOperation"):
                    operation = operations[0]
                rs_item.update(
                    {
                        "item_no": response_line.get("lineNumber"),
                        "quantity": response_line.get("quantity"),
                        "plant": response_line.get("warehouseCode"),
                        "atp_ctp": response_line.get("orderType"),
                        "atp_ctp_detail": response_line.get("status"),
                        "block_code": operation.get("blockCode", ""),
                        "run_code": operation.get("runCode", ""),
                        "paper_machine": operation.get("workCentreCode", ""),
                        "on_hand_stock": response_line.get("onHandStock", ""),
                        "unit": response_line.get("unit"),
                        "confirm_date": response_line.get("dispatchDate")
                        or mock_confirm_date(
                            line_input.get("request_date"), response_line.get("status")
                        ),
                        "order_type": response_line.get("orderType"),
                    }
                )
                success_items.append(rs_item)
                success_response_lines.append(response_line)
            else:
                failed_items.append(rs_item)
                i_plan_messages.append(_get_iplan_error_message(response_line))

        line_input["success_response_lines"] = success_response_lines

    # update iplan
    _update_iplan_for_success_lines(line_inputs)

    return (
        _transform_data_to_return(success_items),
        i_plan_messages,
        _transform_data_to_return(failed_items),
    )


def _update_iplan_for_success_lines(line_inputs):
    iplans = []
    update_data = {}
    for line_input in line_inputs:
        if not line_input["success_response_lines"]:
            continue

        iplan = line_input["line_instance"].iplan
        line_params = line_input["line_params"]
        update_data = {
            # save request params
            "inquiry_method_code": line_params.get("inquiryMethod"),
            "use_inventory": line_params.get("useInventory"),
            "use_consignment_inventory": line_params.get("useConsignmentInventory"),
            "use_projected_inventory": line_params.get("useProjectedInventory"),
            "use_production": line_params.get("useProduction"),
            "split_order_item": line_params.get("orderSplitLogic"),
            "single_source": line_params.get("singleSourcing"),
            "re_atp_required": line_params.get("reATPRequired"),
            "fix_source_assignment": line_params.get("fixSourceAssignment", ""),
            "request_type": line_params.get("requestType"),
            "type_of_delivery": line_params.get("typeOfDelivery", ""),
            "transportation_method": line_params.get("transportMethod", ""),
            # save success response lines
            "request_iplan_response": line_input["success_response_lines"] or None,
        }
        _set_instance_fields(iplan, update_data)
        iplans.append(iplan)
    if iplans:
        OrderLineIPlan.objects.bulk_update(iplans, fields=update_data.keys())


def _call_iplan_rollback_if_exists_response(manager, order, order_lines):
    rollback_lines_input = []
    for order_line in order_lines:
        response_lines = order_line.iplan.request_iplan_response
        if not response_lines:
            continue

        rollback_lines_input.append(
            {
                "calculated_item_no": order_line.item_no,
                "item_no": order_line.item_no,
                "action": "ROLLBACK",
                "order_no": order.so_no,
            }
        )

    is_full_iplan_success = True
    i_plan_error_messages = []
    iplan_response = {}
    if rollback_lines_input:
        (
            is_full_iplan_success,
            i_plan_error_messages,
            iplan_response,
        ) = _call_iplan_rollback(manager, rollback_lines_input)
        if is_full_iplan_success:
            _delete_iplan_response([order_line.iplan for order_line in order_lines])

    return is_full_iplan_success, i_plan_error_messages, iplan_response


def _insert_iplan_response_lines_to_line_input(
    manager, order, order_lines, _lines_input
):
    lines_input = deepcopy(_lines_input)

    request_body = _build_params_for_iplan_request(order, order_lines, lines_input)
    response = call_i_plan_request_get_response(manager, request_body)
    response_lines = (
        response.get("DDQResponse", {})
        .get("DDQResponseHeader")[0]
        .get("DDQResponseLine", [])
    )

    line_id_to_order_line = {
        str(order_line.id): order_line for order_line in order_lines
    }

    for line_input in lines_input:
        item_no = line_input.get("item_no")
        line_input["line_instance"] = line_id_to_order_line[line_input.get("line_id")]
        line_input["iplan_response_lines"] = []
        for response_line in response_lines:
            if response_line.get("lineNumber").split(".")[0] == item_no:
                line_input["iplan_response_lines"].append(response_line)

    return lines_input


def _build_params_for_iplan_request(order, order_lines, order_lines_input):
    id_to_order_line = {str(order_line.id): order_line for order_line in order_lines}
    lines_body = []
    for line_input in order_lines_input:
        order_line = id_to_order_line.get(line_input.get("line_id"))
        if line_input.get("inquiry_method"):
            order_line.inquiry_method = line_input.get("inquiry_method")
        line_params = _get_some_param_for_iplan(order_line, order)
        line_params.update(
            {
                "lineNumber": line_input.get("item_no"),
                "locationCode": order.sold_to__sold_to_code.lstrip("0")
                if order.sold_to and order.sold_to__sold_to_code
                else "",
                "productCode": get_product_code(order_line),
                "quantity": str(line_input.get("quantity")),
                "typeOfDelivery": "E",
                "requestType": "AMENDMENT",
                "unit": "ROL",
                "transportMethod": "Truck",
                "requestDate": line_input.get("request_date") + "T00:00:00.000Z",
                "consignmentOrder": False,
                "fixSourceAssignment": line_input.get("plant") or "",
                "consignmentLocation": order.sale_group_code,
                "DDQSourcingCategories": [
                    {"categoryCode": order.sale_group_code},
                    {"categoryCode": order.sale_org_code},
                ],
            }
        )
        lines_body.append(line_params)
        line_input["line_params"] = line_params

    request_body = {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": [
                {
                    "headerCode": getattr(order, "so_no", "").lstrip("0"),
                    "autoCreate": False,
                    "DDQRequestLine": lines_body,
                }
            ],
        }
    }
    return request_body


def _build_request_body_for_iplan_rollback(input_items):
    param_lines = []
    set_item_no = set()
    for input_item in input_items:
        item_no = input_item.get("item_no").split(".")[0]
        list_items = input_item.get("list_items", None)
        if (item_no in set_item_no) or (list_items and list_items[0].atp_ctp == "fail"):
            continue

        param_line = {
            "lineNumber": item_no,
            "originalLineNumber": item_no,
            "status": "ROLLBACK",
            "DDQOrderInformationType": [],
        }

        param_lines.append(param_line)
        set_item_no.add(item_no)

    request_body = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": input_items[0]["order_no"].lstrip("0"),
                    "originalHeaderCode": input_items[0]["order_no"].lstrip("0"),
                    "DDQConfirmLine": param_lines,
                }
            ],
        }
    }

    return request_body


def _build_request_body_for_iplan_confirm(input_items, es21_response=None):
    param_lines = []
    for input_item in input_items:
        calculated_item_no = input_item["calculated_item_no"]

        # build param for onHandQuantityConfirmed
        es21_order_schedules_out = es21_response.get("orderSchedulesOut")
        item_no_to_es21_order_schedules_out = {
            item.get("itemNo").lstrip("0"): item for item in es21_order_schedules_out
        }
        on_hand_stock = input_item.get("on_hand_stock")
        es21_order_schedules_out = item_no_to_es21_order_schedules_out[
            calculated_item_no
        ]

        confirm_quantity = (
            str(es21_order_schedules_out.get("confirmQuantity"))
            if on_hand_stock
            else "0"
        )

        # line param
        param_line = {
            "lineNumber": calculated_item_no,
            "originalLineNumber": input_item.get("item_no"),
            "unit": input_item.get("unit"),
            "onHandQuantityConfirmed": confirm_quantity,
            "status": "COMMIT",
            "DDQOrderInformationType": [],
        }
        param_lines.append(param_line)

    request_body = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": input_items[0]["order_no"].lstrip("0"),
                    "originalHeaderCode": input_items[0]["order_no"].lstrip("0"),
                    "DDQConfirmLine": param_lines,
                }
            ],
        }
    }

    return request_body


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


def _get_iplan_error_message(line):
    return_code = line.get("returnCode")
    if not return_code:
        return {
            "item_no": line.get("lineNumber", "").lstrip("0"),
            "first_code": "0",
            "second_code": "0",
            "message": line.get("returnCodeDescription"),
        }

    return {
        "item_no": line.get("lineNumber", "").lstrip("0"),
        "first_code": return_code[18:24],
        "second_code": return_code[24:32],
        "message": line.get("returnCodeDescription"),
    }


def get_data_for_iplan_request_params(line_params):
    return {
        "inquiry_method_code": line_params.get("inquiryMethod"),
        "use_inventory": line_params.get("useInventory"),
        "use_consignment_inventory": line_params.get("useConsignmentInventory"),
        "use_projected_inventory": line_params.get("useProjectedInventory"),
        "use_production": line_params.get("useProduction"),
        "split_order_item": line_params.get("useProduction"),
        "single_source": line_params.get("singleSourcing"),
        "re_atp_required": line_params.get("reATPRequired"),
        "fix_source_assignment": line_params.get("fixSourceAssignment", ""),
        "request_type": line_params.get("requestType"),
        "type_of_delivery": line_params.get("typeOfDelivery", ""),
        "transportation_method": line_params.get("transportMethod", ""),
    }


def change_order_call_atp_ctp_confirm(info, input_data):
    # prepare common data
    input_items = _transform_data_to_input(input_data.get("items"))
    order_lines = OrderLines.all_objects.select_related(
        "material_variant", "order", "iplan"
    ).filter(id__in=[item.get("line_id") for item in input_items])
    _inject_order_line_instance_to_input_item(input_items, order_lines)
    _inject_calculated_item_no_to_input_items(
        order_lines[0].order, order_lines, input_items
    )
    action_type = input_items[0].get("action")

    # return variables
    sap_order_error_messages = []
    sap_item_messages = []
    i_plan_error_messages = []

    # ROLLBACK CASE
    if action_type == ATPCTPActionType.ROLLBACK:
        # call iplan rollback
        is_full_iplan_success, i_plan_error_messages, _ = _call_iplan_rollback(
            info, input_items
        )
        logging.info(
            f"[Export: ATP/CTP Rollback] is_full_iplan_success: {is_full_iplan_success},"
            f" i_plan_error_messages : {i_plan_error_messages}"
        )
        if is_full_iplan_success:
            _delete_iplan_response([order_line.iplan for order_line in order_lines])
            input_items = rollback_input_items(input_items)
        return (
            sap_order_error_messages,
            sap_item_messages,
            i_plan_error_messages,
            input_items,
        )

    # COMMIT CASE
    order = Order.objects.filter(so_no=input_items[0]["order_no"]).first()

    # call es21 update order
    (
        is_es21_success,
        sap_order_error_messages,
        sap_item_messages,
        es21_response,
    ) = _call_es_21(info, order, input_items)
    logging.info(
        f"[Export: ATP/CTP Accept] is_es21_success: {is_es21_success},"
        f" sap_order_error_messages : {sap_order_error_messages},"
        f"sap_item_messages: {sap_item_messages}"
    )
    if not is_es21_success:
        # call iplan rollback
        is_full_iplan_success, i_plan_error_messages, _ = _call_iplan_rollback(
            info, input_items
        )
        logging.info(
            f"[Export: ATP/CTP Rollback] is_full_iplan_success: {is_full_iplan_success},"
            f" i_plan_rollback_error_messages : {i_plan_error_messages}"
        )
        if is_full_iplan_success:
            _delete_iplan_response([order_line.iplan for order_line in order_lines])
        return (
            sap_order_error_messages,
            sap_item_messages,
            i_plan_error_messages,
            input_items,
        )

    # update db
    old_order_lines, new_order_lines = _update_db(input_items)
    update_attention_type_r1(old_order_lines + new_order_lines)

    # call iplan commit
    _, i_plan_error_messages, iplan_response = _call_iplan_confirm(
        info, input_items, es21_response, order=order
    )
    logging.info(
        f"[Export: ATP/CTP Confirm] i_plan_confirm_error_messages: {i_plan_error_messages}"
    )
    if not i_plan_error_messages:
        # commit success
        _update_db_after_commit_success(old_order_lines + new_order_lines)

    # update flag R5 for failed lines
    _update_flag_R5(old_order_lines + new_order_lines, i_plan_error_messages)

    _inject_new_line_id_to_input_items(input_items, new_order_lines)
    return (
        sap_order_error_messages,
        sap_item_messages,
        i_plan_error_messages,
        input_items,
    )


def _inject_order_line_instance_to_input_item(input_items, order_lines):
    # NOTE: many input item has the same order line due to split case

    str_line_id_to_order_line = {str(instance.id): instance for instance in order_lines}
    for input_item in input_items:
        input_item["order_line_instance"] = str_line_id_to_order_line.get(
            input_item.get("line_id")
        )


def _call_es_21(info, order, input_items):
    es21_request_body = _build_request_body_for_es_21(order, input_items)
    es21_response = call_es21_get_response(info, es21_request_body)
    (
        sap_order_message,
        sap_item_message,
        is_being_process,
        is_es21_success,
    ) = get_error_messages_from_sap_response_for_change_order(es21_response)
    return is_es21_success, sap_order_message, sap_item_message, es21_response


def _call_iplan_confirm(info, input_items, es21_response=None, order=None):
    iplan_confirm_body = _build_request_body_for_iplan_confirm(
        input_items, es21_response
    )
    iplan_response = call_i_plan_confirm(info, iplan_confirm_body, order=order)
    is_full_iplan_success, i_plan_error_messages = get_iplan_error_messages(
        iplan_response
    )
    return is_full_iplan_success, i_plan_error_messages, iplan_response


def _call_iplan_rollback(info, input_items):
    request_body = _build_request_body_for_iplan_rollback(input_items)
    iplan_response = {}
    i_plan_error_messages = []
    is_full_iplan_success = True
    if len(
        request_body.get("DDQConfirm").get("DDQConfirmHeader")[0].get("DDQConfirmLine")
    ):
        iplan_response = call_i_plan_confirm(info, request_body)
        is_full_iplan_success, i_plan_error_messages = get_iplan_error_messages(
            iplan_response
        )
    return is_full_iplan_success, i_plan_error_messages, iplan_response


def _build_request_body_for_es_21(order, input_items):
    param_order_items_in = []
    param_order_items_in_x = []
    param_order_schedules_in = []
    param_order_schedules_in_x = []

    for input_item in input_items:
        order_line = input_item.get("order_line_instance")
        is_new_order_line = order_line.item_no != input_item.get("calculated_item_no")

        param_item_no = input_item.get("calculated_item_no").zfill(6)
        param_quantity = float(input_item.get("quantity"))
        param_request_quantity = param_quantity

        # build param for field: orderItemsIn
        order_items_in = {
            "itemNo": param_item_no,
            "material": input_item.get("material_variant_code"),
            "targetQty": param_quantity,
            "plant": input_item.get("plant"),
            "refDoc": order_line.ref_doc,
            "refDocIt": order_line.contract_material.item_no,
        }
        # build param for field: orderItemsInx
        order_items_inx = {
            "itemNo": param_item_no,
        }
        original_param_req_date = DateHelper.obj_to_sap_str(order_line.request_date)
        original_req_date = DateHelper.obj_to_sap_str(order_line.original_request_date)
        if is_new_order_line:
            order_items_inx["poDate"] = is_new_order_line
            order_items_inx["targetQty"] = is_new_order_line
            order_items_inx["plant"] = is_new_order_line
            order_items_inx["updateflag"] = "I"
            order_items_in["poDate"] = original_req_date
        else:
            order_items_inx["targetQty"] = order_line.quantity != param_quantity
            order_items_inx["plant"] = order_line.plant != input_item.get("plant")
            order_items_inx["updateflag"] = "U"
        param_order_items_in.append(order_items_in)
        param_order_items_in_x.append(order_items_inx)

        # build param for field: orderSchedulesIn
        param_confirm_quantity = input_item.get("on_hand_stock") and param_quantity or 0
        param_req_date = DateHelper.iso_str_to_sap_str(input_item.get("confirm_date"))
        param_order_schedules_in.append(
            {
                "itemNo": param_item_no,
                "scheduleLine": "0001",
                "reqDate": param_req_date,
                "reqQty": param_request_quantity,
                "confirmQty": param_confirm_quantity,
            }
        )

        # build param for field: orderSchedulesInx
        param_order_schedules_in_x.append(
            {
                "itemNo": param_item_no,
                "updateflag": "I" if is_new_order_line else "U",
                "scheduleLine": "0001",
                "requestDate": is_new_order_line
                or (param_req_date != original_param_req_date),
                "requestQuantity": is_new_order_line
                or (param_request_quantity != order_line.quantity),
                "confirmQuantity": True,
            }
        )

    # full body
    body = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderItemsIn": param_order_items_in,
        "orderItemsInx": param_order_items_in_x,
        "orderSchedulesIn": param_order_schedules_in,
        "orderSchedulesInx": param_order_schedules_in_x,
    }
    return body


def _update_db(input_items):
    old_order_lines = []
    old_iplans = []
    new_order_lines = []
    new_iplans = []
    for input_item in input_items:
        original_order_line = input_item.get("order_line_instance")

        order_line = deepcopy(original_order_line)
        iplan = order_line.iplan
        _set_iplan_fields(iplan, input_item)
        _set_order_line_fields(order_line, iplan, input_item)

        item_no_parts = input_item.get("item_no").split(".")
        if len(item_no_parts) > 1 and int(item_no_parts[1].lstrip("0")) > 1:
            # case item no like: 10.002, 10.003, ...
            order_line.id = None
            iplan.id = None
            new_order_lines.append(order_line)
            new_iplans.append(iplan)
        else:
            # case item no like 10.001, 20.001
            old_order_lines.append(order_line)
            old_iplans.append(iplan)

    # save to db
    with transaction.atomic():
        _bulk_update_iplans(old_iplans)
        _bulk_update_order_lines(old_order_lines)
        _bulk_create_order_lines_and_iplans(new_order_lines, new_iplans)
        update_status_for_order(old_order_lines[0].order)
        update_field_item_no_latest_for_order(old_order_lines + new_order_lines)
    return old_order_lines, new_order_lines


def _set_iplan_fields(iplan, input_item):
    # exists case that iplan return dispatchDate = ""
    if iplant_confirm_date := (input_item.get("confirm_date") or None):
        iplant_confirm_date = DateHelper.iso_str_to_obj(input_item.get("confirm_date"))

    iplan.item_no = input_item.get("calculated_item_no")
    iplan.item_status = input_item.get("atp_ctp_detail")
    iplan.iplant_confirm_quantity = input_item.get("quantity")
    iplan.iplant_confirm_date = iplant_confirm_date
    iplan.order_type = input_item.get("atp_ctp")
    iplan.plant = input_item.get("plant")
    iplan.on_hand_stock = input_item.get("on_hand_stock")
    iplan.block = input_item.get("block_code")
    iplan.run = input_item.get("run_code")
    iplan.paper_machine = input_item.get("paper_machine")
    iplan.request_iplan_response = None

    # TODO: remove these field when refactor old code
    # these field are redundancy, but to compatible with old code, we have to set it too.
    iplan.original_date = iplant_confirm_date
    iplan.atp_ctp_detail = input_item.get("atp_ctp")
    iplan.atp_ctp = input_item.get("atp_ctp").split(" ")[0].upper()


def _set_order_line_fields(order_line, iplan, input_item):
    order_line.item_no = iplan.item_no
    order_line.request_date = DateHelper.iso_str_to_obj(
        input_item.get("original_request_date")
    )
    # TODO: has some field redundant between orderline and iplan, should migrate to use in iplan model
    order_line.quantity = float(input_item.get("quantity"))
    order_line.return_status = iplan.item_status  # redundant
    order_line.plant = iplan.plant  # redundant

    # TODO: handle when migrate to use iplan.order_type to check atp/ctp type
    order_line.i_plan_on_hand_stock = input_item.get(
        "on_hand_stock"
    )  # this one used in SEO-1181
    order_line.i_plan_operations = {
        "blockCode": input_item.get("block_code")
    }  # this one used in SEO-1181

    set_status_for_order_line(order_line)


def _bulk_update_iplans(iplans):
    OrderLineIPlan.objects.bulk_update(
        iplans,
        fields=[
            "item_no",
            "item_status",
            "iplant_confirm_quantity",
            "iplant_confirm_date",
            "order_type",
            "plant",
            "on_hand_stock",
            "block",
            "run",
            "paper_machine",
            "request_iplan_response",
            "original_date",
            "atp_ctp_detail",
            "atp_ctp",
        ],
    )


def _bulk_update_order_lines(order_lines):
    OrderLines.objects.bulk_update(
        order_lines,
        fields=[
            "item_no",
            "request_date",
            "quantity",
            "return_status",
            "plant",
            "i_plan_on_hand_stock",
            "i_plan_operations",
            "item_status_en",
            "item_status_th",
            "item_status_en_rollback",
        ],
    )


def _bulk_create_order_lines_and_iplans(order_lines, iplans):
    iplans = OrderLineIPlan.objects.bulk_create(iplans)
    item_no_to_iplan = {iplan.item_no: iplan for iplan in iplans}
    for order_line in order_lines:
        order_line.iplan = item_no_to_iplan.get(order_line.item_no)

    OrderLines.objects.bulk_create(order_lines)


def _inject_new_line_id_to_input_items(input_items, new_order_lines):
    # inject new order line id to return for FE
    item_no_to_order_line = {line.item_no: line for line in new_order_lines}
    for input_item in input_items:
        item_no = input_item.get("calculated_item_no")
        if item_no in item_no_to_order_line:
            input_item["line_id"] = item_no_to_order_line[item_no].id


def _update_flag_R5(order_lines, i_plan_error_messages):
    failed_order_lines = []
    item_no_to_order_line = {line.item_no: line for line in order_lines}
    for message in i_plan_error_messages:
        item_no = message.get("item_no")
        if order_line := item_no_to_order_line.get(item_no):
            failed_order_lines.append(order_line)

    if failed_order_lines:
        update_attention_type_r5(failed_order_lines)


def _set_instance_fields(instance, data):
    for field_name, value in data.items():
        setattr(instance, field_name, value)


def _delete_iplan_response(iplans):
    for iplan in iplans:
        iplan.request_iplan_response = None

    OrderLineIPlan.objects.bulk_update(iplans, fields=["request_iplan_response"])


def _set_item_status_for_new_order_line(order_line):
    order_line.item_status_en = IPlanOrderItemStatus.ITEM_CREATED.value
    order_line.item_status_th = (
        IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            IPlanOrderItemStatus.ITEM_CREATED.value
        )
    )
    order_line.item_status_en_rollback = None


def update_item_no_latest(order, order_lines):
    current_item_no_latest = int(order.item_no_latest) or 0
    item_no_latest = 0
    for order_line in order_lines:
        item_no_latest = max(int(order_line.item_no), item_no_latest)

    item_no_latest = max(current_item_no_latest, item_no_latest)
    if order.item_no_latest != str(item_no_latest):
        order.item_no_latest = str(item_no_latest)
        order.save()
    return order.item_no_latest


def _set_calculated_item_no(item_no_latest, input_items):
    item_no_latest = int(item_no_latest)
    for input_item in input_items:
        item_no_parts = input_item.get("item_no").split(".")
        if len(item_no_parts) > 1 and int(item_no_parts[1].lstrip("0")) > 1:
            # case item no like: 10.002, 10.003, ...
            item_no_latest += 10
            input_item["calculated_item_no"] = str(item_no_latest)
        else:
            # case item no like 10.001, 20.001
            input_item["calculated_item_no"] = item_no_parts[0]


def _inject_calculated_item_no_to_input_items(order, order_lines, input_items):
    item_no_latest = update_item_no_latest(order, order_lines)
    _set_calculated_item_no(item_no_latest, input_items)


def rollback_input_items(input_items):
    rollback_items = []
    for input_item in input_items:
        order_line_instance = input_item.pop("order_line_instance")
        iplan = order_line_instance.iplan

        input_item["quantity"] = str(order_line_instance.quantity)
        input_item["confirm_date"] = str(iplan.iplant_confirm_date)
        input_item["plant"] = order_line_instance.plant
        input_item["atp_ctp"] = iplan.atp_ctp
        input_item["atp_ctp_detail"] = iplan.atp_ctp_detail
        input_item["block_code"] = iplan.block
        input_item["run_code"] = iplan.run
        input_item["paper_machine"] = iplan.paper_machine
        input_item["original_quantity"] = order_line_instance.quantity
        input_item["original_request_date"] = str(order_line_instance.request_date)
        input_item["original_plant"] = order_line_instance.plant
        input_item["on_hand_stock"] = iplan.on_hand_stock

        rollback_items.append(input_item)

    return rollback_items


list_item_fields = [
    "item_no",
    "quantity",
    "confirm_date",
    "plant",
    "atp_ctp",
    "atp_ctp_detail",
    "block_code",
    "run_code",
    "paper_machine",
    "unit",
    "on_hand_stock",
    "order_type",
]


def _transform_data_to_return(_items):
    items = deepcopy(_items)
    rs = {}
    for item in items:
        original_item_no = item["original_item_no"]
        if original_item_no not in rs:
            rs[original_item_no] = item

        if item["item_no"] == "-" or item["item_no"].split(".")[0] == original_item_no:
            rs[original_item_no].setdefault("list_items", []).append(
                {field: item.get(field) for field in list_item_fields}
            )
    rs = rs.values()
    for item in rs:
        item["list_items"].sort(key=lambda it: _sort_by_item_no_key(it["item_no"]))
    return rs


def _transform_data_to_input(items):
    rs = []
    for item in items:
        for response_item in item["list_items"]:
            new_item = deepcopy(item)
            for field in response_item.keys():
                new_item[field] = response_item[field]
            rs.append(new_item)
    return rs


def _sort_by_item_no_key(item_no):
    if item_no == "-":
        return -1

    item_no_parts = item_no.split(".")
    if len(item_no_parts) > 1:
        return int(item_no_parts[1].lstrip("0"))
    else:
        return int(item_no)


def _update_db_after_commit_success(order_lines):
    for order_line in order_lines:
        iplan = order_line.iplan
        order_line.confirmed_date = iplan.iplant_confirm_date  # redundant
        order_line.assigned_quantity = order_line.quantity if iplan.on_hand_stock else 0

    OrderLines.objects.bulk_update(
        order_lines, fields=["confirmed_date", "assigned_quantity"]
    )
