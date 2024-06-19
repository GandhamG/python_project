from typing import Callable, List, Optional, Tuple

from django.core.exceptions import ValidationError

from common.iplan.item_level_helpers import get_item_production_status
from sap_migration.models import Order, OrderLines
from scgp_export.error_codes import ScgpExportErrorCode
from scgp_export.graphql.enums import ScgpExportOrderStatus


def validate_order_exists(order):
    if not order:
        raise ValidationError(
            "order not found.",
            code=ScgpExportErrorCode.NOT_FOUND.value,
        )


def validate_cannot_change_order(order):
    if order.status == ScgpExportOrderStatus.CONFIRMED.value:
        raise ValidationError(
            "cannot change order due to order has been confirmed",
            code=ScgpExportErrorCode.INVALID.value,
        )


def validate_item_during_production(
    item: OrderLines, item_input_data: dict
) -> Tuple[bool, Optional[str]]:
    if item.plant != item_input_data.get("plant", ""):
        return False, "Cannot change plant of item during production"

    assigned_quantity = item.assigned_quantity or 0
    item_quantity = item.quantity
    input_quantity = item_input_data.get("quantity", 0)
    if input_quantity < assigned_quantity:
        return False, "โปรดระบุจำนวนให้มากกว่า assigned quantity"

    if input_quantity > item_quantity:
        return False, "ไม่สามารถเพิ่มจำนวนได้"

    return True, None


def validate_item_after_production(
    item: OrderLines, item_input_data: dict
) -> Tuple[bool, Optional[str]]:
    if item.plant != item_input_data.get("plant", ""):
        return False, "Cannot change plant of item after production"
    item_quantity = item.quantity
    input_quantity = item_input_data.get("quantity", 0)

    if input_quantity > item_quantity:
        return False, "ไม่สามารถเพิ่มจำนวนได้"

    return True, None


def validate_item_level(
    order_items: List[OrderLines],
    dict_order_items_update: dict,
    func: Callable[[OrderLines, dict], Tuple[bool, Optional[str]]],
) -> None:
    for item in order_items:
        item_input_data = dict_order_items_update.get(str(item.pk), {})
        status, message = func(item, item_input_data)
        if not status:
            raise ValueError(message)


def validate_edit_order(
    order: Order,
    order_items: dict,
    order_item_input_data: dict,
):
    validate_order_exists(order)
    validate_cannot_change_order(order)
    items_with_production_status = {
        "BEFORE PRODUCTION": [],
        "DURING PRODUCTION": [],
        "AFTER PRODUCTION": [],
    }

    for item in order_items.values():
        items_with_production_status[get_item_production_status(item).value].append(
            item
        )
    validate_item_level(
        items_with_production_status["DURING PRODUCTION"],
        order_item_input_data,
        validate_item_during_production,
    )
    validate_item_level(
        items_with_production_status["AFTER PRODUCTION"],
        order_item_input_data,
        validate_item_after_production,
    )
