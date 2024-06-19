import datetime
from typing import Any, TypedDict

import graphene

from sap_migration.models import OrderLines
from scg_checkout.graphql.enums import ProductionStatus


class EOrderingProductionStatus(graphene.Enum):
    BEFORE_PRODUCTION = "BEFORE PRODUCTION"
    DURING_PRODUCTION = "DURING PRODUCTION"
    AFTER_PRODUCTION = "AFTER PRODUCTION"


class ItemLevelUpdateField(TypedDict):
    request_date: datetime.date
    quantity: Any
    plant: str


def get_item_production_status(item: OrderLines):
    is_ctp = False
    if not item.i_plan_on_hand_stock and item.i_plan_operations:
        is_ctp = True

    if not is_ctp:
        return EOrderingProductionStatus.BEFORE_PRODUCTION

    production_status = item.production_status
    production_status_rank = ProductionStatus.STATUS_RANK.value
    if production_status not in production_status_rank:
        return EOrderingProductionStatus.BEFORE_PRODUCTION

    if production_status_rank.index(production_status) < production_status_rank.index(
        ProductionStatus.CLOSE_RUN.value
    ):
        return EOrderingProductionStatus.BEFORE_PRODUCTION

    if production_status_rank.index(production_status) < production_status_rank.index(
        ProductionStatus.COMPLETED.value
    ):
        return EOrderingProductionStatus.DURING_PRODUCTION

    if production_status_rank.index(production_status) == production_status_rank.index(
        ProductionStatus.COMPLETED.value
    ):
        return EOrderingProductionStatus.AFTER_PRODUCTION

    return None


def get_product_code(line):
    if line.material_variant_id is not None:
        return line.material_variant.code
    elif line.material_code is not None:
        return line.material_code
    else:
        return ""


def get_product_and_ddq_alt_prod_of_order_line(
    alt_mat_i_plan_dict, order, order_line, is_po_upload=False, item_data_from_file=None
):
    alternate_products = list()
    if is_po_upload:
        if order_line.material_variant:
            product_code = order_line.material_variant.code
        elif item_data_from_file:
            product_code = item_data_from_file.get("sku_code")
    else:
        product_code = get_product_code(order_line)

    key = f"{order.id}_{order_line.item_no}"
    if order_line.material_variant:
        alt_mat_codes = alt_mat_i_plan_dict.get(key, {}).get("alt_mat_codes", [])
        if alt_mat_codes:
            product_code = alt_mat_codes[0]
            if len(alt_mat_codes) > 1:
                for alt_mat in alt_mat_codes[1:]:
                    alternate_products.append({"alternateProductCode": alt_mat})
    return alternate_products, product_code
