import logging
from copy import deepcopy
from typing import Tuple, TypedDict, Union

from django.db import transaction

from common.atp_ctp.enums import AtpCtpStatus
from common.enum import EorderingItemStatusEN, EorderingItemStatusTH
from common.helpers import mock_confirm_date
from common.require_attention.helpers import add_flag_attention
from sap_migration.graphql.enums import InquiryMethodType, OrderType
from sap_migration.models import Order, OrderLineIPlan, OrderLines
from scg_checkout.graphql.enums import IPlanOrderItemStatus
from scg_checkout.graphql.helper import update_order_status
from scgp_export.implementations.atp_ctp import _update_flag_R5

ITEM_INPUT_MAP_WITH_MODEL = {
    "ref_pi_no": "ref_pi_stock",
    "inquiry_method": "inquiry_method",
    "roll_diameter": "roll_diameter",
    "roll_core_diameter": "roll_core_diameter",
    "roll_per_pallet": "roll_per_pallet",
    "package_quantity": "package_quantity",
    "pallet_size": "pallet_size",
    "pallet_no": "pallet_no",
    "packing_list": "packing_list",
    "request_date": "request_date",
    "shipping_mark": "shipping_mark",
    "quantity": "quantity",
}

ORDERLINE_IPLAN_DATA_UPDATE_FIELDS = [
    "assigned_quantity",
    "i_plan_on_hand_stock",
    "i_plan_operations",
    "confirmed_date",
    "item_status_en",
    "item_status_th",
]

IPLAN_UPDATE_FIELDS = [
    "atp_ctp",
    "atp_ctp_detail",
    "iplant_confirm_quantity",
    "on_hand_stock",
    "item_status",
    "plant",
    "iplant_confirm_date",
    "request_type",
    "order_type",
]


class EditOrderData(TypedDict):
    item_no: str
    iplan_item_no: Union[str, None]
    db_item: OrderLines
    item_input_data: dict
    iplan_item: Union[dict, None]
    update_flag: str
    _from: str


def update_iplan_item(
    order_line_iplan: OrderLineIPlan,
    iplan_item: dict,
    order_line: OrderLines,
    item_schedule_out: dict,
    item_update_flag,
) -> None:
    iplan_on_handstock = iplan_item.get("onHandStock", order_line_iplan.on_hand_stock)
    iplan_operation = iplan_item.get("DDQResponseOperation", [])
    status = iplan_item.get("status", "")

    if iplan_operation:
        iplan_operation = iplan_operation[0]
    else:
        iplan_operation = None
    order_type = iplan_item.get("orderType", order_line_iplan.order_type)

    order_line_iplan.atp_ctp = order_type.split(" ")[0]
    order_line_iplan.atp_ctp_detail = order_type
    order_line_iplan.iplant_confirm_quantity = iplan_item.get(
        "quantity", order_line_iplan.iplant_confirm_quantity or 0
    )
    order_line_iplan.on_hand_stock = iplan_on_handstock
    order_line_iplan.item_status = iplan_item.get(
        "status", order_line_iplan.item_status
    )
    order_line_iplan.plant = iplan_item.get("warehouseCode", order_line_iplan.plant)
    order_line_iplan.fix_source_assignment = iplan_item.get(
        "warehouseCode", order_line_iplan.fix_source_assignment
    )

    if iplan_item:
        dispatch_date = iplan_item.get("dispatchDate", None)
        if not dispatch_date:
            dispatch_date = mock_confirm_date(order_line.request_date, status)
        order_line.confirmed_date = dispatch_date
        order_line.request_date = order_line.request_date
        order_line_iplan.iplant_confirm_date = order_line.confirmed_date

    order_line_iplan.order_type = order_type
    order_line_iplan.request_type = "AMENDMENT" if item_update_flag == "U" else "NEW"

    if not iplan_on_handstock:
        order_line.assigned_quantity = 0
    if iplan_on_handstock and order_type != "CTP":
        order_line.assigned_quantity = item_schedule_out.get("confirmQuantity", None)

    order_line.i_plan_on_hand_stock = iplan_on_handstock
    order_line.i_plan_operations = iplan_operation
    if order_type == AtpCtpStatus.ATP_ON_HAND.value:
        order_line.item_status_en = EorderingItemStatusEN.FULL_COMMITTED_ORDER.value
        order_line.item_status_th = EorderingItemStatusTH.FULL_COMMITTED_ORDER.value
    if order_type == AtpCtpStatus.ATP_FUTURE.value:
        order_line.item_status_en = EorderingItemStatusEN.PLANNING_OUTSOURCING.value
        order_line.item_status_th = EorderingItemStatusTH.PLANNING_OUTSOURCING.value
    if order_type == AtpCtpStatus.CTP.value:
        order_line.item_status_en = EorderingItemStatusEN.ITEM_CREATED.value
        order_line.item_status_th = EorderingItemStatusTH.ITEM_CREATED.value


def update_item_after_yt65156(order_items: list) -> None:
    update_order_lines = []
    update_order_line_iplans = []
    for item in order_items:
        item_input_data = item.get("item_input_data", None)
        item_schedule_out = item.get("item_schedule_out", {})
        item_update_flag = item.get("update_flag")
        iplan_item = item.get("iplan_item", {})
        order_line: OrderLines = item.get("db_item", None)
        order_line_iplan: OrderLineIPlan = order_line.iplan if order_line else None
        if not item_input_data:
            continue
        for model_update_key, item_input_key in ITEM_INPUT_MAP_WITH_MODEL.items():
            model_field_data = getattr(order_line, model_update_key, None)
            updated_data = item_input_data.get(item_input_key, model_field_data)
            setattr(order_line, model_update_key, updated_data)

        if iplan_item and order_line_iplan:
            update_iplan_item(
                order_line_iplan,
                iplan_item,
                order_line,
                item_schedule_out,
                item_update_flag,
            )
            update_order_line_iplans.append(order_line_iplan)
        else:
            # if not container and special plant then update confirm date = request date
            # SEO-5852: For items which are not updated by user dates shouldn't be changed
            if order_line.item_cat_eo == "ZKC0":
                order_line.confirmed_date = None
            elif OrderType.EXPORT.value == order_line.type and (
                order_line.plant in ["754F", "7531", "7533"]
            ):
                order_line.confirmed_date = item_input_data.get("request_date")
        update_order_lines.append(order_line)

    OrderLines.objects.bulk_update(
        update_order_lines,
        list(ITEM_INPUT_MAP_WITH_MODEL.keys()) + ORDERLINE_IPLAN_DATA_UPDATE_FIELDS,
    )
    OrderLineIPlan.objects.bulk_update(update_order_line_iplans, IPLAN_UPDATE_FIELDS)


def create_new_item_after_yt65216(order_items: list) -> None:
    new_order_lines = []

    for item in order_items:
        item_input_data = item.get("item_input_data", None)
        iplan_item = item.get("iplan_item", {})
        schedule_out = item.get("item_schedule_out", {})
        item_update_flag = item.get("update_flag")
        order_line: OrderLines = item.get("db_item", None)
        if order_line:
            order_line.refresh_from_db()

        new_order_line = deepcopy(order_line)
        new_order_line.pk = None
        new_order_line.item_no = str(item.get("item_no"))
        new_order_line.original_item_no = item.get("iplan_item_no")
        new_order_line.inquiry_method = InquiryMethodType.EXPORT.value

        if item_input_data:
            for model_update_key, item_input_key in item_input_data.items():
                model_field_data = getattr(new_order_line, model_update_key, None)
                updated_data = item_input_data.get(item_input_key, model_field_data)
                setattr(new_order_line, model_update_key, updated_data)
        new_order_line.production_status = None
        new_order_line.item_status_en = IPlanOrderItemStatus.ITEM_CREATED.value
        new_order_line.item_status_th = (
            IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
                IPlanOrderItemStatus.ITEM_CREATED.value
            )
        )
        new_order_line_iplan = deepcopy(
            order_line.iplan if order_line else OrderLineIPlan()
        )
        new_order_line_iplan.pk = None
        update_iplan_item(
            new_order_line_iplan,
            iplan_item,
            new_order_line,
            schedule_out,
            item_update_flag,
        )
        new_order_line_iplan.save()
        new_order_line.iplan = new_order_line_iplan
        new_order_lines.append(new_order_line)
    OrderLines.objects.bulk_create(new_order_lines)


def flag_r5_failed_items(item_no_lst, split=False):
    if split:
        order_lines = OrderLines.objects.filter(id__in=item_no_lst).all()
    else:
        order_lines = OrderLines.objects.filter(item_no__in=item_no_lst).all()
    for order_line in order_lines:
        add_flag_attention(order_line, ["R5"])

    OrderLines.objects.bulk_update(order_lines, ["attention_type"])


@transaction.atomic
def update_order_after_request_mulesoft(
    order: Order,
    order_header_input: dict,
    data: list,
    failed_item_no: list,
    order_items: OrderLines,
) -> bool:
    def _get_item_by_process(
        data: list,
    ) -> Tuple[list, list, list]:
        item_call_yt65156_update = []
        item_call_yt65156_new = []
        item_call_yt65217 = []

        for item in data:
            if item["update_flag"] == "U":
                item_call_yt65156_update.append(item)
            elif item["update_flag"] == "I":
                item_call_yt65156_new.append(item)
        return (
            item_call_yt65156_update,
            item_call_yt65156_new,
            item_call_yt65217,
        )

    try:
        if (
            order_header_input
            and (ref_pi_no := order_header_input.get("ref_pi_no", None)) is not None
        ):
            order.ref_pi_no = ref_pi_no
        (
            items_call_yt65156_update,
            items_call_yt65156_new,
            items_call_yt65217,
        ) = _get_item_by_process(data)
        update_item_after_yt65156(items_call_yt65156_update)
        create_new_item_after_yt65216(items_call_yt65156_new)
        status_en, status_thai = update_order_status(order.pk)
        logging.info(
            f"[Export change order] order {order.so_no}, DB status:{order.status} updated to: {status_en}"
        )
        order.status = status_en
        order.status_thai = status_thai
        _update_flag_R5(order_items, failed_item_no)
        order.save()
        return True
    except Exception:
        transaction.set_rollback(True)
        return False
