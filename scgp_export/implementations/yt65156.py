import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Tuple

from common.enum import MulesoftServiceType
from common.helpers import dictgetattrd
from common.iplan.iplan_api import IPlanApiRequest
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data.models import SoldToPartnerAddressMaster
from sap_migration.graphql.enums import OrderType
from sap_migration.models import Order, OrderLines
from scg_checkout.graphql.implementations.iplan import (
    change_parameter_inquiry_method,
    get_contract_consignment_location_from_order,
)
from scgp_export.graphql.enums import IPlanEndPoint


def get_parameter_follow_inquiry_method(
    item: OrderLines, order_type, input_inquiry_method
):
    input_inquiry_method = input_inquiry_method or item.inquiry_method
    params = change_parameter_inquiry_method(input_inquiry_method, order_type)

    return (
        params["inquiry_method"],
        params["use_inventory"],
        params["use_consignment_inventory"],
        params["use_projected_inventory"],
        params["use_production"],
        params["order_split_logic"],
        params["single_source"],
        params["re_atp_required"],
    )


def get_yt65156_request_update_line(
    order: Order,
    item: OrderLines,
    request_date: date = None,
    quantity: int = None,
    plant: str = "",
    input_inquiry_method: str = "",
    sourcing_cat: list = None,
) -> dict:
    item_no = item.item_no.lstrip("0")
    location_code = (
        order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
    ).lstrip("0") or None
    product_code = (
        item.material_variant.code if item.material_variant else item.material_code
    )
    request_date = (
        request_date.strftime("%Y-%m-%dT00:00:00.000Z")
        if request_date
        else item.request_date.strftime("%Y-%m-%dT00:00:00.000Z")
    )
    quantity = str(quantity or 0) if quantity else str(item.quantity or 0)
    consignment_location = get_contract_consignment_location_from_order(order)
    (
        inquiry_method,
        use_inventory,
        use_consignment_inventory,
        use_projected_inventory,
        use_production,
        order_split_logic,
        single_source,
        re_atp_required,
    ) = get_parameter_follow_inquiry_method(
        item, OrderType.EXPORT.value, input_inquiry_method
    )

    return {
        "inquiryMethod": inquiry_method,
        "useInventory": use_inventory,
        "useConsignmentInventory": use_consignment_inventory,
        "useProjectedInventory": use_projected_inventory,
        "useProduction": use_production,
        "orderSplitLogic": order_split_logic,
        "singleSourcing": single_source,
        "lineNumber": item_no,
        "locationCode": location_code,
        "productCode": product_code,
        "quantity": quantity,
        "typeOfDelivery": "E",
        "requestType": "AMENDMENT",
        "unit": "ROL",
        "transportMethod": "Truck",
        "reATPRequired": re_atp_required,
        "requestDate": request_date,
        "consignmentOrder": False,
        "consignmentLocation": consignment_location,
        "fixSourceAssignment": plant,
        "DDQSourcingCategories": sourcing_cat or [],
    }


def get_request_params_yt65156_update_export_items(
    order: Order, items: List[OrderLines], updated_data: dict
) -> dict:
    request_lines = []
    sourcing_cat = [
        {"categoryCode": order.sale_group_code},
        {"categoryCode": order.sale_org_code},
    ]
    for line in items:
        item_updated_data = updated_data.get(str(line.id))
        request_date = item_updated_data.get("request_date", None)
        quantity = item_updated_data.get("quantity", None)
        plant = item_updated_data.get("plant", None)
        inquiry_method = item_updated_data.get("inquiry_method", None)
        request_lines.append(
            get_yt65156_request_update_line(
                order, line, request_date, quantity, plant, inquiry_method, sourcing_cat
            )
        )

    return {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": [
                {
                    "headerCode": order.so_no.lstrip("0"),
                    "autoCreate": False,
                    "DDQRequestLine": sorted(
                        request_lines, key=lambda x: int(x["lineNumber"])
                    ),
                }
            ],
        }
    }


def is_item_need_to_request_iplan(item: OrderLines, order_item_data: dict) -> bool:
    update_fields = ["request_date", "quantity", "plant", "inquiry_method"]

    from ..graphql.mutations.constants import MATERIAL_OS_PLANT

    # If item is special plant or container, no need to request iplan
    if (
        order_item_data.get("plant", "") in MATERIAL_OS_PLANT
        or item.item_cat_eo == "ZKC0"
    ):
        return False
    for field in update_fields:
        item_model_data = getattr(item, field, None)
        order_item_field_data = getattr(order_item_data, field, None)
        if item_model_data != order_item_field_data:
            logging.info(
                f"[Export change order] checking for item updated fields by comparing DB value with FE value"
                f" item: {item.item_no} Field: {field},"
                f" db value: {item_model_data}, FE value: {order_item_field_data}"
            )
            return True
    return False


def get_iplan_request_line(iplan_response: Any) -> Dict[str, List]:
    from ..graphql.enums import IPlanResponseStatus

    dict_response_lines: Dict[str, list] = {e.value: [] for e in IPlanResponseStatus}
    response_headers = dictgetattrd(
        iplan_response, "DDQResponse.DDQResponseHeader", [None]
    )[0]
    if response_headers:
        response_lines = response_headers.get("DDQResponseLine")
        for line in response_lines:
            dict_response_lines[line.get("returnStatus", "")].append(line)

    return dict_response_lines


def handle_yt65156_request(
    order: Order, order_items_model: dict, order_items_updated_data: dict
) -> Tuple[dict, Dict[str, List]]:
    data = get_request_params_yt65156_update_export_items(
        order=order,
        items=order_items_model.values(),
        updated_data=order_items_updated_data,
    )

    response = IPlanApiRequest.call_yt65156_api(data=data, order=order)
    dict_response_lines = get_iplan_request_line(response)

    return response, dict_response_lines


def build_yt65156_confirm_line(
    order: Order,
    updated_order_header_data: dict,
    request_item: dict,
    order_schedule: dict,
):
    line_number = str(request_item.get("item_no"))
    original_line_number = request_item.get("iplan_item_no") or line_number
    iplan_request_item = request_item.get("iplan_item", {})
    on_hand_qty = 0
    if iplan_request_item.get("onHandStock", False):
        on_hand_qty = order_schedule.get("confirmQuantity", 0)

    unit = iplan_request_item.get("unit", "ROL")

    order_info_types = []
    shipping_mark = ""
    if updated_order_header_data:
        shipping_mark = updated_order_header_data.get("shipping_mark", "")
    if (not shipping_mark) and order:
        shipping_mark = order.shipping_mark
    if shipping_mark:
        order_info_types.append({"valueType": "ShippingMarks", "value": shipping_mark})

    if order.contract.code:
        order_info_types.append(
            {"valueType": "ProformaInvoice", "value": order.contract.code}
        )
    sold_to_code = order.sold_to.sold_to_code
    sold_to_partner = SoldToPartnerAddressMaster.objects.filter(
        partner_code=sold_to_code
    ).first()
    if sold_to_partner:
        sold_to_name = " ".join(
            filter(
                None,
                [
                    getattr(sold_to_partner, field, "")
                    for field in ["name1", "name2", "name3", "name4"]
                ],
            )
        )
        sold_to = f"{sold_to_code} - {sold_to_name}"

        order_info_types.append({"valueType": "SoldTo", "value": sold_to})

    ship_to_code = order.ship_to.split("-")[0].strip() if order.ship_to else None
    if ship_to_code:
        ship_to_partner = SoldToPartnerAddressMaster.objects.filter(
            partner_code=ship_to_code
        ).first()

        if ship_to_partner and ship_to_partner.country_code:
            order_info_types.append(
                {"valueType": "Country", "value": ship_to_partner.country_code}
            )

    line_data = {
        "lineNumber": line_number,
        "originalLineNumber": original_line_number,
        "onHandQuantityConfirmed": str(on_hand_qty),
        "unit": unit,
        "status": "COMMIT",
        "DDQOrderInformationType": [
            {"type": "CustomInfo", "DDQOrderInformationItem": order_info_types}
        ]
        if request_item.get("update_flag", "U") == "I"
        else [],
    }

    return line_data


def get_iplan_confirm_line(iplan_response: Any) -> Dict[str, List]:
    from ..graphql.enums import IPlanResponseStatus

    dict_response_lines: Dict[str, list] = {e.value: [] for e in IPlanResponseStatus}
    response_headers = dictgetattrd(
        iplan_response, "DDQAcknowledge.DDQAcknowledgeHeader", [None]
    )[0]
    if response_headers:
        response_lines = response_headers.get("DDQAcknowledgeLine")
        for line in response_lines:
            dict_response_lines[line.get("returnStatus", "")].append(line)

    return dict_response_lines


def handle_yt65156_confirm(
    order: Order,
    updated_order_header_data: dict,
    request_items: List,
    order_schedules_out: List,
):
    header_code: str = order.so_no.lstrip("0")
    confirm_lines = []
    for item in request_items:
        item_no = str(item.get("item_no", "")).zfill(6)
        order_schedule = list(
            filter(
                lambda order_schedule: order_schedule.get("itemNo", "") == item_no,
                order_schedules_out,
            )
        )

        order_schedule = order_schedule[0] or {}
        confirm_lines.append(
            build_yt65156_confirm_line(
                order=order,
                updated_order_header_data=updated_order_header_data,
                request_item=item,
                order_schedule=order_schedule,
            )
        )
    params = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": header_code,
                    "originalHeaderCode": header_code,
                    "DDQConfirmLine": confirm_lines,
                }
            ],
        }
    }
    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value, **log_val
    ).request_mulesoft_post(IPlanEndPoint.I_PLAN_CONFIRM.value, params)

    dict_response_line = get_iplan_confirm_line(response)
    return response, dict_response_line


def handle_yt65156_rollback(order: Order, request_items: List):
    request_items = sorted(request_items, key=lambda item: float(item))
    header_code: str = order.so_no.lstrip("0")
    params = {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": header_code,
                    "originalHeaderCode": header_code,
                    "DDQConfirmLine": [
                        {
                            "lineNumber": item_no,
                            "originalLineNumber": item_no,
                            "status": "ROLLBACK",
                            "DDQOrderInformationType": [],
                        }
                        for item_no in request_items
                        if request_items
                    ],
                }
            ],
        }
    }
    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.IPLAN.value, **log_val
    ).request_mulesoft_post(IPlanEndPoint.I_PLAN_CONFIRM.value, params)
    return response
