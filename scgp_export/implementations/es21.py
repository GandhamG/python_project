import datetime
import uuid
from typing import List, Tuple

from common.enum import EorderingItemStatusEN, MulesoftServiceType
from common.helpers import dictgetattrd, getattrd, is_field_updated, update_dict_if
from common.mulesoft_api import MulesoftApiRequest
from sap_migration.models import Order, OrderLines
from scgp_export.graphql.enums import SapEnpoint
from scgp_require_attention_items.graphql.helper import add_class_mark_into_order_line

from ..graphql.mutations.constants import (
    MATERIAL_OS_PLANT,
    ORDER_HEADER_FIELD_FROM_DB_TO_SAP,
)


def build_order_header_es21(
    order: Order, updated_order_header_data: dict
) -> Tuple[dict, dict]:
    order_header_in = {}
    order_header_in_x = {}
    required_fields = [
        "po_no",
        "description",
        "unloading_point",
        "usage",
        "request_date",
        "place_of_delivery",
    ]
    for db_field, request_header_field in ORDER_HEADER_FIELD_FROM_DB_TO_SAP.items():
        if db_field in required_fields:
            updated_field_data = updated_order_header_data.get(db_field, None)
            if not updated_field_data:
                continue
            if isinstance(updated_field_data, datetime.date):
                updated_field_data = updated_field_data.strftime("%d/%m/%Y")
            order_header_in.update({request_header_field: updated_field_data})
            order_header_in_x.update({request_header_field: True})

    order_header_in.update({"refDoc": order.contract.code if order.contract else ""})
    return order_header_in, order_header_in_x


def build_update_order_item_es21(
    request_item: dict,
    default_plant: str,
    input_data,
    order_header_data=dict,
    updated_order_header_data=dict,
):
    order_item_in = {}
    order_item_inx = {}
    order_schedule_in = {}
    order_schedule_inx = {}
    item_order_texts = []

    item_model: OrderLines = request_item.get("db_item")
    item_input_data: dict = request_item.get("item_input_data", {})
    yt_65156_response = request_item.get("iplan_item", {})

    item_no = item_model.item_no.lstrip("0")
    mat_code = getattrd(item_model, "material_variant.code", "")

    order_item_in = {
        "itemNo": item_no,
        "material": mat_code,
    }

    order_item_inx = {"itemNo": item_no, "updateflag": "U"}

    target_qty = (
        yt_65156_response.get("quantity")
        if yt_65156_response
        else item_input_data.get("quantity")
    )
    update_dict_if(
        target_qty != item_model.quantity,
        order_item_in,
        "targetQty",
        target_qty,
    )

    is_container = (
        item_model.material_variant
        and item_model.material_variant.material.material_group == "PK00"
    )

    if is_container:
        plant = default_plant
    else:
        plant = (
            yt_65156_response.get("warehouseCode", "")
            if yt_65156_response
            else item_input_data.get("plant", "")
        )
    update_dict_if(
        is_field_updated(item_model, item_input_data, "plant"),
        order_item_in,
        "plant",
        plant,
    )
    shipping_point = item_input_data.get("shipping_point")
    update_dict_if(
        is_field_updated(item_model, item_input_data, "shipping_point"),
        order_item_in,
        "shippingPoint",
        shipping_point,
    )

    route = item_input_data.get("route", "").split("-")[0].strip()
    old_route = item_model.route.split("-")[0].strip() if item_model.route else ""
    is_route_updated = route != old_route
    update_dict_if(
        is_route_updated,
        order_item_in,
        "route",
        route,
    )

    item_category = item_input_data.get("item_cat_eo")
    update_dict_if(
        is_field_updated(item_model, item_input_data, "item_cat_eo"),
        order_item_in,
        "itemCategory",
        item_category,
    )

    delivery_tol_over = item_input_data.get("delivery_tol_over")
    update_dict_if(
        is_field_updated(item_model, item_input_data, "delivery_tol_over"),
        order_item_in,
        "overdlvtol",
        delivery_tol_over,
    )

    unlimit_tol = "X" if item_input_data.get("delivery_tol_unlimited") else ""
    update_dict_if(
        is_field_updated(item_model, item_input_data, "delivery_tol_unlimited"),
        order_item_in,
        "unlimitTol",
        unlimit_tol,
    )

    delivery_tol_under = item_input_data.get("delivery_tol_under")
    update_dict_if(
        is_field_updated(item_model, item_input_data, "delivery_tol_under"),
        order_item_in,
        "unddlvTol",
        delivery_tol_under,
    )

    condition_group1 = item_input_data.get("condition_group1")
    update_dict_if(
        is_field_updated(item_model, item_input_data, "condition_group1"),
        order_item_in,
        "conditionGroup1",
        condition_group1,
    )

    if is_field_updated(item_model, order_header_data, "internal_comment_to_warehouse"):
        if updated_order_header_data.get("internal_comment_to_warehouse"):
            item_order_texts.append(
                build_order_text_es21(
                    item_no.zfill(6),
                    "Z001",
                    order_header_data.get("internal_comment_to_warehouse"),
                )
            )

    if is_field_updated(item_model, input_data, "shipping_mark"):
        item_order_texts.append(
            build_order_text_es21(
                item_no.zfill(6), "Z004", input_data.get("shipping_mark")
            )
        )

    if (
        order_header_data.request_date
        and order_header_data.request_date != item_model.request_date
    ):
        if updated_order_header_data.get("request_date"):
            add_class_mark_into_order_line(item_model, "C4", "C", 1, 4)
            item_order_texts.append(
                build_order_text_es21(
                    item_no.zfill(6),
                    "Z020",
                    item_model.class_mark if item_model else "",
                )
            )

    if (
        not bool(set(order_item_in.keys()) - {"itemNo", "material"})
        and not item_order_texts
    ):
        order_item_in = None
        order_item_inx = None
    else:
        order_item_in.update(
            {
                "refDoc": item_model.ref_doc,
                "refItem": item_model.ref_doc_it,
                "refDocIt": item_model.ref_doc_it,
            }
        )

        if order_item_in.get("unlimitTol") and unlimit_tol == "X":
            if order_item_in.get("unddlvTol", None) is not None:
                order_item_in["unddlvTol"] = 0
            if order_item_in.get("overdlvtol", None) is not None:
                order_item_in["overdlvtol"] = 0

        order_item_in_keys = order_item_in.keys()

        for k in order_item_in_keys:
            if k in ["itemNo", "material", "refDoc", "refItem", "refDocIt"]:
                continue
            elif k == "route" and order_item_in.get("route") == "":
                order_item_inx.update({k: False})
            else:
                order_item_inx.update({k: True})
    order_schedule_in = {
        "itemNo": item_no,
    }

    order_schedule_inx = {"itemNo": item_no, "updateflag": "U"}
    request_date_from_ui = item_input_data.get("request_date", None)
    request_date_from_db = item_model.request_date
    request_date_formatted_ui: str = (
        request_date_from_ui.strftime("%d/%m/%Y") if request_date_from_ui else ""
    )

    request_date_formatted_db: str = (
        request_date_from_db.strftime("%d/%m/%Y") if request_date_from_db else ""
    )
    # Send the request date only if it has been modified
    update_dict_if(
        request_date_formatted_ui != request_date_formatted_db,
        order_schedule_in,
        "reqDate",
        request_date_formatted_ui
        if request_date_formatted_ui
        else request_date_formatted_db,
    )

    update_dict_if(
        target_qty != item_model.quantity,
        order_schedule_in,
        "reqQty",
        target_qty,
    )
    confirm_quantity = 0
    is_confirm_quantity_updated = False
    if is_container or plant in MATERIAL_OS_PLANT:
        confirm_quantity = target_qty
        # Only send confirm quantity for container and special plant if target quantity updated
        if item_model.quantity != target_qty:
            is_confirm_quantity_updated = True
    else:
        # No data from YT65156, won't update confirm quantity
        # The request date always needs to be sent, irrespective of whether the request date has been modified or not
        if yt_65156_response:
            is_confirm_quantity_updated = True
            if not order_schedule_in.get("reqDate"):
                update_dict_if(
                    True,
                    order_schedule_in,
                    "reqDate",
                    request_date_formatted_ui
                    if request_date_formatted_ui
                    else request_date_formatted_db,
                )
            if not order_schedule_in.get("reqQty"):
                update_dict_if(
                    True,
                    order_schedule_in,
                    "reqQty",
                    target_qty,
                )
            on_hand_stock = dictgetattrd(yt_65156_response, "onHandStock", False)
            if on_hand_stock:
                confirm_quantity = dictgetattrd(yt_65156_response, "quantity", 0)
            else:
                confirm_quantity = 0
            item_model.confirm_quantity = confirm_quantity
            item_model.save()

    update_dict_if(
        is_confirm_quantity_updated,
        order_schedule_in,
        "confirmQty",
        confirm_quantity,
    )

    if not bool(set(order_schedule_in.keys()) - {"itemNo"}):
        order_schedule_in = None
        order_schedule_inx = None
    else:
        order_schedule_in_flag = {
            "reqDate": "requestDate",
            "reqQty": "requestQuantity",
            "confirmQty": "confirmQuantity",
        }

        for k, v in order_schedule_in_flag.items():
            if order_schedule_in.get(k) is not None:
                order_schedule_inx.update({v: True})

    return (
        order_item_in,
        order_item_inx,
        order_schedule_in,
        order_schedule_inx,
        item_order_texts,
    )


def build_new_order_item_es21(order: Order, iplan_request_item: dict):
    item_no = str(iplan_request_item.get("item_no"))
    iplan_item = iplan_request_item.get("iplan_item", {})
    item_input_data: dict = iplan_request_item.get("item_input_data", {})

    order_item_model: OrderLines = iplan_request_item.get("db_item", None)

    # SEO-6239: Remove request date compare logic and reqDate will be request date from UI
    request_date = (
        item_input_data.get("request_date") or order_item_model.request_date or None
    )
    if request_date:
        request_date_format = request_date.strftime("%d/%m/%Y")
    material = (
        order_item_model.material_variant.code
        if order_item_model.material_variant
        else ""
    )
    quantity = iplan_item.get("quantity", 0)
    sales_unit = "ROL"
    plant = iplan_item.get("warehouseCode")
    po_date = (
        order_item_model.original_request_date.strftime("%d/%m/%Y")
        if order_item_model.original_request_date
        else ""
    )

    over_div_tol = order_item_model.delivery_tol_unlimited or 0
    under_div_tol = order_item_model.delivery_tol_under or 0
    unlimited_div_tol = "X" if order_item_model.delivery_tol_unlimited else ""
    ref_doc = order_item_model.ref_doc
    ref_doc_it = order_item_model.ref_doc_it
    order_item_in = {
        "itemNo": item_no,
        "material": material,
        "targetQty": quantity,
        "salesUnit": sales_unit,
        "plant": plant,
        "poDate": po_date,
        "overdlvtol": over_div_tol,
        "unlimitTol": unlimited_div_tol,
        "unddlvTol": under_div_tol,
        "refDoc": ref_doc,
        "refDocIt": ref_doc_it,
    }

    if order_item_in.get("unlimitTol", "") == "X":
        order_item_in["overdlvtol"] = 0
        order_item_in["unddlvTol"] = 0

    order_item_inx = {
        "itemNo": item_no,
        "updateflag": "I",
        "targetQty": True,
        "salesUnit": True,
        "plant": True,
        "poDate": True,
        "overdlvtol": True,
        "unlimitTol": True,
        "unddlvTol": True,
    }

    if not item_input_data.get("shipping_point", ""):
        order_item_in.pop("shippingPoint")
        order_item_inx.pop("shippingPoint")

    order_schedule_in = {
        "itemNo": item_no,
        "reqDate": request_date_format,
        "reqQty": iplan_item.get("quantity", 0),
        "confirmQty": iplan_item.get("quantity", 0)
        if iplan_item.get("onHandStock", False)
        else 0,
    }

    order_schedule_inx = {
        "itemNo": item_no,
        "updateflag": "I",
        "requestDate": True,
        "requestQuantity": True,
        "confirmQuantity": True,
    }

    return order_item_in, order_item_inx, order_schedule_in, order_schedule_inx


def build_order_partner_header_es21(role: str, numb: str):
    return {"partnerRole": role, "partnerNumb": numb, "itemNo": "000000"}


def build_order_text_es21(
    item_no: str,
    text_id: str,
    text_lines: str,
    header_text_lines: str = None,
    ignore_blank=False,
    language="EN",
):
    def _hook_text_lines(_text_lines):
        for instance_type in [datetime.date, datetime.datetime]:
            if isinstance(_text_lines, instance_type):
                _text_lines = _text_lines.strftime("%d%m%Y")
        return _text_lines

    text_line = list(
        filter(
            lambda x: x and len(x) > 0, (_hook_text_lines(text_lines or "")).split("\n")
        )
    )
    if not text_line:
        if ignore_blank:
            return
        text_line = [" "]

    request_text = {
        "itemNo": item_no,
        "language": language,
        "textId": text_id,
        "textLineList": [{"textLine": item} for item in text_line],
    }

    return request_text


def request_es21_update_export_order(
    order: Order,
    i_plan_request_items: List,
    order_header_data: dict,
    updated_order_header_data: dict,
    default_plant=None,
):
    order_header_in, order_header_in_x = build_order_header_es21(
        order, updated_order_header_data
    )

    order_partners = []
    ship_to = order_header_data.get("ship_to", "").split("-")[0].strip()
    order_partners.append(build_order_partner_header_es21("WE", ship_to))

    bill_to = order_header_data.get("bill_to", "").split("-")[0].strip()
    order_partners.append(build_order_partner_header_es21("RE", bill_to))

    payer = order_header_data.get("payer", "").split("-")[0].strip()
    order_partners.append(build_order_partner_header_es21("RG", payer))

    order_items_in = []
    order_items_in_x = []
    order_schedules_in = []
    order_schedules_in_x = []

    order_texts = []

    # Changes SEO-6016
    header_item_no = "000000"

    if updated_order_header_data.get("internal_comment_to_warehouse"):
        order_texts.append(
            build_order_text_es21(
                header_item_no,
                "Z001",
                order_header_data.get("internal_comment_to_warehouse"),
            )
        )

    if updated_order_header_data.get("port_of_discharge"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z013", order_header_data.get("port_of_discharge")
            )
        )

    if updated_order_header_data.get("port_of_loading"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z014", order_header_data.get("port_of_loading")
            )
        )

    if updated_order_header_data.get("no_of_containers"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z022", order_header_data.get("no_of_containers", "")
            )
        )

    if updated_order_header_data.get("shipping_mark"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z004", order_header_data.get("shipping_mark")
            )
        )

    if updated_order_header_data.get("uom"):
        order_texts.append(
            build_order_text_es21(header_item_no, "Z019", order_header_data.get("uom"))
        )
    if updated_order_header_data.get("gw_uom"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "ZK35", order_header_data.get("gw_uom", "")
            )
        )

    if updated_order_header_data.get("etd"):
        etd: datetime.date = order_header_data.get("etd", "")
        if etd:
            etd = etd.strftime("%d%m%Y")
        order_texts.append(build_order_text_es21(header_item_no, "Z038", etd))

    if updated_order_header_data.get("eta"):
        eta: datetime.date = order_header_data.get("eta", "")
        if eta:
            eta = eta.strftime("%d%m%Y")
        order_texts.append(build_order_text_es21(header_item_no, "Z066", eta))

    if updated_order_header_data.get("dlc_expiry_date"):
        dlc_expiry_date: datetime.datetime = order_header_data.get(
            "dlc_expiry_date", None
        )
        dlc_expiry_date_format = (
            dlc_expiry_date.strftime("%d%m%Y") if dlc_expiry_date else " "
        )

    dlc_latest_delivery_date: datetime.datetime = order_header_data.get(
        "dlc_latest_delivery_date", None
    )
    dlc_latest_delivery_date_format = (
        dlc_latest_delivery_date.strftime("%d%m%Y") if dlc_latest_delivery_date else " "
    )

    if updated_order_header_data.get("dlc_expiry_date"):
        order_texts.append(
            build_order_text_es21(header_item_no, "Z223", dlc_expiry_date_format)
        )

    if updated_order_header_data.get("dlc_no"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z222", str(order_header_data.get("dlc_no", ""))
            )
        )

    if updated_order_header_data.get("dlc_latest_delivery_date"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z224", dlc_latest_delivery_date_format
            )
        )

    if updated_order_header_data.get("payment_instruction"):
        order_texts.append(
            build_order_text_es21(
                header_item_no,
                "Z012",
                str(order_header_data.get("payment_instruction", "")),
            )
        )

    if updated_order_header_data.get("remark"):
        order_texts.append(
            build_order_text_es21(
                header_item_no, "Z016", str(order_header_data.get("remark", ""))
            )
        )

    if updated_order_header_data.get("production_information"):
        order_texts.append(
            build_order_text_es21(
                header_item_no,
                "ZK08",
                str(order_header_data.get("production_information", "")),
            )
        )

    for v in i_plan_request_items:
        input_data = v.get("item_input_data", {})
        item_model: OrderLines = v.get("db_item", None)
        if item_model.item_status_en == EorderingItemStatusEN.CANCEL.value:
            continue
        if v.get("update_flag") == "U":
            (
                order_item_in,
                order_item_in_x,
                order_schedule_in,
                order_schedule_in_x,
                item_order_texts,
            ) = build_update_order_item_es21(
                v,
                default_plant=default_plant,
                input_data=input_data,
                order_header_data=order_header_data,
                updated_order_header_data=updated_order_header_data,
            )
        else:
            item_order_texts = []  # reset to avoid SEO-7823 remark being repeated
            (
                order_item_in,
                order_item_in_x,
                order_schedule_in,
                order_schedule_in_x,
            ) = build_new_order_item_es21(order, v)
        if EorderingItemStatusEN.COMPLETE_DELIVERY.value != order.status:
            if order_item_in:
                order_items_in.append(order_item_in)
            if order_item_in_x:
                order_items_in_x.append(order_item_in_x)
            if order_schedule_in:
                order_schedules_in.append(order_schedule_in)
            if order_schedule_in_x:
                order_schedules_in_x.append(order_schedule_in_x)
        if item_order_texts:
            order_texts.extend(item_order_texts)

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no.lstrip("0"),
        "testrun": False,
        "orderHeaderIn": order_header_in,
        "orderHeaderInX": order_header_in_x,
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_in_x,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_in_x,
        "orderText": order_texts,
    }

    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
    }
    response = MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value, **log_val
    ).request_mulesoft_post(SapEnpoint.ES_21.value, params)
    return_item_message = response.get("return", [])
    return_messages = {"fail": [], "success": [], "warning": []}
    for message_obj in return_item_message:
        __type = message_obj.get("type", None)
        if __type:
            return_messages[__type].append(message_obj)

    order_items_out = response.get("orderItemsOut", [])
    order_schedules_out = response.get("orderSchedulesOut", [])

    return (
        response,
        return_messages,
        order_items_out,
        order_schedules_out,
        order_items_in,
        order_schedules_in,
    )
