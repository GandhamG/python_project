import logging
import uuid

from common.mulesoft_api import MulesoftApiRequest
from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import ScgpClassMarkData
from scg_checkout.graphql.resolves.orders import call_sap_es26
from scgp_export.graphql.enums import SapEnpoint, TextID
from scgp_require_attention_items.graphql.enums import ScgpRequireAttentionTypeData
from scgp_require_attention_items.graphql.helper import append_field


def gen_param_es21_class_mark(order_lines):

    order = order_lines[0].order
    param = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no.lstrip("0"),
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": order.contract.code,
        },
        "orderItemsIn": [],
        "orderItemsInX": [],
        "orderText": [],
    }
    update_order_lines_with_ref_doc_it(order, order_lines)
    # update class mark (Z020) to sap
    for order_line in order_lines:
        # order item
        order_item = {
            "itemNo": order_line.item_no,
            "material": order_line.material_code,
            "refDoc": order.contract.code,
            "refDocIt": order_line.ref_doc_it,
        }
        param["orderItemsIn"].append(order_item)

        order_item_x = {"itemNo": order_line.item_no, "updateflag": "U"}
        param["orderItemsInX"].append(order_item_x)

        # order text
        order_text = {
            "itemNo": order_line.item_no,
            "language": "EN",
            "textId": TextID.ITEM_REMARK.value,
            "textLineList": [{"textLine": order_line.class_mark}],
        }
        param["orderText"].append(order_text)

    return param


def update_order_lines_with_ref_doc_it(order, order_lines):
    # Prod issue SEO-6394
    is_ref_doc_it_null = False
    for order_line in order_lines:
        if not order_line.ref_doc_it:
            is_ref_doc_it_null = True
            break
    if is_ref_doc_it_null:
        logging.info("order number :", order.so_no)
        es26_response = call_sap_es26(order.so_no, None)
        _order_lines_from_es26 = es26_response["data"][0]["orderItems"]
        order_lines_map = {}
        update_order_lines = []
        for order_line in _order_lines_from_es26:
            order_lines_map[order_line.get("itemNo").lstrip("0")] = order_line.get(
                "contractItemNo", None
            )
        for order_line in order_lines:
            order_line.ref_doc_it = order_lines_map.get(order_line.item_no)
            update_order_lines.append(order_line)
        sap_migration_models.OrderLines.objects.bulk_update(
            update_order_lines, fields=["ref_doc_it"]
        )


def update_order_line_value(order_line_value, new_value):
    if not order_line_value:
        return new_value
    if new_value not in order_line_value:
        return ", ".join(
            sorted(
                map(lambda x: x.strip(), f"{order_line_value}, {new_value}".split(","))
            )
        )
    return order_line_value


def class_mark_logic(
    order_line,
    confirm_available_to_date,
    original_confirmed_date,
    dict_order_line_update_class_mark,
):
    if confirm_available_to_date > original_confirmed_date:
        order_line.attention_type = update_order_line_value(
            order_line.attention_type, ScgpRequireAttentionTypeData.R1.value
        )
        update_class_mark_to_order_line(order_line, ScgpClassMarkData.C2.value)
        if order_line.order not in dict_order_line_update_class_mark:
            dict_order_line_update_class_mark[order_line.order] = []
        dict_order_line_update_class_mark[order_line.order].append(order_line)


def update_class_mark_to_sap(dict_order_lines):
    if not dict_order_lines:
        return
    for order_lines in dict_order_lines.values():
        order = order_lines[0].order
        if order_lines[0].type == "export":
            if not order.contract:
                logging.warning(
                    "Order %s has no contract, cannot update_class_mark_to_sap"
                    % order.so_no
                )
                continue
            param = gen_param_es21_class_mark(order_lines)
            MulesoftApiRequest.instance(service_type="sap").request_mulesoft_post(
                SapEnpoint.ES_21.value, param
            )


def update_class_mark_to_order_line(order_line, value):
    if not value:
        return
    value_class_mark = order_line.class_mark
    value_class_mark = append_field(value_class_mark, value)
    order_line.class_mark = value_class_mark
