import logging

from sap_migration.models import Order
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_create_order,
)
from scgp_cip.common.constants import BOM_FLAG_TRUE_VALUE, REASON_REJECT
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.graphql.order.types import OrderHeaderPriceInfo
from scgp_cip.service.helper.create_order_helper import derive_order_partners
from scgp_cip.service.sap import call_sap_es_41


def derive_price_summary_using_es_41(info, input_data):
    order_db: Order = OrderRepo.get_order_by_id(input_data["id"])
    order_lines_db = OrderLineRepo.find_all_order_line_by_order(order_db)
    order_information_in: OrderHeaderPriceInfo = input_data.get("input").get(
        "order_information"
    )
    lines_in = input_data.get("input").get("lines", [])
    lines_in = sorted(lines_in, key=lambda x: int(x["item_no"]))
    item_no_order_line_db = {line.item_no: line for line in order_lines_db}
    item_ship_to_dict = {
        line_in.item_no: line_in.get("ship_to", "") for line_in in lines_in
    }

    # Order partners derivation
    order_partners = derive_order_partners(
        order_db.sold_to.sold_to_code,
        order_information_in.sales_employee,
        order_information_in.bill_to,
        order_information_in.ship_to,
        item_ship_to_dict,
    )
    response = call_sap_es_41(
        lines_in,
        order_db,
        order_information_in,
        order_partners,
        item_no_order_line_db,
    )
    logging.info(f"[No Ref Contract - Price Calculator] ES41 Response : {response}")
    derive_parent_item_price(response)
    (
        sap_success,
        sap_order_messages,
        sap_item_messages,
        sap_errors_code,
        order_header_msg,
        is_being_process,
        is_items_error,
        order_item_message,
    ) = get_error_messages_from_sap_response_for_create_order(response)
    return response, sap_order_messages, sap_item_messages, sap_success


def derive_parent_item_price(response):
    order_items_res = response and response.get("orderItemsOut", [])
    if order_items_res:
        parent_item_no_child_price_dict = {}
        for item in order_items_res:
            if (
                BOM_FLAG_TRUE_VALUE == item.get("bomFlag")
                and item.get("parentItemNo")
                and str(item.get("rejectReason", "")) != REASON_REJECT
            ):
                price_dict = parent_item_no_child_price_dict.setdefault(
                    item.get("parentItemNo"), {"price_per_unit": 0, "total_price": 0}
                )
                price_dict["price_per_unit"] += item.get("netPricePerUnit")
                price_dict["total_price"] += item.get("netValue")
        for item in order_items_res:
            if BOM_FLAG_TRUE_VALUE == item.get("bomFlag") and not item.get(
                "parentItemNo"
            ):
                item.update(
                    {
                        "netPricePerUnit": parent_item_no_child_price_dict.get(
                            item.get("itemNo"), {}
                        ).get("total_price", 0)
                        / item.get("targetQuantity", 1)
                    }
                )
                item.update(
                    {
                        "netValue": parent_item_no_child_price_dict.get(
                            item.get("itemNo"), {}
                        ).get("total_price", 0)
                    }
                )
