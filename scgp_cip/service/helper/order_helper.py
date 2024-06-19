import uuid

from scgp_cip.common.constants import CIP, REASON_REJECT
from scgp_cip.common.enum import (
    CIPOrderItemStatus,
    CIPOrderTypes,
    ES26ItemStatus,
    PPOrderTypes,
)


def get_line_status_from_es26_cip(es26_order_line, item_status_count_dict):
    delivery_status = es26_order_line.get("deliveryStatus", "")
    status = es26_order_line.get("status", "")
    reason_reject = es26_order_line.get("reasonReject", "")
    list_status_th = CIPOrderItemStatus.CIP_ORDER_LINES_STATUS_TH.value

    if (
        status == ES26ItemStatus.COMPLETED_OR_CANCELLED.value
        and str(reason_reject) == REASON_REJECT
    ):
        item_status_count_dict["cancelled_item_count"] += 1
        return {
            "item_status_en": CIPOrderItemStatus.CANCEL.value,
            "item_status_th": list_status_th.get(CIPOrderItemStatus.CANCEL.value),
        }

    if delivery_status == status:
        if status == ES26ItemStatus.PARTIAL_DELIVERY.value:
            item_status_count_dict["partial_deliver_item_count"] += 1
            return {
                "item_status_en": CIPOrderItemStatus.PARTIAL_DELIVERY.value,
                "item_status_th": list_status_th.get(
                    CIPOrderItemStatus.PARTIAL_DELIVERY.value
                ),
            }

        if status == ES26ItemStatus.COMPLETED_OR_CANCELLED.value:
            item_status_count_dict["completed_item_count"] += 1
            return {
                "item_status_en": CIPOrderItemStatus.COMPLETE_DELIVERY.value,
                "item_status_th": list_status_th.get(
                    CIPOrderItemStatus.COMPLETE_DELIVERY.value
                ),
            }
        if status == ES26ItemStatus.CREATED.value or status == "":
            return {
                "item_status_en": CIPOrderItemStatus.ITEM_CREATED.value,
                "item_status_th": list_status_th.get(
                    CIPOrderItemStatus.ITEM_CREATED.value
                ),
            }
    return {}


def derive_order_status(item_status_count_dict, order_item_count):
    if item_status_count_dict.get("cancelled_item_count", 0) >= order_item_count:
        return CIPOrderItemStatus.CANCEL.value
    if item_status_count_dict.get("partial_deliver_item_count", 0) > 0:
        return CIPOrderItemStatus.PARTIAL_DELIVERY.value
    if (
        item_status_count_dict.get("completed_item_count")
        + item_status_count_dict.get("cancelled_item_count")
        >= order_item_count
    ):
        return CIPOrderItemStatus.COMPLETE_DELIVERY.value
    return CIPOrderItemStatus.RECEIVED_ORDER.value


def prepare_payload_ots(input_data, info):
    material_description_list = input_data.get("material_no_material_description")
    params = {
        "requestId": str(uuid.uuid1().int),
        "customer": input_data.get("sold_to"),
        "material": material_description_list[0] if material_description_list else "",
        "createDateFrom": str(input_data.get("create_date", {}).get("gte", "")) or None,
        "createDateTo": str(input_data.get("create_date", {}).get("lte", "")) or None,
        "poNo": input_data.get("purchase_order_no", ""),
        "salesOrders": input_data.get("so_no")
        if input_data.get("so_no")
        else input_data.get("sale_order_no", ""),
        "plant": input_data.get("plant", ""),
        "shipTo": input_data.get("ship_to", ""),
        "webUserId": str(info.context.user.id),
        "orderType": get_ots_order_type(input_data),
    }
    return params


def get_ots_order_type(input_data):
    order_type = input_data.get("order_type")
    if order_type == "All":
        order_types = CIPOrderTypes if CIP == input_data.get("bu") else PPOrderTypes
        return [order_type.name for order_type in order_types.__enum__]
    return [order_type] if order_type else []
