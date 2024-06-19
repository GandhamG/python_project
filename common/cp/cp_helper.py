import uuid
from datetime import datetime, timezone
from typing import List, Tuple

from scgp_cip.common.constants import DMY_FORMAT
from scgp_cip.common.enum import (
    CpApiMessage,
    CPRequestType,
    MaterialTypes,
    ProductionFlag,
)
from scgp_cip.service.helper.order_line_helper import is_bom_parent

CP_SENDER = "e-ordering"


def prepare_cp_payload(
    order,
    temp_order_no,
    cp_order_lines,
    request_type,
    original_order_lines_obj_dict=None,
    split_line_child_parent=None,
    **kwargs,
):
    payload = {
        "requestId": str(uuid.uuid1().int)[:10],
        "sender": CP_SENDER,
    }
    sold_to = (
        order.sold_to.sold_to_code.lstrip("0").zfill(7)
        if order.sold_to and order.sold_to.sold_to_code
        else None
    )
    order_header = {
        "requestType": request_type,
        "saleOrg": order.sales_organization.code,
        "soldTo": sold_to,
    }
    current_date = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    order_header["tempOrder"] = temp_order_no.zfill(10)
    if CPRequestType.NEW.value == request_type:
        order_header["createDT"] = current_date
    else:
        order_header["changedDT"] = current_date
        order_header["soNo"] = order.so_no
    payload["orderHeader"] = order_header
    payload["orderItem"] = get_cp_order_items(
        sold_to,
        cp_order_lines,
        original_order_lines_obj_dict,
        split_line_child_parent,
        **kwargs,
    )
    return payload


def get_cp_order_items(
    sold_to,
    order_lines,
    original_order_lines_obj_dict=None,
    split_line_child_parent=None,
    **kwargs,
):
    cp_order_items = []
    is_excel_upload_flow = kwargs.get("is_excel_upload", False)
    for order_line in order_lines:
        original_line_db = order_line
        is_new = False
        """
            Split case:
                1. Order_lines is of type:SplitCipOrderLineInput
                2. for split lines alone order_line.id won't be available hence that has to be sent with isNew = True
        """
        force_flag = order_line.force_flag if is_excel_upload_flow else False
        if original_order_lines_obj_dict:
            if order_line.id:
                original_line_db = original_order_lines_obj_dict.get(order_line.id)
            elif order_line.original_item_id:
                original_line_db = original_order_lines_obj_dict.get(
                    order_line.original_item_id
                )
                is_new = True
        elif order_line.draft:
            is_new = True
        cp_order_item = {
            "itemNo": order_line.item_no.zfill(6),
            "matCode": original_line_db.material_code.zfill(18),
            "qty": int(order_line.quantity),
            "unit": original_line_db.sales_unit,
            "soldTo": sold_to,
            "shipTo": (
                str(original_line_db.ship_to or "").strip().split("-")[0].lstrip("0")
            )
            .strip()
            .zfill(7)
            if original_line_db.ship_to
            else "",
            "requestDate": order_line.request_date.strftime(DMY_FORMAT),
            "isNew": is_new,
            "forceFlag": force_flag,
        }
        if original_line_db.plant:
            cp_order_item["plant"] = original_line_db.plant
        parent_bom_line = original_line_db.parent
        if parent_bom_line:
            parent_item_no = parent_bom_line.item_no
            if split_line_child_parent and split_line_child_parent.get(
                order_line.item_no
            ):
                parent_split_line = split_line_child_parent.get(order_line.item_no)
                parent_item_no = parent_split_line.item_no
            cp_order_item["matBom"] = parent_item_no.zfill(
                6
            ) + parent_bom_line.material_code.zfill(18)
        cp_order_items.append(cp_order_item)

    return cp_order_items


def is_cp_planning_required(production_flag, bom_flag, parent, material):
    cp_planning_required_flag = True
    if ProductionFlag.NOT_PRODUCED.value == production_flag:
        cp_planning_required_flag = False
    elif is_bom_parent(bom_flag, parent):
        cp_planning_required_flag = False
    elif material and material.material_type in [
        MaterialTypes.SERVICE_MATERIAL.value,
    ]:
        cp_planning_required_flag = False
    return cp_planning_required_flag


def filter_cp_order_line(order_lines, original_line_items_dict=None, item_details=None):
    cp_order_items = []
    for order_line in order_lines:
        item_production_flag = None
        if item_details:
            for item_detail in item_details:
                if item_detail["id"] == str(order_line.id):
                    item_production_flag = item_detail.get("production_flag")
        production_flag = (
            item_production_flag if item_production_flag else order_line.production_flag
        )
        if is_cp_planning_required(
            production_flag, order_line.bom_flag, order_line.parent, order_line.material
        ):
            if original_line_items_dict and original_line_items_dict.get(order_line.id):
                cp_order_items.append(original_line_items_dict.get(order_line.id))
            else:
                cp_order_items.append(order_line)
    return cp_order_items


def process_cp_response(
    cp_response,
    order_lines,
    request_type,
    original_order_lines_obj_dict=None,
    split_line_child_parent=None,
):
    cp_item_messages = []
    cp_error_messages = []
    bom_parent_item_nos = []
    order_line_dict = {item.item_no: item for item in order_lines}
    cp_confirm_date_mismatch = False
    if CpApiMessage.SUCCESS.value != cp_response.get("message", ""):
        # TODO: prepare CP Error Message
        return cp_item_messages, cp_error_messages, cp_confirm_date_mismatch
    for item in cp_response.get("orderItem", []):
        order_line = order_line_dict.get(item.get("itemNo", "").lstrip("0"))
        (
            cp_confirm_date_mismatch,
            bom_parent_item_nos,
            cp_item_messages,
        ) = prepare_cp_item_message(
            item,
            order_line,
            request_type,
            bom_parent_item_nos,
            cp_item_messages,
            cp_confirm_date_mismatch,
            original_order_lines_obj_dict,
            split_line_child_parent,
        )
        cp_item_messages = sorted(cp_item_messages, key=lambda x: int(x["item_no"]))
    return cp_item_messages, cp_error_messages, cp_confirm_date_mismatch


def prepare_cp_item_message(
    cp_response_item,
    order_line,
    request_type,
    bom_parent_item_nos,
    cp_item_messages,
    cp_confirm_date_mismatch=False,
    original_order_lines_obj_dict=None,
    split_line_child_parent=None,
) -> Tuple[bool, List[int], List[dict]]:
    """
    Prepares CP item message data for order line and its parents recursively.
    Args:
        cp_response_item: CP response data for the item.
        order_line: The current order line.
        request_type: Type of request (NEW or CHANGE).
        bom_parent_item_nos: List to track unique parent Item Nos.
        cp_item_messages: List to store CP item messages.
        cp_confirm_date_mismatch: Flag indicating if there is a CP's confirm date and request date mismatch.
        original_order_lines_obj_dict: Key: Order Line Id (original order lines on which split performed) & Value: Order Line Object
        split_line_child_parent: Key: Child Item No Value: Parent Split Item
    Returns:
        Tuple containing cp_confirm_date_mismatch, bom_parent_ids, and cp_item_messages.
    """
    if not order_line:
        return cp_confirm_date_mismatch, bom_parent_item_nos, cp_item_messages

    confirm_date = cp_response_item.get("confirmDate", "")
    plant = cp_response_item.get("plant", "")
    mat_bom = cp_response_item.get("matBom", "")
    order_line_db = order_line
    request_date = (
        order_line_db.request_date.strftime(DMY_FORMAT)
        if order_line_db is not None
        else None
    )

    """
        Split Flow:
        Original Order lines - same as Other flows we can get from DB using order line id
        Split order lines: Get Order Line from DB using original Item Id
    """
    if original_order_lines_obj_dict:
        order_line_id = order_line.id if order_line.id else order_line.original_item_id
        order_line_db = original_order_lines_obj_dict.get(order_line_id)

    if CPRequestType.NEW.value == request_type and confirm_date == request_date:
        """
        1. CREATE Order: Only if CP's confirm date doesn't match with request date then only create CpItemMessage
        2. CHANGE Order: Irrespective of Cp's confirm date matches or not with request date
                        CpItemMessage will have complete data
        """
        return cp_confirm_date_mismatch, bom_parent_item_nos, cp_item_messages
    if not cp_confirm_date_mismatch and confirm_date != request_date:
        cp_confirm_date_mismatch = True
    parent_order_line = order_line_db.parent
    if split_line_child_parent and split_line_child_parent.get(order_line.item_no):
        parent_order_line = split_line_child_parent.get(order_line.item_no)

    cp_item_message = {
        "item_no": order_line.item_no,
        "parent_item_no": parent_order_line.item_no if parent_order_line else None,
        "material_code": order_line_db.material_code,
        "material_description": order_line_db.material.description_en,
        "quantity": order_line.quantity,
        "request_date": order_line.request_date,
        "original_date": order_line.request_date.strftime(DMY_FORMAT),
        "confirm_date": confirm_date,
        "plant": plant,
        "bom_flag": order_line_db.bom_flag,
        "parent_bom": mat_bom
        if order_line_db.bom_flag and order_line_db.parent
        else "",
        "show_in_popup": confirm_date != request_date,
    }
    cp_item_messages.append(cp_item_message)
    if parent_order_line and parent_order_line.item_no not in bom_parent_item_nos:
        bom_parent_item_nos.append(parent_order_line.item_no)
        prepare_cp_item_message(
            cp_response_item,
            parent_order_line,
            request_type,
            bom_parent_item_nos,
            cp_item_messages,
            cp_confirm_date_mismatch,
            original_order_lines_obj_dict,
            split_line_child_parent,
        )
    return cp_confirm_date_mismatch, bom_parent_item_nos, cp_item_messages


def prepare_order_line_update(order_lines, cp_response):
    order_line_dict = {item.item_no: item for item in order_lines}
    for item in cp_response.get("orderItem", []):
        order_line = order_line_dict.get(item.get("itemNo", "").lstrip("0"))
        order_line.confirmed_date = datetime.strptime(
            item.get("confirmDate"), "%d/%m/%Y"
        )
