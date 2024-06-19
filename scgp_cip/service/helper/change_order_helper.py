import logging
import uuid

from common.helpers import DateHelper
from sap_master_data import models as master_data_models
from sap_migration import models as sap_migration_models
from scg_checkout.graphql.enums import (
    RealtimePartnerType,
    SapUpdateFlag,
    ScgOrderStatus,
)
from scg_checkout.graphql.helper import (
    make_ship_to_from_order_partner,
    mapping_order_partners,
    round_qty_decimal,
)
from scgp_cip.common.constants import (
    BOM_FLAG_TRUE_VALUE,
    DISABLE_SPLIT_ITEM_SATUS,
    DMY_FORMAT,
    ENABLE_SPLIT_ITEM_SATUS,
    HEADER_ORDER_KEY,
    ITEM_NOTE_WHEN_NOT_PRODUCED,
    MAPPING_HEADER_ADDITIONAL_FIELDS,
    MAPPING_ITEM_ADDITIONAL_FIELDS,
    ORDER_PARTNER_AG,
    REASON_REJECT,
    SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX,
    SAP_RESPONSE_TRUE_VALUE,
    SAP_SCHEDULE_LINE_KEY,
)
from scgp_cip.common.enum import (
    SAP_FLAG,
    CIPOrderPaymentType,
    ItemCat,
    MappingLevel,
    MaterialTypes,
    ProductionFlag,
)
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo
from scgp_cip.service.helper.create_order_helper import (
    fetch_item_category,
    partner_address_params_es18,
)
from scgp_cip.service.helper.order_helper import get_line_status_from_es26_cip
from scgp_cip.service.helper.order_line_helper import is_bom_child, is_bom_parent


def get_data_from_order_text_cip(order_texts, order_text_level):
    result = {}
    if (
        order_text_level == MappingLevel.ITEM_LEVEL
        or order_text_level == MappingLevel.HEADER_LEVEL
    ):
        mapping = get_order_text_mapping(order_text_level)
    else:
        mapping = get_order_text_mapping_by_table(order_text_level)
    if not order_texts:
        return result
    for text in order_texts:
        if text.get("textId") in mapping:
            text_lines = text.get("textLine", "")
            result[mapping.get(text.get("textId"))] = "\n".join(
                str(text_line.get("text", "")) if isinstance(text_line, dict) else ""
                for text_line in text_lines
            )
            mapping.pop(text.get("textId"))
    return result


def get_order_text_mapping(order_text_level):
    if MappingLevel.ITEM_LEVEL == order_text_level:
        return {
            "Z001": "internal_comments_to_warehouse",
            "Z002": "external_comments_to_customer",
            "0001": "sale_text1",
            "Z004": "remark",
            "0002": "item_note",
            "Z021": "pr_item_text",
            "ZG23": "lot_no",
            "0006": "production_memo",
        }
    return {
        "0001": "form_header",
        "0002": "header_note_1",
        "Z002": "internal_comments_to_logistic",
        "Z001": "internal_comments_to_warehouse",
        "Z067": "external_comments_to_customer",
        "ZK08": "production_information",
        "Z041": "cash",
    }


def get_order_text_mapping_by_table(order_text_table):
    if order_text_table == "orderline":
        return {
            "Z001": "internal_comments_to_warehouse",
            "Z002": "external_comments_to_customer",
            "Z004": "remark",
            "0002": "item_note",
            "ZG23": "lot_no",
            "0006": "production_memo",
        }
    elif order_text_table == "order":
        return {
            "Z002": "internal_comments_to_logistic",
            "Z001": "internal_comments_to_warehouse",
            "Z067": "external_comments_to_customer",
            "ZK08": "production_information",
        }
    elif order_text_table == "order_extension":
        return {
            "0001": "additional_txt_from_header",
            "0002": "additional_txt_header_note1",
            "Z041": "additional_txt_cash",
        }


def get_data_from_order_partner_cip(
    order_partners, mapping_level, is_model_field_mapping=False
):
    result = {}
    mapping = {
        "AG": "sold_to",
        "WE": "ship_to",
        "RE": "bill_to",
        "RG": "payer",
        "VE": "sales_employee",
        "AP": "contact_person",
        "AU": "author",
        "ZI": "end_customer",
    }
    if not order_partners:
        return result
    for partner in order_partners:
        if partner.get("partnerRole") in mapping:
            partner_address_text = make_ship_to_from_order_partner(partner)
            result[mapping.get(partner.get("partnerRole"))] = partner_address_text
            mapping.pop(partner.get("partnerRole"))
            if MappingLevel.HEADER_LEVEL == mapping_level:
                if ORDER_PARTNER_AG == partner.get("partnerRole"):
                    result["sold_to_code"] = partner.get("partnerNo")
                if (
                    SAP_RESPONSE_TRUE_VALUE == partner.get("onetimeFlag")
                    and not is_model_field_mapping
                ):
                    result.setdefault("otc_order_partners", []).append(partner)
                    if partner.get("partnerRole") == "RE":
                        result["bill_to"] = ""
                    if partner.get(
                        "partnerRole"
                    ) == "WE" and SoldToMasterRepo.is_otc_sold_to(
                        partner.get("partnerNo", "").strip()
                    ):
                        result["ship_to"] = ""
    return result


def get_parent_child_item_no_dict(order_item, parent_child_order_items_dict):
    item_no = order_item.get("item_no")
    if not order_item.get("bom_flag"):
        parent_child_order_items_dict[item_no] = []
    elif order_item.get("bom_flag") and order_item.get("parentItemNo"):
        parent_item_no = order_item.get("parentItemNo").lstrip("0")
        parent_child_order_items_dict.setdefault(parent_item_no, []).append(
            order_item.get("item_no")
        )


def disable_split_flag(purchase_no, material_type, status):
    return (
        purchase_no
        or str(material_type) == MaterialTypes.SERVICE_MATERIAL.value
        or status in DISABLE_SPLIT_ITEM_SATUS
    )


def enable_split_flag(confirm_qty, status):
    return confirm_qty > 0 and status in ENABLE_SPLIT_ITEM_SATUS


def derive_enable_split_flag(
    order_items_dict, order_type, parent_child_order_items_dict
):
    if CIPOrderPaymentType.CASH.value != order_type:
        for key, value in parent_child_order_items_dict.items():
            if not value:
                order_item = order_items_dict.get(key)
                if disable_split_flag(
                    order_item.get("purchaseNo"),
                    order_item.get("materialType"),
                    order_item.get("item_status_en"),
                ):
                    order_items_dict.get(key)["is_split_enabled"] = False
                elif enable_split_flag(
                    order_item.get("comfirmQty", 0), order_item.get("item_status_en")
                ):
                    order_items_dict.get(key)["is_split_enabled"] = True
            else:
                parent_bom_item = order_items_dict.get(key)
                if enable_split_flag(
                    parent_bom_item.get("comfirmQty", 0),
                    parent_bom_item.get("item_status_en"),
                ):
                    enable_split = True
                    for child_item in value:
                        child_bom_item = order_items_dict.get(child_item)
                        if disable_split_flag(
                            child_bom_item.get("purchaseNo"),
                            child_bom_item.get("materialType"),
                            child_bom_item.get("item_status_en"),
                        ):
                            enable_split = False
                            break
                    order_items_dict.get(key)["is_split_enabled"] = enable_split
                else:
                    order_items_dict.get(key)["is_split_enabled"] = False


def derive_price_and_weight_for_parent_bom(
    order_items_dict, parent_child_order_items_dict
):
    for key, value in parent_child_order_items_dict.items():
        if value:
            parent_weight = 0
            net_price = 0
            parent_item = order_items_dict.get(key)
            for item_no in value:
                item = order_items_dict.get(item_no)
                item["parentMaterial"] = parent_item.get("material")
                if str(item.get("rejectReason", "")) != REASON_REJECT:
                    parent_weight += item.get("netWeight", 0)
                    net_price += item.get("totalNetPrice", 0)
            parent_item["totalNetPrice"] = net_price
            parent_item["netWeight"] = parent_weight
            parent_item["netPricePerUnit"] = net_price / parent_item.get("orderQty", 1)


def extract_es_26_res_for_change_order(data):
    response = get_order_mapping_fields(data.get("orderHeaderIn"))
    response.update(get_order_mapping_code_fields(data.get("orderHeaderIn")))
    response.update(get_order_extn_mapping_fields(data.get("orderHeaderIn")))
    response.update(
        {
            "dp": data.get("dp", []),
            "invoice": data.get("billing", []),
            "order_partners": data.get("orderPartners", []),
            "order_items": data.get("orderItems", []),
            "order_condition": data.get("orderCondition", []),
            "order_text": data.get("orderText", []),
            "otc_order_partners": [],
        }
    )
    return response


mapping_header_fields = {
    "request_date": "reqDateH",
    "payment_terms": "paymentTerms",
    "po_no": "poNo",
    "price_date": "priceDate",
    "un_loading_point": "unloadingPoint",
    "tax_class": "taxClass",
    "sale_group_code": "salesGroup",
}
mapping_item_fields_add = {
    "quantity": "targetQty",
    "unit": "salesUnit",
    "sale_qty_factor": "numconvert",
    "material_no": "material",
    "batch_no": "batchNumber",
    "payment_term": "paymentTerms",
    "item_category": "item_category",
    "po_detail": "custPoItemNo",
    "po_item_no": "poitemNoS",
    "price_date": "priceDate",
    "delivery_tol_over": "overdlvtol",
    "delivery_tol_under": "unddlvTol",
    "shipping_point": "shippingPoint",
    "po_date": "poDate",
}

mapping_item_fields_edit = {
    "quantity": "targetQty",
    "unit": "salesUnit",
    "sale_qty_factor": "numconvert",
    "batch_no": "batchNumber",
    "payment_term": "paymentTerms",
    "item_category": "item_category",
    "po_detail": "custPoItemNo",
    "po_item_no": "poitemNoS",
    "price_date": "priceDate",
    "delivery_tol_over": "overdlvtol",
    "delivery_tol_under": "unddlvTol",
    "shipping_point": "shippingPoint",
    "po_date": "poDate",
}
mapping_partner_fields = {
    "ship_to": "reqDateH",
    "bill_to": "paymentTerms",
}
mapping_split_item_additional_fields = {
    "internal_comments_to_warehouse": "Z001",
    "external_comments_to_customer": "Z002",
    "sale_text_1": "0001",
    "sale_text_2": "0001",
    "sale_text_3": "0001",
    "sale_text_4": "0001",
    "remark": "Z004",
    "item_note_cip": "0002",
    "pr_item_text_cip": "Z021",
    "lot_no": "ZG23",
    "production_memo_pp": "0006",
}

mapping_split_item_fields = {
    "quantity": "targetQty",
    "sales_unit": "salesUnit",
    "plant": "plant",
    "batch_no": "batchNumber",
    "payment_term_item": "paymentTerms",
    "item_category": "itemCategory",
    "po_item_no": "poItemNo",
    "delivery_tol_over": "overdlvtol",
    "delivery_tol_unlimited": "unlimitTol",
    "delivery_tol_under": "unddlvTol",
    "shipping_point": "shippingPoint",
}

column_mapping_for_order = {
    "request_date": "request_date",
    "payment_terms": "payment_term",
    "po_no": "po_no",
    "sale_group_code": "sales_group_id",
    "price_date": "price_date",
    "un_loading_point": "unloading_point",
    "ship_to": "ship_to",
    "bill_to": "bill_to",
    "internal_comments_to_warehouse": "internal_comments_to_warehouse",
    "internal_comments_to_logistic": "internal_comments_to_logistic",
    "external_comments_to_customer": "external_comments_to_customer",
    "product_information": "product_information",
}

column_mapping_for_order_extension = {
    "tax_class": "tax_class",
    "from_header": "additional_txt_from_header",
    "header_note1": "additional_txt_header_note1",
    "cash": "additional_txt_cash",
}

column_mapping_for_order_line = {
    "quantity": "target_quantity",
    "unit": "sales_unit",
    "sale_qty_factor": "sales_qty_factor",
    "plant": "plant",
    "batch_no": "batch_no",
    "price_per_unit": "price_per_unit",
    "payment_term": "payment_term_item",
    "item_category": "item_category",
    "po_detail": "po_no",
    "po_item_no": "po_item_no",
    "price_date": "price_date",
    "delivery_tol_over": "delivery_tol_over",
    "delivery_tol_under": "delivery_tol_under",
    "shipping_point": "shipping_point",
    "po_date": "po_date",
    "ship_to": "ship_to",
    "internal_comments_to_warehouse": "internal_comments_to_warehouse",
    "internal_comments_to_logistic": "internal_comments_to_logistic",
    "remark": "remark",
    "sale_text1": "sale_text1",
    "sale_text2": "sale_text2",
    "sale_text3": "sale_text3",
    "sale_text4": "sale_text4",
    "item_note": "item_note",
    "pr_item_text": "pr_item_text",
    "lot_no": "lot_no",
    "production_memo": "production_memo",
    "production_flag": "production_flag",
    "confirm_quantity": "confirm_quantity",
    "sap_confirm_qty": "sap_confirm_qty",
    "assigned_quantity": "assigned_quantity",
    "batch_choice_flag": "batch_choice_flag",
    "draft": "draft",
}


def header_params_es18(header_details):
    order_header_in = {}
    order_header_in_x = {}
    order_text = []
    prepare_headers(header_details, order_header_in, order_header_in_x)
    prepare_header_order_text_es18(header_details, order_text)
    return order_header_in, order_header_in_x, order_text


def prepare_headers(header_details, order_header_in, order_header_in_x):
    for field, mapped_field in mapping_header_fields.items():
        if field in header_details and header_details[field] is not None:
            if field == "request_date":
                order_header_in[mapped_field] = header_details[field].strftime(
                    "%d/%m/%Y"
                )
            else:
                order_header_in[mapped_field] = header_details[field]
            order_header_in_x[mapped_field] = True


def partner_param_es18(header_details, item_details, item_otc_dict):
    mapping_header_addresses = {}
    order_partners = []
    if "ship_to" in header_details:
        ship_to = str(header_details["ship_to"] or "").strip().split("-")[0] or ""
        mapping_header_addresses[RealtimePartnerType.SHIP_TO.value] = ship_to.strip()
    if "bill_to" in header_details:
        bill_to = str(header_details["bill_to"] or "").strip().split("-")[0] or ""
        mapping_header_addresses[RealtimePartnerType.BILL_TO.value] = bill_to.strip()
    if "sales_employee" in header_details:
        sales_employee = (
            str(header_details["sales_employee"] or "").strip().split("-")[0] or ""
        )
        mapping_header_addresses[
            RealtimePartnerType.SALE_EMPLOYEE.value
        ] = sales_employee.strip()

    for partner_role, partner_no in mapping_header_addresses.items():
        if not partner_no:
            continue
        partner_data = {
            "partnerRole": partner_role,
            "partnerNo": partner_no,
            "itemNo": HEADER_ORDER_KEY,
        }
        order_partners.append(partner_data)
    for item in item_details:
        if "ship_to" in item and item["ship_to"]:
            item_no = item["item_no"]
            partner_data = {
                "partnerRole": RealtimePartnerType.SHIP_TO.value,
                "partnerNo": (
                    str(item["ship_to"] or "").strip().split("-")[0] or ""
                ).strip(),
                "itemNo": item_no.zfill(6),
            }
            if item_otc_dict.get(item_no):
                partner_data["addressLink"] = item_otc_dict[item_no]
            order_partners.append(partner_data)
    return order_partners


def prepare_header_order_text_es18(header_details, order_text):
    for field, text_id in MAPPING_HEADER_ADDITIONAL_FIELDS.items():
        if field in header_details and header_details[field] is not None:
            order_text.append(
                {
                    "itemNo": HEADER_ORDER_KEY,
                    "textId": text_id,
                    "textLineList": [{"textLine": header_details[field]}],
                }
            )


def add_change_order_condition_in(
    item_no,
    price,
    material_code,
    order_conditions_ins,
    order_conditions_in_xs,
    manual_price_flag,
):
    if (
        material_code
        and material_code == MaterialTypes.SERVICE_MATERIAL.value
        and manual_price_flag
    ):
        order_conditions_in = {
            "itemNo": item_no,
            "conditionType": ItemCat.ZPS2.value,
            "conditionValue": price,
        }
        order_conditions_in_x = {
            "condItemNo": item_no,
            "condType": ItemCat.ZPS2.value,
            "condRate": True,
            "updateFlg": SapUpdateFlag.UPDATE.value,
        }
        order_conditions_ins.append(order_conditions_in)
        order_conditions_in_xs.append(order_conditions_in_x)


def item_params_es18(
    item_details, order_text, order_type, is_new, order_lines_by_item_no, order
):
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_conditions_in = []
    order_conditions_in_x = []
    parent_child_item_no_dict = {}
    fields_added = False

    for line in order_lines_by_item_no.values():
        if line.parent:
            parent_child_item_no_dict.setdefault(line.parent.item_no, []).append(
                line.item_no
            )

    for item in item_details:
        item_no = item["item_no"].zfill(6)
        material_no = item["material_no"]
        production_flag = item.get("production_flag")
        batch_no = item.get("batch_no")
        order_line_db = order_lines_by_item_no.get(item["item_no"])
        parent = order_line_db.parent
        bom = order_line_db.bom_flag
        bom_parent = is_bom_parent(bom, parent)
        bom_child = is_bom_child(bom, parent)
        order_item = {
            "itemNo": item_no,
        }

        order_item_inx = {
            "itemNo": item_no,
            "updateflag": SapUpdateFlag.INSERT.value
            if is_new
            else SapUpdateFlag.UPDATE.value,
        }

        if order_line_db and bom_child:
            order_item["parentItemNo"] = parent.item_no.zfill(6)
            order_item_inx["parentItemNo"] = True
        if item.get("ship_to"):
            fields_added = True
        if "plant" in item or is_new:
            if bom_parent:
                child_item_nos = parent_child_item_no_dict.get(item.item_no)
                if child_item_nos:
                    child_order_line_cp = (
                        OrderLineCpRepo.get_order_line_cp_by_order_id_and_item_no(
                            order, child_item_nos
                        )
                    )
                order_item["plant"] = (
                    child_order_line_cp
                    and child_order_line_cp.plant
                    or item.get("plant")
                    or ""
                )
            else:
                order_line_cp = OrderLineCpRepo.get_order_line_cp_by_order_line_id(
                    order_line_db.id
                )
                order_item["plant"] = (
                    order_line_cp and order_line_cp.plant or item.get("plant") or ""
                )
            order_item_inx["plant"] = True
            fields_added = True
        mapping_item_fields = (
            mapping_item_fields_add if is_new else mapping_item_fields_edit
        )
        for field, mapped_field in mapping_item_fields.items():
            if field in item and item[field] is not None:
                order_item[mapped_field] = (
                    item["price_date"].strftime("%d/%m/%Y")
                    if field == "price_date"
                    else item[field]
                )
                if mapped_field == "custPoItemNo":
                    mapped_field = "purchaseOrderItem"
                order_item_inx[mapped_field] = True
                fields_added = True
        material = MaterialMasterRepo.get_material_by_material_code(material_no)

        if (
            production_flag
            and material.material_type == MaterialTypes.OUTSOURCE_MATERIAL.value
        ) or (
            "batch_no" in item
            and material.material_type == MaterialTypes.OWN_MATERIAL.value
        ):

            item_category = fetch_item_category(
                material, order_type, production_flag, batch_no
            )
            if item_category or is_reset_item_category_required(
                material, order_line_db, production_flag, batch_no
            ):
                item["item_category"] = item_category
                order_item["itemCategory"] = item_category
                order_item_inx["itemCategory"] = True

        if item.get("quantity") or item.get("request_date"):

            order_schedule = {
                "itemNo": item_no,
                **(
                    {"requestDate": item["request_date"].strftime("%d/%m/%Y")}
                    if item.get("request_date")
                    else {}
                ),
                **(
                    {"requestQuantity": item["quantity"]}
                    if item.get("quantity")
                    else {}
                ),
                **(
                    {"confirmQuantity": item["quantity"]}
                    if item.get("quantity")
                    else {}
                ),
            }
            order_schedule_x = {
                "itemNo": item_no,
                "updateflag": SapUpdateFlag.INSERT.value
                if is_new
                else SapUpdateFlag.UPDATE.value,
                **({"requestDate": True} if item.get("request_date") else {}),
                **({"requestQuantity": True} if item.get("quantity") else {}),
                **({"confirmQuantity": True} if item.get("quantity") else {}),
            }

            order_schedules_in.append(order_schedule)
            order_schedules_inx.append(order_schedule_x)
        price = item.get("price_per_unit")
        if price:
            add_change_order_condition_in(
                item_no,
                price,
                material.material_type,
                order_conditions_in,
                order_conditions_in_x,
                item.get("manual_price_flag", True),
            )
        prepare_item_order_text_es18(item, order_text)
        if order_text:
            fields_added = True
        if fields_added:
            order_items_in.append(order_item)
            order_items_inx.append(order_item_inx)
    return (
        item_details,
        order_items_in,
        order_items_inx,
        order_schedules_in,
        order_schedules_inx,
        order_text,
        order_conditions_in,
        order_conditions_in_x,
    )


def prepare_item_order_text_es18(item, order_text):
    text_fields = [
        "internal_comments_to_warehouse",
        "external_comments_to_customer",
        "remark",
        "sale_text1",
        "sale_text2",
        "sale_text3",
        "sale_text4",
        "item_note",
        "pr_item_text",
        "lot_no",
        "production_memo",
    ]
    for field in text_fields:
        if field in item and item[field] is not None:
            note_value = item[field]
            if field == "item_note":
                if item.production_flag == ProductionFlag.NOT_PRODUCED.value:
                    note_value = f"{ITEM_NOTE_WHEN_NOT_PRODUCED} {note_value}"
                elif (
                    item.production_flag == ProductionFlag.PRODUCED.value
                    and note_value.startswith(ITEM_NOTE_WHEN_NOT_PRODUCED)
                ):
                    note_value = note_value[4:]

            order_text.append(
                {
                    "itemNo": item["item_no"],
                    "textId": MAPPING_ITEM_ADDITIONAL_FIELDS.get(field),
                    "textLineList": [
                        {"textLine": text} for text in note_value.split("\n")
                    ]
                    if note_value
                    else [],
                }
            )


def params_for_es18_edit_flow(data, order_type, is_new=False):
    input_data = data["input"]
    header_details = input_data["header_details"]
    item_details = input_data["item_details"]
    item_details = sorted(item_details, key=lambda x: int(x["item_no"]))

    order_header_in, order_header_in_x, order_text = header_params_es18(header_details)
    order = OrderRepo.get_order_by_so_no(header_details["so_no"])
    order_lines_by_item_no = OrderLineRepo.get_order_line_by_order_distinct_item_no(
        order
    )
    item_otc_dict = {}
    item_ship_to_dict = {}
    order_otc_partner_addresses = []
    partner_addresses = []
    for item in item_details:
        if "ship_to" in item and item["ship_to"]:
            item_no = item["item_no"]
            ship_to = str(item["ship_to"] or "").strip().split("-")[0] or ""
            item_ship_to_dict[item_no] = ship_to

    for line in order_lines_by_item_no.values():
        if (
            line.otc_ship_to
            and line.item_no in item_ship_to_dict
            and item_ship_to_dict[line.item_no].strip() == line.otc_ship_to.sold_to_code
        ):
            item_otc_dict[line.item_no] = line.otc_ship_to.address.address_code
            order_otc_partner_addresses.append(line.otc_ship_to.address)
    partner_address_params_es18(order_otc_partner_addresses, partner_addresses)
    handle_bom_child(item_details, order_lines_by_item_no)
    order_partners = partner_param_es18(header_details, item_details, item_otc_dict)

    (
        item_details_x,
        orderItemsIn,
        orderItemsInX,
        orderSchedulesIn,
        orderSchedulesInx,
        order_text,
        order_conditions_in,
        order_conditions_in_x,
    ) = item_params_es18(
        item_details, order_text, order_type, is_new, order_lines_by_item_no, order
    )
    es18_params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": header_details["so_no"],
        "testrun": False,
        "orderHeaderIn": order_header_in,
        "orderHeaderInX": order_header_in_x,
        "orderItemsIn": orderItemsIn,
        "orderItemsInx": orderItemsInX,
        **({"partnerAddresses": partner_addresses} if partner_addresses else {}),
        **({"orderSchedulesIn": orderSchedulesIn} if orderSchedulesIn else {}),
        **({"orderSchedulesInx": orderSchedulesInx} if orderSchedulesInx else {}),
        **({"orderConditionsIn": order_conditions_in} if order_conditions_in else {}),
        **(
            {"orderConditionsInX": order_conditions_in_x}
            if order_conditions_in_x
            else {}
        ),
        "orderText": order_text,
        **({"orderPartners": order_partners} if order_partners else {}),
    }
    return es18_params, item_details_x


def handle_bom_child(item_details, order_lines_by_item_no):
    parent_child_item_dict = {}
    for line in order_lines_by_item_no.values():
        if line.parent:
            parent_child_item_dict.setdefault(line.parent.item_no.zfill(6), []).append(
                line
            )
    for item in item_details:
        item_no = item["item_no"].zfill(6)
        order_line_db = order_lines_by_item_no.get(item["item_no"])
        parent = order_line_db.parent
        bom = order_line_db.bom_flag
        bom_parent = is_bom_parent(bom, parent)
        if bom_parent:
            if item_no in parent_child_item_dict:
                child_items = parent_child_item_dict[item_no]
                for child_item in child_items:
                    existing_child = next(
                        (
                            existing_item
                            for existing_item in item_details
                            if existing_item["id"] == str(child_item.id)
                        ),
                        None,
                    )
                    if existing_child:
                        existing_child.update(
                            {
                                **{
                                    key: value
                                    for key, value in item.items()
                                    if key not in existing_child
                                }
                            }
                        )
                    else:
                        child_data = {
                            "id": str(child_item.id),
                            "item_no": child_item.item_no,
                            "material_no": child_item.material_code,
                            **{
                                key: value
                                for key, value in item.items()
                                if key not in ["id", "item_no", "material_no"]
                            },
                        }
                        item_details.append(child_data)


def prepare_order_texts_es_18_for_split(order_texts, parent_line, split_line_input):
    for key, value in mapping_split_item_additional_fields.items():
        order_text = {
            "itemNo": split_line_input.item_no.zfill(6),
            "textId": value,
            "textLineList": [],
        }
        additional_text_value = getattr(split_line_input, key)
        if not additional_text_value and not split_line_input.is_parent and parent_line:
            additional_text_value = getattr(parent_line, key)
        if additional_text_value:
            if "item_note_cip" == key:
                if (
                    ProductionFlag.NOT_PRODUCED.value
                    == split_line_input.production_flag
                ):
                    if not additional_text_value.startswith(
                        SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX
                    ):
                        additional_text_value = (
                            SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX
                            + additional_text_value
                        )
                else:
                    additional_text_value = additional_text_value.replace(
                        SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX, "", 1
                    )
            order_text["textLineList"].extend(
                {"textLine": text} for text in additional_text_value.split("\n")
            )
            order_texts.append(order_text)


def prepare_order_partners_es_18(order_line_input, order_line_db):
    return {
        "partnerRole": "WE",
        "partnerNumb": order_line_db.ship_to.split(" - ")[0],
        "itemNo": order_line_input.item_no.zfill(6),
    }


def prepare_order_schedules_es_18(
    order_line_input,
    order_line_db,
    cp_response_item,
    is_split_flow=False,
    is_split_line=False,
):
    item_no = order_line_input.item_no.zfill(6)
    order_schedule_in = {
        "itemNo": item_no,
        "scheduleLine": "0001",
    }
    quantity = round_qty_decimal(order_line_db.quantity)
    if is_split_flow:
        quantity = round_qty_decimal(order_line_input.quantity)
    order_schedule_in.update(
        {
            "requestQuantity": quantity,
            "confirmQuantity": quantity,
        }
    )
    request_date = order_line_input.request_date.strftime(DMY_FORMAT)
    if cp_response_item:
        request_date = cp_response_item.get("confirm_date")
    order_schedule_in.update(
        {
            "requestDate": request_date,
        }
    )
    order_schedule_inx = {
        "itemNo": item_no,
        "scheduleLine": SAP_SCHEDULE_LINE_KEY,
        "updateflag": SAP_FLAG.INSERT.value if is_split_line else SAP_FLAG.UPDATE.value,
        "requestDate": True,
        "requestQuantity": True,
        "confirmQuantity": True,
    }
    return order_schedule_in, order_schedule_inx


def prepare_order_items_es_18(
    order_line_input,
    order_line_db,
    parent_line,
    cp_response_item=None,
    is_split_flow=False,
    is_split_line=False,
    is_after_cp_confirm_pop_up=False,
):
    item_no = order_line_input.item_no.zfill(6)
    order_item_in = {
        "itemNo": item_no,
        "material": order_line_db.material.material_code,
    }
    order_item_inx = {
        "itemNo": item_no,
        "updateflag": SAP_FLAG.INSERT.value if is_split_line else SAP_FLAG.UPDATE.value,
    }
    target_qty = round_qty_decimal(order_line_db.quantity)
    if is_split_flow:
        target_qty = round_qty_decimal(order_line_input.quantity)
    order_item_in.update(
        {
            "targetQty": target_qty,
        }
    )
    order_item_inx.update(
        {
            "targetQty": True,
        }
    )
    if parent_line:
        order_item_in.update(
            {
                "parentItemNo": parent_line.item_no.zfill(6),
            }
        )
        order_item_inx.update(
            {
                "parentItemNo": True,
            }
        )
    if is_split_line:
        for key, sap_field_name in mapping_split_item_fields.items():
            if key == "quantity":
                continue
            field_value = getattr(order_line_db, key)
            if sap_field_name == "plant":
                if is_after_cp_confirm_pop_up and getattr(order_line_input, key):
                    field_value = getattr(order_line_input, key)
                elif cp_response_item:
                    field_value = cp_response_item.get(field_value, "")
            if field_value:
                order_item_in.update(
                    {
                        sap_field_name: field_value,
                    }
                )
                order_item_inx.update(
                    {
                        sap_field_name: True,
                    }
                )
    return order_item_in, order_item_inx


def prepare_split_line_child_parent_dict(
    is_bom, original_line_items, split_line_child_parent, split_line_items
):
    original_line_parent = None
    split_line_parent = None
    for original_line_input in original_line_items:
        if is_bom:
            if original_line_input.is_parent:
                original_line_parent = original_line_input
            else:
                split_line_child_parent[
                    original_line_input.item_no
                ] = original_line_parent
    for split_line_input in split_line_items:
        if is_bom:
            if split_line_input.is_parent:
                split_line_parent = split_line_input
            else:
                split_line_child_parent[split_line_input.item_no] = split_line_parent


def prepare_params_for_es_18_split(
    cp_response_item_dict,
    order_items_in,
    order_items_inx,
    order_schedules_in,
    order_schedules_inx,
    original_order_lines_obj_dict,
    split_line_child_parent,
    line_input,
    order_texts,
    order_partners,
    order_header_in,
    is_split_line=False,
    is_after_cp_confirm_pop_up=False,
):
    line_id = line_input.id
    if is_split_line:
        line_id = line_input.original_item_id

    original_line_db = original_order_lines_obj_dict.get(line_id)
    if not order_header_in:
        order_header_in.update(
            {
                "po_no": original_line_db.order.po_no,
            }
        )
    parent_line = None
    item_no = line_input.item_no
    if split_line_child_parent and split_line_child_parent.get(item_no):
        parent_line = split_line_child_parent.get(item_no)
    cp_response_item = None
    if cp_response_item_dict and cp_response_item_dict.get(item_no):
        cp_response_item = cp_response_item_dict.get(item_no)
    order_item_in, order_item_inx = prepare_order_items_es_18(
        line_input,
        original_line_db,
        parent_line,
        cp_response_item,
        is_split_flow=True,
        is_split_line=is_split_line,
        is_after_cp_confirm_pop_up=is_after_cp_confirm_pop_up,
    )
    order_items_in.append(order_item_in)
    order_items_inx.append(order_item_inx)
    order_schedule_in, order_schedule_inx = prepare_order_schedules_es_18(
        line_input,
        original_line_db,
        cp_response_item,
        is_split_flow=True,
        is_split_line=is_split_line,
    )
    order_schedules_in.append(order_schedule_in)
    order_schedules_inx.append(order_schedule_inx)
    if is_split_line:
        if original_line_db.ship_to:
            order_partners.append(
                prepare_order_partners_es_18(line_input, original_line_db)
            )
        prepare_order_texts_es_18_for_split(order_texts, parent_line, line_input)


def prepare_es_18_payload_for_split(
    so_no,
    original_line_items,
    split_line_items,
    original_order_lines_obj_dict,
    is_bom=False,
    split_line_child_parent=None,
    cp_item_messages=None,
    is_after_cp_confirm_pop_up=False,
):
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_partners = []
    order_texts = []
    order_header_in = {}
    if not split_line_child_parent and is_bom:
        split_line_child_parent = {}
        prepare_split_line_child_parent_dict(
            is_bom, original_line_items, split_line_child_parent, split_line_items
        )
    cp_response_item_dict = {}
    if cp_item_messages:
        cp_response_item_dict = {
            cp_item_message.get("item_no"): cp_item_message
            for cp_item_message in cp_item_messages
        }

    for original_line_input in original_line_items:
        prepare_params_for_es_18_split(
            cp_response_item_dict,
            order_items_in,
            order_items_inx,
            order_schedules_in,
            order_schedules_inx,
            original_order_lines_obj_dict,
            split_line_child_parent,
            original_line_input,
            order_texts,
            order_partners,
            order_header_in,
            is_split_line=False,
            is_after_cp_confirm_pop_up=is_after_cp_confirm_pop_up,
        )

    for split_line_input in split_line_items:
        prepare_params_for_es_18_split(
            cp_response_item_dict,
            order_items_in,
            order_items_inx,
            order_schedules_in,
            order_schedules_inx,
            original_order_lines_obj_dict,
            split_line_child_parent,
            split_line_input,
            order_texts,
            order_partners,
            order_header_in,
            is_split_line=True,
            is_after_cp_confirm_pop_up=is_after_cp_confirm_pop_up,
        )

    es_18_params_split = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderHeaderIn": order_header_in,
        "orderheaderInx": {},
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
        "orderText": order_texts,
    }

    if not order_partners:
        es_18_params_split.pop("orderPartners")

    return es_18_params_split


def get_order_mapping_fields(order_header):
    return {
        "so_no": order_header["saleDocument"],
        "po_no": order_header["poNo"],
        "price_date": DateHelper.sap_str_to_iso_str(order_header["priceDate"]),
        "request_date": DateHelper.sap_str_to_iso_str(order_header["reqDate"]),
        "payment_term": order_header["paymentTerms"],
        "incoterms_2": order_header["incoterms2"],
        "order_date": DateHelper.sap_str_to_iso_str(order_header.get("createDate", "")),
        "unloading_point": order_header.get("unloadingPoint", None),
        "po_date": DateHelper.sap_str_to_iso_str(order_header.get("poDates")),
        "order_type": order_header["docType"],
        "po_number": order_header["poNo"],
        "price_group": order_header["priceGroup"],
        "sales_district": order_header["salesDistrict"],
        "shipping_condition": order_header["shippingCondition"],
        "status": ScgOrderStatus.RECEIVED_ORDER.value,
        "type": "export" if order_header["distributionChannel"] == "30" else "domestic",
        "total_price": order_header.get("orderAmtBeforeVat", None),
        "tax_amount": order_header.get("orderAmtVat", None),
        "total_price_inc_tax": order_header.get("orderAmtAfterVat", None),
        "usage": order_header.get("usage"),
        # "sales_employee": sales_employee,
        "description": order_header.get("description"),
    }


def get_order_extn_mapping_fields(order_header):
    return {
        "currency": order_header.get("currency"),
        "tax_class": order_header.get("taxClass"),
    }


def get_order_mapping_code_fields(order_header):
    return {
        "distribution_channel_code": order_header.get("distributionChannel", ""),
        "sales_org_code": order_header.get("salesOrg", ""),
        "sales_off_code": order_header.get("salesOff", ""),
        "division_code": order_header.get("division", ""),
        "customer_group": order_header.get("customerGroup", ""),
        "customer_group_1": order_header.get("customerGroup1", ""),
        "customer_group_2": order_header.get("customerGroup2", ""),
        "customer_group_3": order_header.get("customerGroup3", ""),
        "customer_group_4": order_header.get("customerGroup4", ""),
        "incoterms_1": order_header.get("incoterms1", ""),
        "sales_group_code": order_header.get("salesGroup", ""),
        "currency": order_header.get("currency", ""),
    }


def get_order_mapping_id_fields(order_header):
    return {
        "distribution_channel": get_distribution_channel_id_from_code(
            order_header["distributionChannel"]
        ),
        "sales_organization": get_sales_org_id_from_code(order_header["salesOrg"]),
        "division": get_division_id_from_code(order_header["division"]),
        "customer_group": get_customer_group_id_from_code(
            order_header["customerGroup"], "customerGroup"
        ),
        "customer_group_1": get_customer_group_id_from_code(
            order_header.get("customerGroup1"), "customerGroup1"
        ),
        "customer_group_2": get_customer_group_id_from_code(
            order_header.get("customerGroup2"), "customerGroup2"
        ),
        "customer_group_3": get_customer_group_id_from_code(
            order_header.get("customerGroup3"), "customerGroup3"
        ),
        "customer_group_4": get_customer_group_id_from_code(
            order_header.get("customerGroup4"), "customerGroup4"
        ),
        "incoterms_1": get_incoterms_id_from_code(order_header["incoterms1"]),
        "sales_group": get_sales_group_id_from_code(order_header["salesGroup"]),
        "sales_office": get_sales_office_group_id_from_code(order_header["salesOff"]),
        "currency": get_currency_id_from_code(order_header["currency"]),
    }


def get_order_mapping_otc_partneraddress(partner_address):
    return {
        "name1": partner_address.get("name"),
        "name2": partner_address.get("name2"),
        "name3": partner_address.get("name3"),
        "name4": partner_address.get("name4"),
        "city": partner_address.get("city"),
        "postal_code": partner_address.get("postleCode"),
        "district": partner_address.get("district"),
        "street_1": partner_address.get("street"),
        "street_4": partner_address.get("street1"),
        "street_2": partner_address.get("street2"),
        "street_3": partner_address.get("street3"),
        "location": partner_address.get("location"),
        "transport_zone_code": partner_address.get("transpzone"),
        # "transport_zone_name":otc_info.get("transport_zone_name"),
        "country_code": partner_address.get("country"),
        # "country_name":otc_info.get("country_name"),
        "telephone_no": partner_address.get("telephoneNo"),
        "telephone_extension": partner_address.get("telephoneNoExt"),
        "mobile_no": partner_address.get("mobileNo"),
        "fax_no": partner_address.get("faxNo"),
        "fax_no_ext": partner_address.get("faxNoExt"),
        "email": partner_address.get("email"),
        "language": partner_address.get("language", "EN"),
        "tax_number1": partner_address.get("orderTaxNumber").get("taxNumber1")
        if partner_address.get("orderTaxNumber")
        else None,
        "tax_number2": partner_address.get("orderTaxNumber").get("taxNumber2")
        if partner_address.get("orderTaxNumber")
        else None,
        "tax_id": partner_address.get("orderTaxNumber").get("taxId")
        if partner_address.get("orderTaxNumber")
        else None,
        "branch_id": partner_address.get("orderTaxNumber").get("branchId")
        if partner_address.get("orderTaxNumber")
        else None,
    }


def prepare_order_from_sap_response(sap_response):
    order_header = sap_response["orderHeaderIn"]
    order_partner_resp = sap_response["orderPartners"]
    order_partners = mapping_order_partners(order_partner_resp)
    order_text_mapping = get_data_from_order_text_cip(
        sap_response["orderText"], MappingLevel.HEADER_LEVEL
    )
    sold_to_code = order_partners["order"]["sold_to"].split("-")[0].strip()
    header_text = order_text_mapping.get(HEADER_ORDER_KEY, {})

    sap_response["order_text_mapping"] = order_text_mapping
    sap_response["order_partner_mapping"] = order_partners

    sale_org = get_sales_org_id_from_code(order_header["salesOrg"])
    order = {
        "so_no": order_header["saleDocument"],
        "distribution_channel": get_distribution_channel_id_from_code(
            order_header["distributionChannel"]
        ),
        "sales_organization": sale_org,
        "division": get_division_id_from_code(order_header["division"]),
        "request_date": DateHelper.sap_str_to_iso_str(order_header["reqDate"]),
        "ship_to": order_partners["order"]["ship_to"],
        "bill_to": order_partners["order"]["bill_to"],
        "incoterms_1": get_incoterms_id_from_code(order_header["incoterms1"]),
        "incoterms_2": order_header["incoterms2"],
        "payment_term": order_header["paymentTerms"],
        "po_no": order_header["poNo"],
        "po_number": order_header["poNo"],
        "price_group": order_header["priceGroup"],
        "price_date": DateHelper.sap_str_to_iso_str(order_header["priceDate"]),
        "customer_group": get_customer_group_id_from_code(
            order_header["customerGroup"], "customerGroup"
        ),
        "customer_group_1": get_customer_group_id_from_code(
            order_header.get("customerGroup1"), "customerGroup1"
        ),
        "customer_group_2": get_customer_group_id_from_code(
            order_header.get("customerGroup2"), "customerGroup2"
        ),
        "customer_group_3": get_customer_group_id_from_code(
            order_header.get("customerGroup3"), "customerGroup3"
        ),
        "customer_group_4": get_customer_group_id_from_code(
            order_header.get("customerGroup4"), "customerGroup4"
        ),
        "sales_district": order_header["salesDistrict"],
        "internal_comments_to_warehouse": order_text_mapping.get(
            HEADER_ORDER_KEY, {}
        ).get("internal_comments_to_warehouse"),
        "internal_comment_to_warehouse": order_text_mapping.get(
            HEADER_ORDER_KEY, {}
        ).get("internal_comments_to_warehouse"),
        "internal_comments_to_logistic": order_text_mapping.get(
            HEADER_ORDER_KEY, {}
        ).get("internal_comments_to_logistic"),
        "external_comments_to_customer": order_text_mapping.get(
            HEADER_ORDER_KEY, {}
        ).get("external_comments_to_customer"),
        "product_information": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "product_information"
        ),
        "production_information": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "product_information"
        ),
        "shipping_condition": order_header["shippingCondition"],
        "sales_group": get_sales_group_id_from_code(order_header["salesGroup"]),
        "sales_office": get_sales_office_group_id_from_code(order_header["salesOff"]),
        "currency": get_currency_id_from_code(order_header["currency"]),
        "sold_to": get_sold_to_id_from_sold_to_code(sold_to_code),
        "sold_to_code": sold_to_code,
        "status": ScgOrderStatus.RECEIVED_ORDER.value,
        "type": "export" if order_header["distributionChannel"] == "30" else "domestic",
        "po_date": DateHelper.sap_str_to_iso_str(order_header.get("poDates")),
        "order_type": order_header["docType"],
        "total_price": order_header.get("orderAmtBeforeVat", None),
        "tax_amount": order_header.get("orderAmtVat", None),
        "total_price_inc_tax": order_header.get("orderAmtAfterVat", None),
        "unloading_point": order_header.get("unloadingPoint", None),
        "port_of_loading": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "port_of_loading"
        ),
        "shipping_mark": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "shipping_mark"
        ),
        "remark": order_text_mapping.get(HEADER_ORDER_KEY, {}).get("remark"),
        "usage": order_header.get("usage"),
        # "sales_employee": sales_employee,
        "description": order_header.get("description"),
        "etd": DateHelper.sap_str_to_iso_str(header_text.get("etd")),
        "eta": DateHelper.sap_str_to_iso_str(header_text.get("eta")),
        "dlc_expiry_date": DateHelper.sap_str_to_iso_str(
            header_text.get("dlc_expiry_date")
        ),
        "dlc_latest_delivery_date": DateHelper.sap_str_to_iso_str(
            header_text.get("dlc_latest_delivery_date")
        ),
        "dlc_no": order_text_mapping.get(HEADER_ORDER_KEY, {}).get("dlc_no"),
    }

    order_extn = {
        "bu": sale_org.business_unit.code,
        "order_amt_before_vat": order_header.get("order_amt_before_vat"),
        "order_amt_vat": order_header.get("order_amt_vat"),
        "order_amt_after_vat": order_header.get("order_amt_after_vat"),
        "currency": order_header.get("currency"),
        "additional_txt_from_header": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "port_of_loading"
        ),
        "additional_txt_header_note1": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "port_of_loading"
        ),
        "additional_txt_cash": order_text_mapping.get(HEADER_ORDER_KEY, {}).get(
            "port_of_loading"
        ),
        "tax_class": order_header.get("tax_class"),
    }
    return order, order_extn


def prepare_orderlines_from_sap_response(
    sap_response,
    order_db,
    item_no_of_order_line_exits_in_database,
    order_partner,
    order_text_map,
):
    order_lines_from_resp = sap_response["orderItems"]
    # _order_schedule_from_es26 = sap_response.get("orderSchedulesIn", None)
    # order_partner = sap_response["order_partner_mapping"].get("order_lines", {})
    # order_text_resp = sap_response["order_text_mapping"]

    list_material_code = [
        order_line.get("material") for order_line in order_lines_from_resp
    ]
    materils_dic = MaterialMasterRepo.get_materials_by_code_distinct_material_code(
        list_material_code
    )

    list_order_line_create = []
    list_order_line_update = []
    list_order_line_update_fields = []
    parent_child_order_items_dict = {}

    item_status_count_dict = {
        "cancelled_item_count": 0,
        "completed_item_count": 0,
        "partial_deliver_item_count": 0,
    }

    order_items_dict = {}
    for order_line in order_lines_from_resp:
        order_line["bom_flag"] = BOM_FLAG_TRUE_VALUE == order_line.get("bomFlag")
        order_line["item_no"] = order_line.get("itemNo").lstrip("0")
        get_parent_child_item_no_dict(order_line, parent_child_order_items_dict)
        order_items_dict[order_line.get("itemNo", "").lstrip("0")] = order_line
    derive_price_and_weight_for_parent_bom(
        order_items_dict, parent_child_order_items_dict
    )

    for order_line in order_lines_from_resp:
        item_no = order_line.get("itemNo", "").lstrip("0")
        material_master = materils_dic.get(order_line.get("material"))
        order_line_db = item_no_of_order_line_exits_in_database.get(item_no)
        order_line["item_no"] = item_no
        derived_order_partners = get_data_from_order_partner_cip(
            order_partner.get(order_line.get("itemNo", "")),
            MappingLevel.ITEM_LEVEL,
        )
        line_data = {
            "order_id": order_db.id if order_db else None,
            "quantity": order_line.get("orderQty", 0),
            "sales_unit": order_line.get("salesUnit", None),
            "plant": order_line.get("plant", None),
            "payment_term_item": order_line.get("paymentTerm", None),
            "po_no": order_line.get("poNumber", None),
            "item_category": order_line.get("itemCategory", None),
            "request_date": DateHelper.sap_str_to_iso_str(
                order_line.get("requestedDate")
            ),
            "shipping_point": order_line.get("shippingPoint", None),
            "reject_reason": order_line.get("reasonReject", "No"),
            "type": order_db.type
            if order_db
            else "export"
            if sap_response["orderHeaderIn"].get("distributionChannel", "") == "30"
            else "domestic",
            "item_status_en_rollback": getattr(
                order_line_db, "item_status_en_rollback", None
            ),
            "po_date": DateHelper.sap_str_to_iso_str(order_line.get("poDates")),
            "route": order_line.get("routeId", ""),
            "item_cat_eo": order_line.get("itemCategory", None),
            "delivery_tol_unlimited": True if order_line.get("untimatedTol") else False,
            "delivery_tol_over": order_line.get("deliveryTolOver", None)
            if not order_line.get("untimatedTol", None)
            else 0,
            "delivery_tol_under": order_line.get("deliveryTolOverUnder", None)
            if not order_line.get("untimatedTol", None)
            else 0,
            "delivery_quantity": order_line.get("deliveryQty", None),
            "product_hierarchy": order_line.get("prdHierachy", None),
            "weight": order_line.get("netWeight", None),
            "weight_unit": order_line.get("weightUnit", "TON"),
            "gross_weight_ton": order_line.get("grossWeightTon", None),
            "net_weight_ton": order_line.get("netWeightTon", None),
            "weight_unit_ton": order_line.get("weightUnitTon", None),
            "prc_group_1": order_line.get("materialGroup1", None),
            "route_name": order_line.get("routeName", ""),
            "material_group2": order_line.get("materialGroup1", ""),
            "sap_confirm_qty": order_line.get("comfirmQty", None),
            "material_code": order_line.get("material"),
            "condition_group1": order_line.get("conditionGroup1", None),
            "ship_to": derived_order_partners.get("ship_to", None),
            "po_sub_contract": order_line.get("poSubcontract", ""),
            "po_status": order_line.get("poStatus", ""),
            "original_request_date": DateHelper.sap_str_to_iso_str(
                order_line.get("shiptToPODate")
            )
            if order_line.get("shiptToPODate")
            else None,
            "pr_no": order_line.get("purchaseNo", ""),
            "pr_item": order_line.get("prItem", ""),
            "assigned_quantity": round(order_line.get("comfirmQty", 0), 3),
            "confirm_quantity": round(order_line.get("comfirmQty", 0), 3),
            "confirmed_date": order_line.get("request_date"),
            "price_currency": order_line.get("priceCurrency", None),
            "net_price": order_line.get("totalNetPrice", None),
            "material_id": getattr(material_master, "id", None),
            "bom_flag": order_line.get("bom_flag"),
        }

        line_data.update(
            get_line_status_from_es26_cip(order_line, item_status_count_dict)
        )
        line_data.update(
            get_data_from_order_text_cip(
                order_text_map.get(order_line.get("itemNo")),
                MappingLevel.ITEM_LEVEL,
            )
        )

        line_data.update(
            {
                "sale_text1": order_line.get("saleText1_th"),
                "sale_text2": order_line.get("saleText2_th"),
                "sale_text3": order_line.get("saleText3_th"),
                "sale_text4": order_line.get("saleText4_th"),
            }
        )

        if not order_line_db:
            so_no = sap_response["orderHeaderIn"]["saleDocument"]
            logging.info(
                f"[Sync_Es26] [New items] Order {so_no}: Item {item_no} is not exist in the database."
                f" creating it with the provided data from SAP: {line_data}"
            )
            _order_line = sap_migration_models.OrderLines(
                item_no=item_no,
                **line_data,
            )
            list_order_line_create.append(_order_line)
        else:
            logging.info(
                f"[Sync_Es26 Existing items] Order : {order_db.so_no}, "
                f"item : {item_no} exists in the DB and its DB quantity :{order_line_db.quantity} "
                f"updated to:{line_data.get('quantity', '')}, DB plant: {order_line_db.plant} updated to:"
                f"{line_data.get('plant', '')}, DB request_date: {order_line_db.request_date} updated to: "
                f"{line_data.get('request_date', '')}, DB assigned_quantity: {order_line_db.assigned_quantity}"
                f" updated to: {line_data.get('assigned_quantity', '')} db item_category: {order_line_db.item_category}"
                f" updated to: {line_data.get('item_category', '')}"
            )

            order_line_db.__dict__.update(
                **line_data,
            )
            list_order_line_update.append(order_line_db)
            if not list_order_line_update_fields:
                list_order_line_update_fields = line_data.keys()

    return (
        list_order_line_create,
        list_order_line_update,
        list_order_line_update_fields,
        parent_child_order_items_dict,
    )


def get_incoterms_id_from_code(code):
    if not code:
        return None
    instance = master_data_models.Incoterms1Master.objects.filter(code=code).first()
    return instance or None


def get_distribution_channel_id_from_code(code):
    if not code:
        return None
    instance = master_data_models.DistributionChannelMaster.objects.filter(
        code=code
    ).first()
    return instance or None


def get_sales_org_id_from_code(code):
    if not code:
        return None
    instance = master_data_models.SalesOrganizationMaster.objects.filter(
        code=code
    ).first()
    return instance or None


def get_division_id_from_code(code):
    if not code:
        return None
    instance = master_data_models.DivisionMaster.objects.filter(code=code).first()
    return instance or None


def get_customer_group_id_from_code(code, group):
    if not code:
        return None
    if group == "customerGroup":
        instance = master_data_models.CustomerGroupMaster.objects.filter(
            code=code
        ).first()
    elif group == "customerGroup1":
        instance = master_data_models.CustomerGroup1Master.objects.filter(
            code=code
        ).first()
    elif group == "customerGroup2":
        instance = master_data_models.CustomerGroup2Master.objects.filter(
            code=code
        ).first()
    elif group == "customerGroup3":
        instance = master_data_models.CustomerGroup3Master.objects.filter(
            code=code
        ).first()
    elif group == "customerGroup4":
        instance = master_data_models.CustomerGroup4Master.objects.filter(
            code=code
        ).first()
    return instance or None


def get_customer_group1_id_from_code(code):
    if not code:
        return None
    instance = master_data_models.CustomerGroup1Master.objects.filter(code=code).first()
    return instance or None


def get_sales_group_id_from_code(code):
    if not code:
        return None
    instance = sap_migration_models.SalesGroupMaster.objects.filter(code=code).first()
    return instance or None


def get_sales_office_group_id_from_code(code):
    if not code:
        return None
    instance = sap_migration_models.SalesOfficeMaster.objects.filter(code=code).first()
    return instance or None


def get_currency_id_from_code(code):
    if not code:
        return None
    instance = sap_migration_models.CurrencyMaster.objects.filter(code=code).first()
    return instance or None


def get_sold_to_id_from_sold_to_code(sold_to_code):
    if not sold_to_code:
        return None
    instance = master_data_models.SoldToMaster.objects.filter(
        sold_to_code=sold_to_code
    ).first()
    return instance or None


def is_reset_item_category_required(material, order_line, production_flag, batch_no):
    return (
        material
        and order_line
        and (
            (
                material.material_type == MaterialTypes.OWN_MATERIAL.value
                and material.batch_flag
                and not order_line.batch_choice_flag
                and batch_no
            )
            or (
                material.material_type == MaterialTypes.OUTSOURCE_MATERIAL.value
                and production_flag
                and order_line.production_flag == ProductionFlag.NOT_PRODUCED.value
                and production_flag == ProductionFlag.PRODUCED.value
            )
        )
    )
