import logging
import re
import uuid

from django.core.exceptions import ValidationError

from common.enum import MulesoftServiceType
from common.helpers import mock_confirm_date
from common.iplan.item_level_helpers import get_product_and_ddq_alt_prod_of_order_line
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data import models
from sap_migration.graphql.enums import InquiryMethodType
from sap_migration.models import Order
from scg_checkout.graphql.enums import Es21Params, ItemDetailsEdit
from scg_checkout.graphql.helper import (
    default_param_i_plan_request,
    get_inquiry_method_params,
    call_i_plan_request_get_response,
    deepget,
    call_es21_get_response,
    default_param_i_plan_confirm,
    call_i_plan_confirm_get_response,
    default_param_i_plan_rollback,
    default_param_es_21_add_new_item,
    get_warehouse_code_from_iplan_request,
    perform_rounding_on_iplan_qty_with_decimals, add_class_mark_to_es21
)
from common.util.utility import add_lang_to_sap_text_field
from scgp_customer.graphql.helpers import (
    get_sold_to_data_from_es26,
    get_ship_to_data_from_es26,
    get_bill_to_data_from_es26
)
from scgp_export.graphql.enums import SapEnpoint
from scgp_po_upload.graphql.enums import SAP21, IPlanAcknowledge


def get_data_from_db(model, *fields, **filter):
    rs = {}
    qs = model.objects.filter(**filter).first()
    if not qs:
        return rs
    for field in fields:
        rs[field] = getattr(qs, field)
    return rs


def join_field_from_db(data: dict, keys: list):
    rs = []
    for key in keys:
        if result := data.get(key):
            rs.append(result)
    return " - ".join(rs)


def mapping_group_partner(order_header):
    mapping = {
        "customerGroup": {"model": models.CustomerGroupMaster, "fields": ["code", "name"]},
        # "customerGroup1" : {"model": models.CustomerGroup1Master, "fields": ["code", "name"]},
        # "customerGroup2" : {"model": models.CustomerGroup2Master, "fields": ["code", "name"]},
        # "customerGroup3" : {"model": models.CustomerGroup3Master, "fields": ["code", "name"]},
        "incoterms1": {"model": models.CustomerGroupMaster, "fields": ["code", "description"]},
    }
    result = {}
    for key, value in mapping.items():
        data = get_data_from_db(value['model'], *value['fields'], code=order_header[key])
        name_format = join_field_from_db(data, value['fields'])
        result[key] = name_format

    return result


def mapping_additional_data(order_texts):
    result = {}
    mapping = {
        "Z001": "internal_comments_to_warehouse",
        "Z002": "internal_comments_to_logistic",
        "Z067": "external_comments_to_customer",
        "ZK08": "production_information"
    }
    for text in order_texts:
        if text.get("textId") in mapping:
            text_line_list = text.get("textLine")
            for text_line in text_line_list:
                if isinstance(text_line, dict):
                    result[mapping.get(text.get('textId'))] = "\n".join(
                        str(text_line.get('text', ''))
                    )

    return result


def get_list_from_data(data, key):
    result = []
    for item in data:
        if key in item and isinstance(item, dict):
            result.append(item[key])
        result.append(item.get(key))
    return result


def get_data_from_es26(info, so_no):
    try:
        params = {"piMessageId": str(uuid.uuid1().int), "saleOrderNo": so_no}
        api_response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_get(
            SapEnpoint.ES_26.value,
            params
        )

        data_response = api_response.get("data", None)
        if not api_response or not data_response:
            raise ValidationError("SAP error!")
        data_response = data_response[0]

        order_header = data_response.get("orderHeaderIn", {})
        dp_no = get_list_from_data(data_response.get("dp", []), "dpNo")
        billing_no = get_list_from_data(data_response.get("billing", []), "billingNo")
        order_text = data_response.get("orderText", [])
        sold_to_data = get_sold_to_data_from_es26(data_response)
        ship_to_data = get_ship_to_data_from_es26(data_response)
        bill_to_data = get_bill_to_data_from_es26(data_response)
        eordering_status = Order.objects.filter(so_no=order_header["saleDocument"]).first()
        group_data = mapping_group_partner(order_header)
        additional_data = mapping_additional_data(order_text)

        rs = {
            "sale_group": order_header["saleDocument"],
            "contract_no": "",  # API dose not support for now
            "po_no": order_header["poNo"],
            "sold_to_name": sold_to_data.get("sold_to_name") if sold_to_data else "",
            "sold_to_address": sold_to_data.get("sold_to_address")
            if sold_to_data
            else "",
            "ship_to_name": ship_to_data.get('bill_to_name')
            if ship_to_data
            else "",
            "ship_to_address": ship_to_data.get('bill_to_address')
            if ship_to_data
            else "",
            "bill_to_party": bill_to_data.get('bill_to_name'),
            "bill_to_party_address": bill_to_data.get('bill_to_address'),
            "eordering_status": eordering_status.status,
            "order_atm_before_vat": order_header.get("orderAmtBeforeVat"),
            "order_atm_vat": order_header.get("orderAmtVat"),
            "order_atm_after_vat": order_header.get("orderAmtAfterVat"),
            "currency": order_header.get("currency"),
            "customer_group": order_header["customerGroup"],
            "request_date": order_header["reqDate"],
            "payment_terms": order_header["paymentTerms"],
            "dp_no": dp_no,
            "billing_no": billing_no,
            "incoterms_1": order_header["incoterms1"],
            "incoterms_2": order_header["incoterms2"],
            "create_date": order_header["createDate"],
            **group_data,
            **additional_data,
            'sales_group': order_header["salesGroup"],
        }

        return rs

    except Exception as e:
        raise ValueError(e)


def change_order_add_new_item_i_plan_request(order, qs_new_order_lines, manager):
    param_i_plan_request = default_param_i_plan_request(order.so_no)
    fmt_sold_to_code = (
                               order.sold_to and order.sold_to.sold_to_code or order.sold_to_code or ""
                       ).lstrip("0") or None
    inquiry_method = InquiryMethodType.DOMESTIC.value

    alt_mat_i_plan_dict, alt_mat_variant_obj_dict = {}, {}
    alt_mat_errors = []
    from scg_checkout.graphql.implementations.iplan import prepare_alternate_materials_list
    prepare_alternate_materials_list(alt_mat_i_plan_dict, alt_mat_variant_obj_dict, order,
                                     qs_new_order_lines, alt_mat_errors)
    for qs_order_line_new in qs_new_order_lines:
        request_date = qs_order_line_new.request_date and qs_order_line_new.request_date.strftime("%Y-%m-%d") or ""
        inquiry_method_params = get_inquiry_method_params(inquiry_method)
        alternate_products, product_code = get_product_and_ddq_alt_prod_of_order_line(alt_mat_i_plan_dict, order,
                                                                                      qs_order_line_new)

        request_line = {
            "lineNumber": str(qs_order_line_new.item_no),
            "locationCode": fmt_sold_to_code,
            "consignmentOrder": False,
            "productCode": product_code,
            "requestDate": f'{request_date}T00:00:00.000Z',
            "inquiryMethod": inquiry_method_params["inquiry_method"],
            "quantity": str(qs_order_line_new.quantity) if qs_order_line_new.quantity else "0",
            "unit": "ROL",
            "transportMethod": "Truck",
            "typeOfDelivery": "E",
            "useInventory": inquiry_method_params["use_inventory"],
            "useConsignmentInventory": inquiry_method_params["use_consignment_inventory"],
            "useProjectedInventory": inquiry_method_params["use_projected_inventory"],
            "useProduction": inquiry_method_params["use_production"],
            "orderSplitLogic": inquiry_method_params["order_split_logic"],
            "singleSourcing": False,
            "reATPRequired": inquiry_method_params["re_atp_required"],
            "fixSourceAssignment": qs_order_line_new.plant or "",
            "requestType": "NEW",
            "consignmentLocation": order.sale_group_code or "",
            "DDQSourcingCategories": [
                {
                    "categoryCode": order.sale_group_code or ""
                },
                {
                    "categoryCode": order.sale_org_code or ""
                }
            ]
        }
        if alternate_products and len(alternate_products):
            request_line["DDQAlternateProducts"] = alternate_products
        param_i_plan_request["DDQRequest"]["DDQRequestHeader"][0]["DDQRequestLine"].append(request_line)
    param_i_plan_request['DDQRequest']['DDQRequestHeader'][0]['DDQRequestLine'] = sorted(
        param_i_plan_request['DDQRequest']['DDQRequestHeader'][0]['DDQRequestLine'],
        key=lambda x: float(x['lineNumber'])
    )
    logging.info(f"[Domestic: change order Add new items] Calling Iplan")
    i_plan_response = call_i_plan_request_get_response(manager, param_i_plan_request, order=order)
    logging.info(f"[Domestic: change order Add new items] Called Iplan")
    perform_rounding_on_iplan_qty_with_decimals(i_plan_response)
    return i_plan_response, alt_mat_i_plan_dict, alt_mat_variant_obj_dict, alt_mat_errors


def change_order_add_new_item_es_21(order_header, list_order_line_new, response_i_plan, manager, new_items_map,
                                    need_iplan_integration=None, info=None, order=None):
    param_es_21 = default_param_es_21_add_new_item(order_header)
    mapping_order_text = {
        "internal_comments_to_warehouse": "Z001",
        "external_comments_to_customer": "Z002",
        "shipping_mark": "Z004"
    }
    for _, line in new_items_map["order_lines_in_database"].items():
        add_class_mark_to_es21(line, param_es_21)
    for order_line_new in list_order_line_new:
        item_no = order_line_new["item_no"]
        order_line_in = {
            "itemNo": item_no,
            "material": deepget(order_line_new, ItemDetailsEdit.UPDATE_ITEMS.value["material_code"], "")
        }
        order_line_inx = {
            "itemNo": item_no,
            "updateflag": "I"
        }
        for field_name_input, field_in_es21 in Es21Params.NEW_ITEM.value.items():
            if field_name_input == "plant":
                order_line_in[field_in_es21] = get_warehouse_code_from_iplan_request(response_i_plan, item_no)
                order_line_inx["plant"] = True
                continue
            if field_name_input == "request_date":
                order_line_in[field_in_es21] = order_line_new.order_information.request_date
                order_line_inx["poDate"] = True
                continue
            if field_name_input == "header_code":
                # order_line_in["poNo"] = order_header.get("po_no")
                # order_line_inx["poNo"] = True
                continue
            if field_name_input == "unlimited":
                if deepget(order_line_new, ItemDetailsEdit.NEW_ITEMS.value[field_name_input], ""):
                    order_line_in[field_in_es21] = "X"
                else:
                    order_line_in[field_in_es21] = ""
                order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
                continue
            if deepget(order_line_new, ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "") != "":
                order_line_in[field_in_es21] = deepget(order_line_new,
                                                       ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "")
                if not order_line_in[field_in_es21]:
                    order_line_in[field_in_es21] = ''
                order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
        order_line_in["refDoc"] = order_header["contract_no"]
        order_line_in["refDocIt"] = order_line_new.get("ref_doc_it") or item_no
        if not need_iplan_integration:
            logging.debug(
                f"Setting the plant {order_line_new.order_information.plant} information passed from UI {order_line_new.order_information.material_code} itemNo {order_line_new.item_no}")
            order_line_in["plant"] = order_line_new.order_information.plant
            order_line_inx["plant"] = True
        param_es_21["orderItemsIn"].append(order_line_in)
        param_es_21["orderItemsInx"].append(order_line_inx)
        order_schedules_in = {
            "itemNo": item_no.zfill(6),
            "scheduleLine": "0001"
        }
        order_schedules_inx = {
            "itemNo": item_no.zfill(6),
            "scheduleLine": "0001",
            "updateflag": "I",
            "requestDate": True,
            "requestQuantity": True,
            "confirmQuantity": True

        }
        for field_name_input, field_in_es21 in Es21Params.ORDER_SCHEDULE.value.items():
            order_schedules_in[field_in_es21] = deepget(order_line_new,
                                                        ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "")
        if response_i_plan:
            confirm_qty = response_i_plan[item_no]["quantity"] if response_i_plan[item_no][
                "onHandStock"] else 0
        else:
            confirm_qty = order_line_new.order_information.quantity
        order_schedules_in["confirmQty"] = confirm_qty
        request_date_str = deepget(order_line_new, "order_information.request_date", "")
        # SEO-7096: If iplan item status is Unplanned/Tentative mock the request date else i_plan_dispatch_date
        if response_i_plan:
            i_plan_item_status = response_i_plan[item_no]["status"]
            i_plan_dispatch_date = response_i_plan[item_no]["dispatchDate"]
            if not i_plan_dispatch_date:
                i_plan_dispatch_date = mock_confirm_date(request_date_str, i_plan_item_status)
            order_schedules_in["reqDate"] = '/'.join(i_plan_dispatch_date.split("-")[::-1])
        else:
            order_schedules_in["reqDate"] = request_date_str
        param_es_21["orderSchedulesIn"].append(order_schedules_in)
        param_es_21["orderSchedulesInx"].append(order_schedules_inx)
        if info and info.context and info.context.user and info.context.user.scgp_user:
            scgp_user = info.context.user.scgp_user
            if scgp_user and scgp_user.sap_id:
                param_es_21["sapId"] = scgp_user.sap_id
        for field, value in order_line_new.get("additional_data", {}).items():
            if field == "ship_to_party" and value:
                order_partner = {
                    "partnerRole": "WE",
                    "partnerNumb": value,
                    "itemNo": item_no.zfill(6),
                }
                param_es_21["orderPartners"].append(order_partner)
                continue
            if field != "ship_to_party":
                order_text = {
                    "itemNo": item_no.zfill(6),
                    "textId": mapping_order_text.get(field),
                    "textLineList": [
                        {"textLine": text} for text in value.split("\n")
                    ]
                }
                # add_lang_to_sap_text_field( order, order_text, mapping_order_text.get(field), order_line_in['refDocIt'])
                param_es_21["orderText"].append(order_text)
    return call_es21_get_response(manager, param_es_21, order=order)


def change_order_add_new_item_i_plan_confirm(response_i_plan_request, order_header, list_order_line_new, response_es21,
                                             manager, order_in_database):
    param_i_plan_confirm = default_param_i_plan_confirm(order_header["so_no"])
    for order_line_new in list_order_line_new:
        item_no = order_line_new["item_no"]
        confirm_line = {
            "lineNumber": order_line_new["item_no"],
            "originalLineNumber": response_i_plan_request[item_no]["lineNumber"],
            "onHandQuantityConfirmed": "0" if not response_i_plan_request[item_no]["onHandStock"]
            else str(response_es21.get(item_no, {}).get("confirmQuantity", 0)),
            "unit": response_i_plan_request[item_no]["unit"],
            "status": "COMMIT",
            "DDQOrderInformationType": []
        }
        param_i_plan_confirm["DDQConfirm"]["DDQConfirmHeader"][0]["DDQConfirmLine"].append(confirm_line)
    return call_i_plan_confirm_get_response(manager, param_i_plan_confirm, order=order_in_database)


def call_i_plan_rollback(manager, order_header, list_order_line_new, item_error=[]):
    param_i_plan_rollback = default_param_i_plan_rollback(order_header["so_no"])
    for order_line in list_order_line_new:
        if order_line["item_no"] not in item_error:
            confirm_line = {
                "lineNumber": order_line["item_no"],
                "originalLineNumber": order_line["item_no"],
                "status": "ROLLBACK",
                "DDQOrderInformationType": []
            }
            param_i_plan_rollback["DDQConfirm"]["DDQConfirmHeader"][0]["DDQConfirmLine"].append(confirm_line)
    return call_i_plan_confirm_get_response(manager, param_i_plan_rollback)


def get_iplan_error_messages(iplan_response, cancel_delete_item=False):
    i_plan_error_messages = []
    response_lines = []
    i_plan_error_item_no = []
    is_change_flow = False
    if iplan_response.get("DDQResponse"):
        response_lines = iplan_response.get("DDQResponse").get("DDQResponseHeader")[0].get("DDQResponseLine")
    elif iplan_response.get("DDQAcknowledge"):
        response_lines = iplan_response.get("DDQAcknowledge").get("DDQAcknowledgeHeader")[0].get("DDQAcknowledgeLine")
    elif iplan_response.get("OrderUpdateResponse").get("OrderUpdateResponseLine"):
        response_lines = iplan_response.get("OrderUpdateResponse").get("OrderUpdateResponseLine")
        is_change_flow = True
    else:
        return []

    for line in response_lines:
        if line.get("returnStatus").lower() == IPlanAcknowledge.FAILURE.value.lower():
            if is_change_flow:
                return_code = line.get("returnCode", "1")
                i_plan_error_item_no.append(line.get("lineCode", "").lstrip("0"))
                i_plan_error_messages.append({
                    "item_no": line.get("lineCode", "").lstrip("0"),
                    "first_code": return_code,
                    "second_code": "",
                    "message": line.get("returnCodeDescription"),
                })
            else:
                return_code = line.get("returnCode")
                i_plan_error_item_no.append(line.get("lineNumber", "").lstrip("0"))
                i_plan_error_messages.append({
                    "item_no": line.get("lineNumber", "").lstrip("0"),
                    "first_code": return_code and return_code[18:24] or "0",
                    "second_code": return_code and return_code[24:32] or "0",
                    "message": line.get("returnCodeDescription"),
                })
    if cancel_delete_item:
        return i_plan_error_item_no, i_plan_error_messages
    return i_plan_error_messages
