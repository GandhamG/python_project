import logging
from datetime import datetime

from django.core.exceptions import ImproperlyConfigured, ValidationError

from common.cp.cp_api import CPApiRequest
from sap_migration.models import OrderLineCp
from scgp_cip.common.constants import DMY_FORMAT, YMD_FORMAT
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo


def get_cp_solution(request):
    try:
        logging.info(f"cp api request: {request}")
        cp_response = CPApiRequest.call_cp(request)
        # from common.cp.cp_example_response import CP_API_SUCCESS_RESPONSE_BOM
        # cp_response = CP_API_SUCCESS_RESPONSE_BOM
        logging.info(f"cp api response: {cp_response}")
        return cp_response
    except ValidationError as e:
        raise e
    except Exception as e:
        raise ImproperlyConfigured(e)


def prepare_order_line_cp_obj(cp_response_item, order):
    confirm_date = datetime.strptime(
        cp_response_item.get("confirm_date"), DMY_FORMAT
    ).strftime(YMD_FORMAT)

    order_line_cp = OrderLineCp(
        order_id=order.id,
        item_no=cp_response_item.get("item_no", "").lstrip("0"),
        material_code=cp_response_item.get("material_code", ""),
        confirm_date=confirm_date,
        plant=cp_response_item.get("plant", ""),
        material_bom=cp_response_item.get("parent_bom", None),
    )
    return order_line_cp


def save_order_line_cp(order, order_lines, cp_response):
    order_lines_cp_to_create = []
    order_lines_cp_to_update = []
    item_nos = [
        cp_item.get("itemNo", "").lstrip("0")
        for cp_item in cp_response.get("orderItem", [])
    ]
    order_line_cp_dict = OrderLineCpRepo.get_order_lines_cp_by_orderid_and_item_nos(
        order.id, item_nos
    )
    order_line_dict = {item.item_no: item for item in order_lines}
    for item in cp_response.get("orderItem", []):
        confirm_date = datetime.strptime(item.get("confirmDate"), DMY_FORMAT).strftime(
            YMD_FORMAT
        )
        item_no = item.get("itemNo", "").lstrip("0")
        order_line = order_line_dict.get(item_no)
        if order_line_cp_dict.get(item_no):
            order_line_cp = order_line_cp_dict.get(item_no)
            order_lines_cp_to_update.append(order_line_cp)
        else:
            order_line_cp = OrderLineCp(order_id=order.id, item_no=item_no)
            order_lines_cp_to_create.append(order_line_cp)
        order_line_cp.plant = item.get("plant", "")
        order_line_cp.material_bom = item.get("matBom", None)
        order_line_cp.material_code = item.get("matCode", "")
        order_line_cp.confirm_date = confirm_date
        order_line_cp.order_line = order_line
    if order_lines_cp_to_create:
        OrderLineCpRepo.save_order_line_cp_bulk(order_lines_cp_to_create)
    if order_lines_cp_to_update:
        update_fields = [
            "plant",
            "material_bom",
            "material_code",
            "confirm_date",
            "order_line",
        ]
        OrderLineCpRepo.update_order_line_cp_bulk(
            order_lines_cp_to_update, update_fields
        )


def prepare_cp_order_line_using_cp_item_messages(
    cp_response_item_dict, order_line_db, order_line
):
    if cp_response_item_dict and cp_response_item_dict.get(order_line.item_no):
        cp_response_item = cp_response_item_dict.get(order_line.item_no)
        order = order_line_db.order
        order_line_cp = prepare_order_line_cp_obj(cp_response_item, order)
        return cp_response_item, order_line_cp
    return None, None
