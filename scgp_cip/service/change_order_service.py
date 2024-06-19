# TODO: REVISIT NAME
import logging
import time
import uuid
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction

from common.cp.cp_helper import filter_cp_order_line
from common.helpers import update_instance_fields_from_dic
from common.sap.sap_api import SapApiRequest
from scg_checkout.graphql.enums import (
    RealtimePartnerType,
    SapUpdateFlag,
    ScgOrderStatus,
    ScgOrderStatusSAP,
)
from scg_checkout.graphql.helper import update_order_status
from scg_checkout.graphql.implementations.sap import (
    get_error_messages_from_sap_response_for_change_order,
)
from scgp_cip.common.constants import (
    BOM_FLAG_TRUE_VALUE,
    DEFAULT_ITEM_NO,
    HEADER_ORDER_KEY,
    SAP_RESPONSE_TRUE_VALUE,
)
from scgp_cip.common.enum import (
    CIPOrderPaymentType,
    CPRequestType,
    Es26ConditionType,
    MappingLevel,
    MaterialTypes,
    ProductionFlag,
)
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order.sale_organization_master_repo import SalesOrganizationMasterRepo
from scgp_cip.dao.order.sales_group_master_repo import SalesGroupMasterRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.service.create_order_service import call_cp
from scgp_cip.service.helper.change_order_helper import (
    column_mapping_for_order,
    column_mapping_for_order_extension,
    column_mapping_for_order_line,
    derive_enable_split_flag,
    derive_price_and_weight_for_parent_bom,
    extract_es_26_res_for_change_order,
    get_data_from_order_partner_cip,
    get_data_from_order_text_cip,
    get_order_extn_mapping_fields,
    get_order_mapping_code_fields,
    get_order_mapping_fields,
    get_order_mapping_id_fields,
    get_order_mapping_otc_partneraddress,
    get_parent_child_item_no_dict,
    get_sold_to_id_from_sold_to_code,
    params_for_es18_edit_flow,
    prepare_es_18_payload_for_split,
    prepare_orderlines_from_sap_response,
)
from scgp_cip.service.helper.create_order_helper import (
    generate_temp_so_no,
    get_sap_warning_messages,
)
from scgp_cip.service.helper.order_helper import (
    derive_order_status,
    get_line_status_from_es26_cip,
)
from scgp_cip.service.integration.integration_service import get_order_details


def call_es_26_and_extract_response(info, so_no):
    es_26_response = get_order_details(so_no=so_no)
    data = es_26_response.get("data", [])[0]
    response = extract_es_26_res_for_change_order(data)
    response.update(get_order_mapping_code_fields(data.get("orderHeaderIn")))
    order_partner_sap = data.get("orderPartners", [])
    one_time_flag = get_one_time_customer_flag_from_sap_response(order_partner_sap)

    item_no_order_partner_dict = get_order_partner_dic_from_sap_response(
        order_partner_sap
    )

    item_no_order_texts_dict = get_order_text_dic_from_sap_response(
        data.get("orderText", [])
    )
    response.update(
        get_data_from_order_partner_cip(
            item_no_order_partner_dict.get(DEFAULT_ITEM_NO, []),
            MappingLevel.HEADER_LEVEL,
        )
    )
    response.update(
        get_data_from_order_text_cip(
            item_no_order_texts_dict.get(DEFAULT_ITEM_NO, []), MappingLevel.HEADER_LEVEL
        )
    )

    derive_order_items_for_change_order_data(
        response, item_no_order_partner_dict, item_no_order_texts_dict
    )
    response["one_time_flag"] = one_time_flag
    if response.get("sales_org_code"):
        sales_org_instance = SalesOrganizationMasterRepo.get_sale_organization_by_code(
            response.get("sales_org_code")
        )
        info.variable_values.update({"sales_org_instance": sales_org_instance})
    order = OrderRepo.get_order_by_so_no(so_no)
    info.variable_values.update({"order_instance": order})
    return response


def get_one_time_customer_flag_from_sap_response(order_partner_sap):
    return (
        SAP_RESPONSE_TRUE_VALUE == order_partner_sap[0].get("onetimeFlag")
        if order_partner_sap
        else False
    )


def get_order_partner_dic_from_sap_response(order_partner_sap):
    item_no_order_partner_dict = {}
    for partner in order_partner_sap:
        partner_item_no = partner.get("itemNo", DEFAULT_ITEM_NO)
        item_no_order_partner_dict.setdefault(partner_item_no, []).append(partner)
    return item_no_order_partner_dict


def get_order_text_dic_from_sap_response(order_texts_sap):
    item_no_order_texts_dict = {}
    for order_text in order_texts_sap:
        order_text_item_no = order_text.get("ItemNo", DEFAULT_ITEM_NO)
        item_no_order_texts_dict.setdefault(order_text_item_no, []).append(order_text)
    return item_no_order_texts_dict


def derive_order_items_for_change_order_data(
    data, item_no_order_partner_dict, item_no_order_texts_dict
):
    order_items = data.get("order_items", [])
    parent_child_order_items_dict = {}
    order_condition_sap = data.get("order_condition", [])
    item_no_condition_dict = {}
    for condition in order_condition_sap:
        condition_item_no = condition.get("itemNo", DEFAULT_ITEM_NO)
        item_no_condition_dict.setdefault(condition_item_no, []).append(condition)
    item_status_count_dict = {
        "cancelled_item_count": 0,
        "completed_item_count": 0,
        "partial_deliver_item_count": 0,
    }
    order_line_db_dict_by_item_no = OrderLineRepo.get_order_line_dict_by_so_no(
        data.get("so_no")
    )
    order_items_dict = {}
    order_type = data.get("order_type")
    order_item_count = len(order_items)

    for order_item in order_items:
        item_no = order_item.get("itemNo").lstrip("0")
        order_item["item_no"] = item_no
        order_item.update(
            get_line_status_from_es26_cip(order_item, item_status_count_dict)
        )

        order_item.update(
            get_data_from_order_text_cip(
                item_no_order_texts_dict.get(order_item.get("itemNo")),
                MappingLevel.ITEM_LEVEL,
            )
        )

        item_conditions = item_no_condition_dict.get(order_item["itemNo"], [])
        for condition in item_conditions:
            if Es26ConditionType.SERVICE_MAT_NO_PRICE_IN_SAP.value == condition.get(
                "conditionType"
            ) and MaterialTypes.SERVICE_MATERIAL.value == str(
                order_item.get("materialType", "")
            ):
                order_item["manual_price_flag"] = True

        if item_no_order_partner_dict.get(order_item["itemNo"]):
            order_item.update(
                get_data_from_order_partner_cip(
                    item_no_order_partner_dict.get(order_item["itemNo"]),
                    MappingLevel.ITEM_LEVEL,
                )
            )
        order_item["bom_flag"] = BOM_FLAG_TRUE_VALUE == order_item.get("bomFlag")
        order_item["original_request_date"] = order_item.get("shiptToPODate")
        order_line_instance = order_line_db_dict_by_item_no.get(order_item["item_no"])
        order_item["order_line_instance"] = order_line_instance
        get_parent_child_item_no_dict(order_item, parent_child_order_items_dict)
        if not order_items_dict.get(item_no):
            order_items_dict[item_no] = order_item
        if order_type == CIPOrderPaymentType.CASH.value:
            order_item["is_split_enabled"] = False
    data["status"] = derive_order_status(item_status_count_dict, order_item_count)
    derive_enable_split_flag(
        order_items_dict, order_type, parent_child_order_items_dict
    )
    derive_price_and_weight_for_parent_bom(
        order_items_dict, parent_child_order_items_dict
    )
    data["order_items"] = order_items


def change_order_update(data):
    try:
        success = True
        es18_response = call_es18(data)

        (
            sap_order_messages,
            sap_item_messages,
            is_being_process,
            sap_success,
        ) = get_error_messages_from_sap_response_for_change_order(es18_response)
        sap_warning_messages = get_sap_warning_messages(es18_response)
        if sap_order_messages or sap_item_messages:
            success = False
            # TODO pass  is_being_process in response
        response = {
            "success": success,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
            "sap_warning_messages": sap_warning_messages,
            "sap_response": es18_response,
        }
        return response
    except Exception as e:
        logging.exception("Call ES-18 Exception")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def call_cp_change_order_update(data):
    input_data = data["input"]
    item_details = input_data["item_details"]
    cp_eligible_item_ids = []
    item_details_dict = {}
    for item in item_details:
        if (
            "quantity" in item
            or "plant" in item
            or "request_date" in item
            or (
                "production_flag" in item
                and item["production_flag"] == ProductionFlag.PRODUCED.value
            )
        ):
            cp_eligible_item_ids.append(item["id"])

            item_details_dict[item["item_no"]] = {
                "quantity": item.get("quantity"),
                "sales_unit": item.get("unit"),
                "request_date": item.get("request_date"),
                "ship_to": item.get("ship_to"),
                "plant": item.get("plant"),
            }

    if not cp_eligible_item_ids:
        return {"success": True}

    order_lines = OrderLineRepo.get_order_lines(cp_eligible_item_ids)

    cp_order_lines = filter_cp_order_line(order_lines, item_details=item_details)

    if cp_order_lines:
        updated_item_detail_fields(cp_order_lines, item_details_dict)
        order = OrderRepo.get_order_by_id(order_lines.first().order_id)
        cp_item_messages, cp_error_messages, cp_confirm_date_mismatch = call_cp(
            order, order.so_no, cp_order_lines, CPRequestType.CHANGED.value
        )

        if (cp_confirm_date_mismatch and cp_item_messages) or cp_error_messages:
            return {
                "success": False,
                "order": order,
                "cp_item_messages": cp_item_messages,
                "cp_error_messages": cp_error_messages,
            }

    return {"success": True}


def updated_item_detail_fields(cp_order_lines, item_details_dict):
    for order_line in cp_order_lines:
        item_detail = item_details_dict.get(order_line.item_no)
        if item_detail:
            for attr in ["quantity", "sales_unit", "request_date", "ship_to", "plant"]:
                new_value = item_detail.get(attr)
                if new_value is not None:
                    setattr(order_line, attr, new_value)


def call_cp_change_order(data):
    input_data = data["input"]
    item_details = input_data["item_details"]
    ids = {item["id"] for item in item_details}
    order_lines = OrderLineRepo.get_order_lines(ids)

    if order_lines:
        cp_order_lines = filter_cp_order_line(order_lines)
        if cp_order_lines:
            order = OrderRepo.get_order_by_id(order_lines.first().order_id)
            cp_item_messages, cp_error_messages, cp_confirm_date_mismatch = call_cp(
                order, order.so_no, cp_order_lines, CPRequestType.CHANGED.value
            )
            if (cp_confirm_date_mismatch and cp_item_messages) or cp_error_messages:
                return {
                    "success": False,
                    "order": order,
                    "cp_item_messages": cp_item_messages,
                    "cp_error_messages": cp_error_messages,
                }
    return {"success": True}


def change_cp_order_add_new(data):
    try:
        success = True
        input_data = data["input"]
        header_details = input_data["header_details"]
        cp_needed = True
        if "cp_need" in header_details:
            cp_needed = header_details["cp_need"]
        if cp_needed:
            result = call_cp_change_order_update(data)
            if not result.get("success"):
                return result

        order = OrderRepo.get_order_by_so_no(header_details["so_no"])

        es18_params, item_details = params_for_es18_edit_flow(
            data, order.order_type, True
        )
        response = change_order_update(es18_params)
        sap_order_messages = response.get("sap_order_messages", [])
        sap_item_messages = response.get("sap_item_messages", [])
        sap_warning_messages = get_sap_warning_messages(response)
        if sap_order_messages or sap_item_messages:
            success = False
        else:
            update_order_after_es_18(header_details, item_details, order, response)
        return {
            "success": success,
            "order": order,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
            "sap_warning_messages": sap_warning_messages,
        }
    except Exception as e:
        logging.exception("Call ES-18 Exception - Add new")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def update_order_after_es_18(header_details, item_details, order, response):
    update_order(column_mapping_for_order, header_details, order)

    update_order_extension(column_mapping_for_order_extension, header_details, order)

    update_order_lines(
        column_mapping_for_order_line, item_details, response.get("sap_response")
    )


def update_order_lines(column_mapping, item_details, response):
    order_schedule_out = response.get("orderSchedulesOut")
    item_confirm_mapping = {
        item["itemNo"].lstrip("0"): item.get("comfirmQuantity", None)
        for item in order_schedule_out
    }
    for item_detail in item_details:
        if item_detail["item_no"] in item_confirm_mapping:
            confirm_quantity = item_confirm_mapping[item_detail["item_no"]]
            item_detail["confirm_quantity"] = confirm_quantity
            item_detail["sap_confirm_qty"] = confirm_quantity
            item_detail["assigned_quantity"] = confirm_quantity
            item_detail["draft"] = False
        mapped_order_line_edited_fields = {
            column_mapping[key]: value
            for key, value in item_detail.items()
            if key in column_mapping
        }
        if mapped_order_line_edited_fields:
            instance_to_update_order_line = (
                OrderLineRepo.get_order_line_for_bulk_update(
                    mapped_order_line_edited_fields, item_detail["id"]
                )
            )
            OrderLineRepo.update_order_lines_cip(
                instance_to_update_order_line, mapped_order_line_edited_fields
            )


def update_order_extension(column_mapping, header_details, order):
    mapped_order_extension_edited_fields = {
        column_mapping.get(key, key): value
        for key, value in header_details.items()
        if key in column_mapping
    }
    if mapped_order_extension_edited_fields:
        order_extension_instance = OrderRepo.get_order_extension_for_bulk_update(
            mapped_order_extension_edited_fields, order.id
        )
        OrderRepo.update_order_extension(
            order_extension_instance, mapped_order_extension_edited_fields
        )


def update_order(column_mapping, header_details, order):
    mapped_order_edited_fields = {
        column_mapping[key]: value
        for key, value in header_details.items()
        if key in column_mapping
    }
    if mapped_order_edited_fields:
        if "sales_group_id" in mapped_order_edited_fields:
            sales_group_code = mapped_order_edited_fields["sales_group_id"]
            sales_group = SalesGroupMasterRepo.get_sales_group_by_code(sales_group_code)
            mapped_order_edited_fields["sales_group_id"] = sales_group.id or ""
        instance_to_update_header = OrderRepo.get_order_for_bulk_update(
            mapped_order_edited_fields, order
        )
        OrderRepo.bulk_update_order(
            instance_to_update_header, mapped_order_edited_fields
        )


def change_cp_order_update(data):
    success = True
    input_data = data["input"]
    header_details = input_data["header_details"]
    item_details = input_data["item_details"]
    if (not header_details or len(header_details) < 2) and (
        not item_details or len(item_details) < 1
    ):
        return {
            "success": success,
            "order": None,
            "sap_order_messages": None,
            "sap_item_messages": None,
            "warning_messages": None,
        }
    cp_needed = True
    if "cp_need" in header_details:
        cp_needed = header_details["cp_need"]
    try:
        if cp_needed:
            result = call_cp_change_order_update(data)
            if not result.get("success"):
                return result
        order = OrderRepo.get_order_by_so_no(header_details["so_no"])
        es18_params, item_details = params_for_es18_edit_flow(data, order.order_type)
        response = change_order_update(es18_params)
        sap_order_messages = response.get("sap_order_messages", [])
        sap_item_messages = response.get("sap_item_messages", [])
        warning_messages = response.get("sap_warning_messages", [])
        if sap_order_messages or sap_item_messages:
            success = False
        else:
            update_order_after_es_18(header_details, item_details, order, response)
        return {
            "success": success,
            "order": order,
            "sap_order_messages": sap_order_messages,
            "sap_item_messages": sap_item_messages,
            "warning_messages": warning_messages,
        }
    except Exception as e:
        logging.exception("Call ES-18 Exception")
        if isinstance(e, ConnectionError):
            raise ValueError("Error Code : 500 - Internal Server Error")
        raise ImproperlyConfigured(e)


def call_es18(request_payload_es_18):
    start_time = time.time()
    logging.info(f" request_payload_es_18: {request_payload_es_18}")
    es_18_response = SapApiRequest.call_es_18_update(request_payload_es_18)
    end_time = time.time()
    processing_time = end_time - start_time
    logging.info(
        f" response es_18: {es_18_response}, Processing Time: {processing_time} seconds"
    )
    return es_18_response


def process_change_order_edit_es_18(input_data):
    try:
        so_no = input_data.get("so_no")
        logging.info(
            f"[No Ref Contract -  Change Order:Edit] via ES 18for Order :  {so_no}"
        )
        # TODO prepare payload and call api
    except ValidationError as e:
        raise e
    except Exception as e:
        raise ImproperlyConfigured(e)


def cip_sync_order_data(info, so_no):
    es_26_response = get_order_details(so_no=so_no)
    if not es_26_response:
        raise ValueError(f"Error retrieving Order {so_no} from SAP")
    return cip_sync_order_data_from_sap(info, so_no, es_26_response)


@transaction.atomic
def cip_sync_order_data_from_sap(info, so_no, es_26_response):
    order_db = OrderRepo.get_order_by_so_no(so_no)
    data = es_26_response.get("data", [])[0]
    order = get_order_mapping_fields(data.get("orderHeaderIn"))
    order.update(get_order_mapping_id_fields(data.get("orderHeaderIn")))
    order_extn = get_order_extn_mapping_fields(data.get("orderHeaderIn"))
    order_partner_sap = data.get("orderPartners", [])
    one_time_flag = get_one_time_customer_flag_from_sap_response(order_partner_sap)

    item_no_order_partner_dict = get_order_partner_dic_from_sap_response(
        order_partner_sap
    )
    order.update(
        get_data_from_order_partner_cip(
            item_no_order_partner_dict.get(DEFAULT_ITEM_NO, []),
            MappingLevel.HEADER_LEVEL,
            True,
        )
    )
    order.update(
        {"sold_to": get_sold_to_id_from_sold_to_code(order.get("sold_to_code"))}
    )

    item_no_order_texts_dict = get_order_text_dic_from_sap_response(
        data.get("orderText", [])
    )
    order.update(
        get_data_from_order_text_cip(
            item_no_order_texts_dict.get(DEFAULT_ITEM_NO, []), "order"
        )
    )
    order_extn.update(
        get_data_from_order_text_cip(
            item_no_order_texts_dict.get(DEFAULT_ITEM_NO, []), "order_extension"
        )
    )
    order_extn.update(
        {"bu": order.get("sales_organization").business_unit.code}
        if order.get("sales_organization")
        and order.get("sales_organization").business_unit
        else {}
    )
    item_no_of_order_line_exits_in_database = (
        OrderLineRepo.get_order_line_by_order_distinct_item_no(order_db)
    )
    (
        list_order_line_create,
        list_order_line_update,
        list_order_line_update_fields,
        parent_child_order_items_dict,
    ) = prepare_orderlines_from_sap_response(
        data,
        order_db,
        item_no_of_order_line_exits_in_database,
        item_no_order_partner_dict,
        item_no_order_texts_dict,
    )
    # delete draftlines before inserting the new lines
    if order_db:
        list_line_ids = list(map(lambda x: x.id, list_order_line_update))
        OrderLineRepo.delete_all_order_lines_excluding_ids(order_db, list_line_ids)
        update_instance_fields_from_dic(order_db, order)

        order = order_db
        order_extn_db = OrderRepo.get_order_extension_by_id(order_db.id)
    else:
        order = OrderRepo.save_order(order)
        order_extn_db = None
        for line in list_order_line_create:
            line.order_id = order.id

    if order_extn_db:
        update_instance_fields_from_dic(order_extn_db, order_extn)
        order_extn = OrderRepo.save_order_extension(order_extn_db)
    else:
        order_extn.update({"temp_order_no": so_no})
        if one_time_flag:
            update_otc_details_to_order(
                info, order_extn, item_no_order_partner_dict, order
            )
        order_extn.update({"order_id": order.id})
        order_extn = OrderRepo.save_order_extension(order_extn)

    if list_order_line_create:
        OrderLineRepo.save_order_lines(list_order_line_create)
    if list_order_line_update:
        OrderLineRepo.update_order_line_bulk(
            list_order_line_update, list_order_line_update_fields
        )
    update_orderline_bom_parent(parent_child_order_items_dict, order_db)

    max_item_no = OrderLineRepo.get_latest_item_no(order.id)
    item_no_latest = order.item_no_latest or 0
    if int(item_no_latest) < int(max_item_no):
        order.item_no_latest = str(max_item_no) or "0"
    status_en, status_thai = update_order_status(order.id)
    logging.info(
        f"[Sync_Es26] Order: {order.so_no}, DB order status: {order.status} updated to: {status_en}"
    )

    order.status = status_en
    order.status_thai = status_thai
    order = OrderRepo.save_order(order)

    return order


def update_otc_details_to_order(info, order_extn, item_no_order_partner_dict, order):
    for partner in item_no_order_partner_dict.get(HEADER_ORDER_KEY):
        partner_role = partner.get("partnerRole")
        if partner_role == RealtimePartnerType.SOLD_TO.value:
            sold_to = partner.get("address")[0]
            address = get_order_mapping_otc_partneraddress(sold_to)
            partner = create_otc_partner(info, order, address, partner_role)
            order_extn.update({"otc_sold_to": partner})
        elif partner_role == RealtimePartnerType.BILL_TO.value:
            bill_to = partner.get("address")[0]
            address = get_order_mapping_otc_partneraddress(bill_to)
            partner = create_otc_partner(info, order, address, partner_role)
            order_extn.update({"otc_bill_to": partner})
        elif partner_role == RealtimePartnerType.SHIP_TO.value:
            ship_to = partner.get("address")[0] if partner.get("address") else ""
            address = get_order_mapping_otc_partneraddress(ship_to)
            partner = create_otc_partner(info, order, address, partner_role)
            order_extn.update({"otc_ship_to": partner})


def create_otc_partner(info, order, address, partner_role):
    address.update({"created_by": info.context.user})
    address = OrderRepo.save_order_otc_partneraddress(address)
    return OrderRepo.save_order_otc_partner(
        {
            "sold_to_code": order.sold_to_code,
            "partner_role": partner_role,
            "address": address,
            "order": order,
            "created_by": info.context.user,
        }
    )


def update_orderline_bom_parent(parent_child_order_items_dict, order_db):
    for parent in parent_child_order_items_dict:
        if parent:
            child_items = parent_child_order_items_dict[parent]
            parent_line = OrderLineRepo.get_order_line_by_order_and_item_no(
                order_db, parent
            )
            OrderLineRepo.update_order_lines_parent_bom(
                order_db, parent_line, child_items
            )


def process_change_order_add_new_es_18(input_data):
    try:
        so_no = input_data.get("so_no")
        logging.info(
            f"[No Ref Contract -  Change Order:Add New] via ES 18 for Order :  {so_no}"
        )
        # TODO prepare payload and call api
    except ValidationError as e:
        raise e
    except Exception as e:
        raise ImproperlyConfigured(e)


def process_change_order_split_es_18(
    input_data,
    split_line_child_parent=None,
    cp_item_messages=None,
    is_after_cp_confirm_pop_up=False,
):
    try:
        so_no = input_data.get("so_no")
        original_line_items = input_data.get("origin_line_items")
        split_line_items = input_data.get("split_line_items")
        is_bom = input_data.get("is_bom")
        original_lines_db = OrderLineRepo.get_order_lines(
            [item.id for item in original_line_items]
        )
        original_order_lines_obj_dict = {obj.id: obj for obj in original_lines_db}
        logging.info(
            f"[No Ref Contract -  Change Order:Split] via ES 18 for Order : {so_no} on BOM mat? : {is_bom}"
        )
        es_18_params_split = prepare_es_18_payload_for_split(
            so_no,
            original_line_items,
            split_line_items,
            original_order_lines_obj_dict,
            is_bom,
            split_line_child_parent,
            cp_item_messages,
            is_after_cp_confirm_pop_up,
        )

        response = change_order_update(es_18_params_split)
        sap_order_messages = response.get("sap_order_messages", [])
        sap_item_messages = response.get("sap_item_messages", [])
        sap_response = response.get("sap_response")
        return sap_order_messages, sap_item_messages, sap_response
    except ValidationError as e:
        raise e
    except Exception as e:
        raise ImproperlyConfigured(e)


@transaction.atomic
def duplicate_order_cip(so_no, info):
    cip_sync_order_data(info, so_no)
    old_order = OrderRepo.get_order_by_so_no(so_no)
    if not old_order:
        raise ValueError(f"No order found, so_no: {so_no} ")

    old_order_lines = OrderLineRepo.get_order_lines_by_order_order_by_item_no(old_order)
    new_order = deepcopy(old_order)
    new_order.pk = None
    new_order.so_no = generate_temp_so_no()
    current_user = info.context.user
    new_order.created_by = current_user
    new_order.status = ScgOrderStatus.DRAFT.value
    new_order.status_sap = ScgOrderStatusSAP.BEING_PROCESS.value
    new_order.item_no_latest = None
    new_order.save()
    old_order_extension = OrderRepo.get_order_extension_by_id(old_order.id)
    new_order_extension = deepcopy(old_order_extension)
    new_order_extension.pk = None
    new_order_extension.temp_order_no = new_order.so_no
    new_order_extension.order = new_order

    new_order_extension.otc_sold_to = (
        duplicate_order_partners(new_order, old_order_extension.otc_sold_to)
        if old_order_extension.otc_sold_to
        else None
    )
    new_order_extension.otc_bill_to = (
        duplicate_order_partners(new_order, old_order_extension.otc_bill_to)
        if old_order_extension.otc_bill_to
        else None
    )
    new_order_extension.otc_ship_to = (
        duplicate_order_partners(new_order, old_order_extension.otc_ship_to)
        if old_order_extension.otc_ship_to
        else None
    )
    new_order_extension.created_by = current_user
    new_order_extension.last_updated_by = current_user
    OrderRepo.save_order_extension(new_order_extension)
    order_lines = []
    item_no = 0
    old_order_line_id_new_order_line_dict = {}
    for old_order_line in old_order_lines:
        item_no += 10
        new_order_line = deepcopy(old_order_line)
        old_order_line_id_new_order_line_dict[old_order_line.id] = new_order_line
        new_order_line.pk = None
        new_order_line.order = new_order

        new_order_line.otc_ship_to = (
            duplicate_order_partners(new_order, old_order_line.otc_ship_to)
            if old_order_line.otc_ship_to
            else None
        )
        new_order_line.shipping_point = ""
        new_order_line.route = ""
        new_order_line.item_no = str(item_no)
        new_order_line.delivery = None
        new_order_line.item_status_en = None
        new_order_line.item_status_th = None
        new_order_line.reject_reason = None
        new_order_line.remark = None
        new_order_line.original_request_date = None
        new_order_line.attention_type = None
        new_order_line.request_date_change_reason = None
        new_order_line.class_mark = None
        new_order_line.confirmed_date = None
        order_lines.append(new_order_line)
    OrderLineRepo.save_order_line_bulk(order_lines)
    order_line_to_update_parent = []
    for order_line in order_lines:
        if order_line.bom_flag and order_line.parent:
            order_line.parent = old_order_line_id_new_order_line_dict.get(
                order_line.parent_id
            )
            order_line_to_update_parent.append(order_line)
    if order_line_to_update_parent:
        OrderLineRepo.update_order_line_bulk(order_line_to_update_parent, ["parent"])
    return new_order


def duplicate_order_partners(new_order, old_order_partner, current_user=None):
    new_order_otc_partner_address = deepcopy(old_order_partner.address)
    new_order_otc_partner_address.pk = None
    new_order_otc_partner_address.created_by = current_user
    new_order_otc_partner_address.last_updated_by = current_user
    OrderRepo.save_order_otc_partneraddress(new_order_otc_partner_address)
    new_order_otc_partner = deepcopy(old_order_partner)
    new_order_otc_partner.pk = None
    new_order_otc_partner.order = new_order
    new_order_otc_partner.address = new_order_otc_partner_address
    new_order_otc_partner.created_by = current_user
    new_order_otc_partner.last_updated_by = current_user
    OrderRepo.save_order_otc_partner(new_order_otc_partner)
    return new_order_otc_partner


def prepare_params_for_es18_undo(so_no, order_lines, info):
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "orderItemsIn": [],
        "orderItemsInx": [],
    }
    params["orderItemsIn"].append(
        {
            "itemNo": order_lines.item_no,
            "material": order_lines.material_code,
            "targetQty": order_lines.quantity,
            "salesUnit": order_lines.sales_unit,
            "reasonReject": "",
        }
    )
    params["orderItemsInx"].append(
        {
            "itemNo": order_lines.item_no,
            "updateflag": SapUpdateFlag.UPDATE.value,
            "reasonReject": True,
        }
    )

    return params
