import uuid
from datetime import date
from typing import Any, Dict, List, Tuple

from common.helpers import dictgetattrd
from common.iplan.iplan_api import IPlanApiRequest
from sap_migration.models import Order, OrderLines


def get_order_update_request_line(
    order: Order, item: OrderLines, request_date: date, confirm_date: date, quantity
) -> dict:
    request_date = (
        request_date.strftime("%Y-%m-%dT00:00:00.000Z")
        or item.request_date.strftime("%Y-%m-%dT00:00:00.000Z")
        or ""
    )
    confirm_date = (
        item.confirmed_date.strftime("%Y-%m-%dT00:00:00.000Z")
        if item.confirmed_date
        else request_date
    )

    update_quantity = quantity or item.quantity or 0
    request_line = {
        "orderNumber": order.so_no.lstrip("0"),
        "lineCode": item.item_no.lstrip("0"),
        "requestDate": request_date,
        "deliveryDate": confirm_date,
        "quantity": update_quantity,
        "unit": "ROL",
    }

    return request_line


def get_iplan_update_order_request(
    order: Order, items: List[OrderLines], order_lines_updated_data: dict
):
    request_lines = []
    for item in items:
        updated_data = order_lines_updated_data.get(str(item.pk), None)
        if updated_data:
            request_lines.append(
                get_order_update_request_line(
                    order,
                    item,
                    updated_data.get("request_date", None),
                    item.confirmed_date,
                    updated_data.get("quantity", None),
                )
            )
    return {
        "OrderUpdateRequest": {
            "updateId": str(uuid.uuid1().int),
            "OrderUpdateRequestLine": request_lines,
        }
    }


def get_response_line(iplan_response: Any) -> Dict[str, List]:
    from ..graphql.enums import IPlanResponseStatus

    dict_response_lines: Dict[str, list] = {e.value: [] for e in IPlanResponseStatus}
    response_lines = dictgetattrd(
        iplan_response, "OrderUpdateResponse.OrderUpdateResponseLine", []
    )
    for line in response_lines:
        dict_response_lines[line.get("returnStatus", "")].append(line)

    return dict_response_lines


def handle_yt65217_update_order(
    order, items: List[OrderLines], order_lines_updated_data: dict
) -> Tuple[Any, dict]:
    body = get_iplan_update_order_request(order, items, order_lines_updated_data)

    response = IPlanApiRequest.call_yt65217_api_update_order(body, order=order)
    dict_response_line = get_response_line(response)

    return response, dict_response_line
