import logging
from copy import deepcopy
from functools import reduce
import uuid
from datetime import datetime, date
from common.helpers import dictgetattrd, net_price_calculation

from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q

from common.product_group import ProductGroup
from saleor.plugins.manager import get_plugins_manager
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data import models as master_models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import InquiryMethodType
from scg_checkout.graphql.enums import DeliveryStatus, IPlanOrderItemStatus, MaterialType, SapOrderConfirmationStatus
from scg_checkout.graphql.helper import (
    update_order_status,
    make_order_text_mapping,
    get_id_of_object_model_from_code,
    get_item_no_max_order_line, is_other_product_group, mapping_order_partners,
)
from scg_checkout.graphql.resolves.contracts import sync_contract_material, sync_contract_material_variant_v2
from scgp_export.graphql.enums import (
    ScgpExportOrderStatus,
    ItemCat,
    SapEnpoint,
    TextID)
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text
from scgp_require_attention_items.graphql.helper import (
    get_distribution_channel_id_from_code,
    get_sales_org_id_from_code,
    get_division_id_from_code,
    get_incoterms_id_from_code,
    get_customer_group_id_from_code,
    get_customer_group1_id_from_code,
    get_sales_group_id_from_code,
    get_sales_office_group_id_from_code,
    get_currency_id_from_code,
    get_contract_id_from_contract_no,
    get_sold_to_id_from_contract_no,
    update_attention_type_r1,
    update_attention_type_r3,
    update_attention_type_r4,
)

DATE_FORMAT_ISO = "%Y-%m-%d"
DATE_FORMAT = "%d%m%Y"


def check_input_is_contract_id_or_contract_code(export_pi_input):
    is_contract_id = sap_migration_models.Contract.objects.filter(id=export_pi_input).first()
    if is_contract_id:
        return export_pi_input
    is_contract_code = sap_migration_models.Contract.objects.filter(code=export_pi_input).first()
    if is_contract_code:
        return is_contract_code.id
    raise ValueError("We don't have this contract in database. Please recheck again!")


def get_list_item_no(es26_response):
    _order_lines_from_es26 = es26_response["data"][0]["orderItems"]
    list_item_no = []
    for order_line in _order_lines_from_es26:
        list_item_no.append(order_line["itemNo"].lstrip("0"))
    return list_item_no


def get_fixed_item_no(item_nos):
    if not item_nos:
        return ""
    max_no = int(max(item_nos))
    result = []
    for i in range(10, max_no + 1, 10):
        result.append(str(i))
    return ",".join(result)


def handle_order_lines_from_es26(order, es26_response, is_created=None):
    manager = get_plugins_manager()
    sap_fn = manager.call_api_sap_client
    date_format_es26 = '%d/%m/%Y'
    date_format_to_database = '%Y-%m-%d'
    _order_lines_from_es26 = es26_response["data"][0]["orderItems"]
    _order_schedule_from_es26 = es26_response["data"][0].get("orderSchedulesIn", None)
    order_partner = es26_response["order_partner_mapping"].get("order_lines", {})

    _order_schedule_from_es26_dict = {}

    if _order_schedule_from_es26:
        if not isinstance(_order_schedule_from_es26, list):
            _order_schedule_from_es26 = [_order_schedule_from_es26]
        for schedule in _order_schedule_from_es26:
            _order_schedule_from_es26_dict[schedule["itemNo"].lstrip("0")] = schedule

    list_material_code = []
    list_contract_material_code = []
    for order_line in _order_lines_from_es26:
        if not order.product_group:
            order.product_group = order_line.get("materialGroup1", None)
            logging.info(f"[Sync_ES26] Order[{order.type}] {order.so_no},"
                         f" product_group is BLANK. Hence updating from ES26 response to {order.product_group}")
        material_code = order_line.get("material")
        contract_code = order_line.get("contractNo")
        if material_code:
            list_material_code.append(material_code)
        if contract_code:
            list_contract_material_code.append(contract_code)

    need_iplan_integration = ProductGroup.is_iplan_integration_required(order)
    if not list_contract_material_code:
        raise Exception("This order is not ref contract")
    if is_created:
        sync_contract_material(contract_no=list_contract_material_code[0], es26_response=es26_response)
    mapping_material_variant_code_with_material_variant_id = sap_migration_models.MaterialVariantMaster.objects.filter(
        code__in=list_material_code).all()
    mapping_contract_material_code_with_contract_material = sap_migration_models.ContractMaterial.objects.filter(
        contract_no__in=list_contract_material_code).all()
    list_order_line_create = []
    list_order_line_update = []
    list_item_no = get_list_item_no(es26_response)
    item_no_of_order_line_exits_in_database = sap_migration_models.OrderLines.objects.filter(
        order=order, item_no__in=list_item_no).distinct(
        "item_no").order_by("item_no").in_bulk(field_name="item_no")
    request_date = es26_response.get("data")[0].get("orderHeaderIn").get("reqDate")
    weights = get_weigh_domestic_by_material_variant_codes(list_material_code)
    product_group = order.product_group
    is_weight_by_sale_unit = is_other_product_group(product_group)

    if is_created:
        sync_contract_material_variant_v2(
            sap_fn,
            sold_to_code=order.contract.sold_to.sold_to_code if order.contract and order.contract.sold_to else order.sold_to_code,
            material_ids=mapping_contract_material_code_with_contract_material.values_list("material_id", flat=True)
        )
    for order_line in _order_lines_from_es26:
        item_no = order_line.get("itemNo", "").lstrip("0")
        material_variant_code = order_line.get("material")
        order_line_db = item_no_of_order_line_exits_in_database.get(item_no)
        contract_material = handle_contract_material(order_line, mapping_contract_material_code_with_contract_material,
                                                     material_variant_code)
        weight = weights.get(material_variant_code).get(
            order_line.get("salesUnit") if is_weight_by_sale_unit else "ROL", 1) if weights.get(
            material_variant_code) else 1

        line_data = {}
        if contract_material:
            material_id = contract_material.material_id
            material_variant = mapping_material_variant_code_with_material_variant_id.filter(
                material_id=material_id, code=material_variant_code).first()
            material_variant_id = material_variant.id if material_variant else None
            price_per_unit = contract_material.price_per_unit if contract_material.price_per_unit else 0
            line_data = {
                "contract_material_id": contract_material.id,
                "contract_material": contract_material,
                "price_per_unit": price_per_unit,
                "price_currency": contract_material.currency if contract_material.currency else "",
                "net_price": net_price_calculation(
                    contract_material.mat_group_1,
                    float(order_line.get("itemQty", 0)),
                    float(price_per_unit),
                    float(weight)
                ),
                "weight_unit": contract_material.weight_unit,
                "material_id": material_id,
            }
            if material_variant_id:
                line_data["material_variant_id"] = material_variant_id
        sap_confirm_qty = _order_schedule_from_es26_dict.get(item_no, {}).get("confirmQty", None)
        sap_confirm_status = handle_sap_confirm_status_from_es26(order_line)
        inquiry_method_db = getattr(order_line_db, "inquiry_method", None)
        inquiry_method_es26 = InquiryMethodType.EXPORT.value if getattr(order.distribution_channel,
                                                                        "code") == "30" else InquiryMethodType.DOMESTIC.value
        assigned_quantity = round(order_line.get("comfirmQty", 0), 3) if not need_iplan_integration else getattr(
            order_line_db, "assigned_quantity", None)
        line_data = {
            **line_data,
            "order_id": order.id,
            "quantity": order_line.get("itemQty", 0),
            "sales_unit": order_line.get("salesUnit", None),
            "plant": order_line.get("plant", None),
            "payment_term_item": order_line.get("paymentTerm", None),
            "po_no": order_line.get("poNumber", None),
            "item_category": order_line.get("itemCategory", None),
            "request_date": datetime.strptime(
                order_line.get("requestedDate") or request_date
                , date_format_es26).strftime(
                date_format_to_database)
            ,
            "shipping_point": order_line.get("shippingPoint", None),
            "reject_reason": order_line.get("reasonReject", "No"),
            "ref_doc": order_line.get("contractNo", None),
            "ref_doc_it": order_line.get("contractItemNo", None),
            "type": "export" if getattr(order.distribution_channel, "code") == "30" else "domestic",
            "item_status_en_rollback": getattr(order_line_db, "item_status_en_rollback", None),
            "item_status_en": getattr(order_line_db, "item_status_en", None),
            "item_status_th": getattr(order_line_db, "item_status_th", None),
            "po_date": datetime.strptime(order_line.get("poDates"), '%d/%m/%Y') if order_line.get("poDates") else None,
            "route": order_line.get("routeId", ""),
            "item_cat_eo": order_line.get("itemCategory", None),
            "delivery_tol_unlimited": True if order_line.get("untimatedTol") else False,
            "delivery_tol_over": order_line.get("deliveryTolOver", None) if not order_line.get("untimatedTol",
                                                                                               None) else 0,
            "delivery_tol_under": order_line.get("deliveryTolOverUnder", None) if not order_line.get("untimatedTol",
                                                                                                     None) else 0,
            # Dont sync data confirm quantity from ES26 SEO-4931
            # "confirm_quantity": order_line.get("comfirmQty", None),
            "shipping_mark": es26_response["order_text_mapping"].get(item_no.zfill(6), {}).get(
                "shipping_mark"),
            "internal_comments_to_warehouse": es26_response["order_text_mapping"].get(item_no.zfill(6), {}).get(
                "internal_comments_to_warehouse"),
            "external_comments_to_customer": es26_response["order_text_mapping"].get(item_no.zfill(6), {}).get(
                "external_comments_to_customer"),
            "delivery_quantity": order_line.get("deliveryQty", None),
            "product_hierarchy": order_line.get("prdHierachy", None),
            "weight": weight,
            "weight_unit": order_line.get("weightUnitTon", "TON"),
            "gross_weight_ton": order_line.get("grossWeightTon", None),
            "net_weight_ton": order_line.get("netWeightTon", None),
            "weight_unit_ton": order_line.get("weightUnitTon", None),
            "prc_group_1": order_line.get("materialGroup1", None),
            "route_name": order_line.get("routeName", ""),
            "material_group2": order_line.get("materialGroup1", ""),
            "sap_confirm_qty": float(sap_confirm_qty) if sap_confirm_qty else None,
            "material_code": order_line.get("material"),
            "condition_group1": order_line.get("conditionGroup1", None),
            "ship_to": order_partner.get(item_no.zfill(6), {}).get("ship_to", None),
            "sap_confirm_status": sap_confirm_status,
            "po_sub_contract": order_line.get("poSubcontract", ""),
            "po_status": order_line.get("poStatus", ""),
            "original_request_date": datetime.strptime(
                order_line.get("shiptToPODate"), date_format_es26) if order_line.get("shiptToPODate") else None,
            "inquiry_method": inquiry_method_db if inquiry_method_db else inquiry_method_es26,
            "pr_no": order_line.get("purchaseNo", ""),
            "pr_item": order_line.get("prItem", ""),
            "assigned_quantity": assigned_quantity
        }
        if not need_iplan_integration:
            line_data["confirmed_date"] = line_data.get("request_date")

        # created_by = order.created_by
        # if not created_by:
        #     update_status_item_from_es26(line_data, order_line)
        # else:
        #     get_line_status_from_es26(line_data, order_line)
        # XXX: support migrated order
        get_line_status_from_es26(line_data, order_line)
        if item_no not in item_no_of_order_line_exits_in_database:
            logging.info(
                f"[Sync_Es26] [New items] Order {order.so_no}: Item {item_no} is not exist in the database."
                f" creating it with the provided data from SAP: {line_data}")
            # Handle order_line_iplan
            iplan_order_line = sap_migration_models.OrderLineIPlan()
            iplan_order_line.save()
            # Adding default inquiry method when sync item from SAP if order is created from SAP
            line_data = {
                **line_data,
                "inquiry_method": "Export" if getattr(order.distribution_channel, "code") == "30" else "Domestic",
            }
            _order_line = sap_migration_models.OrderLines(
                item_no=item_no,
                iplan=iplan_order_line,
                **line_data,
            )
            list_order_line_create.append(_order_line)
        else:
            exist_line = item_no_of_order_line_exits_in_database.get(item_no)
            logging.info(
                f"[Sync_Es26 Existing items] Order : {order.so_no}, "
                f"item : {item_no} exists in the DB and its DB quantity :{exist_line.quantity} "
                f"updated to:{line_data.get('quantity', '')}, DB plant: {exist_line.plant} updated to:"
                f"{line_data.get('plant', '')}, DB request_date: {exist_line.request_date} updated to: "
                f"{line_data.get('request_date', '')}, DB assigned_quantity: {exist_line.assigned_quantity}"
                f" updated to: {line_data.get('assigned_quantity', '')} db item_category: {exist_line.item_category}"
                f" updated to: {line_data.get('item_category', '')}")
            exist_line.__dict__.update(
                **line_data,
            )
            list_order_line_update.append(exist_line)
    # delete draftlines before inserting the new lines
    list_line_ids = list(map(lambda x: x.id, list_order_line_update))
    sap_migration_models.OrderLines.all_objects.filter(order=order).exclude(
        Q(id__in=list_line_ids, draft=False) | Q(item_no__isnull=True)
    ).delete()

    if list_order_line_create:
        sap_migration_models.OrderLines.objects.bulk_create(list_order_line_create)
    if list_order_line_update:
        sap_migration_models.OrderLines.objects.bulk_update(list_order_line_update, line_data.keys())

    max_item_no = get_item_no_max_order_line(order.id)
    item_no_latest = order.item_no_latest or 0
    if int(item_no_latest) < int(max_item_no):
        order.item_no_latest = str(max_item_no) or '0'
    status_en, status_thai = update_order_status(order.id)
    logging.info(f"[Sync_Es26] Order: {order.so_no}, DB order status: {order.status} updated to: {status_en}")
    order.status = status_en
    order.status_thai = status_thai
    order.save()
    return list_order_line_update


def get_sold_to_code_from_es26(es26_response):
    data = es26_response.get("data", [])
    if not data:
        return ""
    partners = data[0].get("orderPartners")
    for partner in partners:
        if partner.get("partnerRole") == "AG":
            return partner.get("addrLink")
    return ""


def create_or_update_order(es26_response):
    date_format_es26 = '%d/%m/%Y'
    date_format_to_database = '%Y-%m-%d'
    _order_from_es26 = es26_response["data"][0]["orderHeaderIn"]
    _order_partners_from_es26 = es26_response["data"][0]["orderPartners"]
    _order_lines_from_es26 = es26_response["data"][0].get("orderItems", None)
    order_partners = mapping_order_partners(_order_partners_from_es26)
    order_text_mapping = make_order_text_mapping(es26_response["data"][0]["orderText"])
    es26_response["order_text_mapping"] = order_text_mapping
    es26_response["order_partner_mapping"] = order_partners
    so_no = _order_from_es26["saleDocument"]
    try:
        distribution_channel = get_distribution_channel_id_from_code(_order_from_es26["distributionChannel"])
        order_partner_list = es26_response["data"][0].get("orderPartners", [])
        order_partner = next((x for x in order_partner_list if x.get("partnerRole") == "VE"), {})
        payer_code = order_partner.get('partnerNo')
        payer_name = resolve_display_text(payer_code) if payer_code else ""
        sales_employee = f"{payer_code} - {payer_name}"
        header_text = order_text_mapping.get("000000", {})
        etd = get_sap_iso_date(header_text, "etd", DATE_FORMAT_ISO, {"so_no": so_no})
        eta = get_sap_iso_date(header_text, "eta", DATE_FORMAT_ISO, {"so_no": so_no})
        dlc_expiry_date = get_sap_iso_date(header_text, "dlc_expiry_date", DATE_FORMAT_ISO, {"so_no": so_no})
        contract_no = _order_from_es26.get("contractNo") or _order_lines_from_es26[0] and _order_lines_from_es26[0].get(
            "contractNo") or None
        dlc_latest_delivery_date = get_sap_iso_date(header_text, "dlc_latest_delivery_date", DATE_FORMAT_ISO,
                                                    {"so_no": so_no})
        order, is_created = sap_migration_models.Order.objects.update_or_create(
            so_no=so_no,
            defaults={
                "so_no": _order_from_es26["saleDocument"],
                "distribution_channel": distribution_channel,
                "sales_organization": get_sales_org_id_from_code(_order_from_es26["salesOrg"]),
                "division": get_division_id_from_code(_order_from_es26["division"]),
                "request_date": datetime.strptime(_order_from_es26["reqDate"], date_format_es26).strftime(
                    date_format_to_database),
                "ship_to": order_partners["order"]["ship_to"],
                "bill_to": order_partners["order"]["bill_to"],
                "incoterms_1": get_incoterms_id_from_code(_order_from_es26["incoterms1"]),
                "incoterms_2": _order_from_es26["incoterms2"],
                "payment_term": _order_from_es26["paymentTerms"],
                "po_no": _order_from_es26["poNo"],
                "po_number": _order_from_es26["poNo"],
                "price_group": _order_from_es26["priceGroup"],
                "price_date": datetime.strptime(_order_from_es26["priceDate"], date_format_es26).strftime(
                    date_format_to_database),
                "customer_group": get_customer_group_id_from_code(_order_from_es26["customerGroup"]),
                "customer_group_1": get_customer_group1_id_from_code(_order_from_es26.get("customerGroup1")),
                "customer_group_2_id": get_id_of_object_model_from_code(
                    sap_migration_models.CustomerGroup2Master.objects, _order_from_es26.get("customerGroup2")),
                "customer_group_3_id": get_id_of_object_model_from_code(
                    sap_migration_models.CustomerGroup3Master.objects, _order_from_es26.get("customerGroup3")),
                "customer_group_4_id": get_id_of_object_model_from_code(
                    sap_migration_models.CustomerGroup4Master.objects, _order_from_es26.get("customerGroup4")),
                "sales_district": _order_from_es26["salesDistrict"],
                "internal_comments_to_warehouse": order_text_mapping.get("000000", {}).get(
                    "internal_comments_to_warehouse"),
                "internal_comment_to_warehouse": order_text_mapping.get("000000", {}).get(
                    "internal_comments_to_warehouse"),
                "internal_comments_to_logistic": order_text_mapping.get("000000", {}).get(
                    "internal_comments_to_logistic"),
                "external_comments_to_customer": order_text_mapping.get("000000", {}).get(
                    "external_comments_to_customer"),
                "product_information": order_text_mapping.get("000000", {}).get("product_information"),
                "production_information": order_text_mapping.get("000000", {}).get("product_information"),
                "shipping_condition": _order_from_es26["shippingCondition"],
                "sales_group": get_sales_group_id_from_code(_order_from_es26["salesGroup"]),
                "sales_office": get_sales_office_group_id_from_code(_order_from_es26["salesOff"]),
                "currency": get_currency_id_from_code(_order_from_es26["currency"]),
                "contract": get_contract_id_from_contract_no(contract_no),
                "sold_to": get_sold_to_id_from_contract_no(contract_no),
                "status": ScgpExportOrderStatus.RECEIVED_ORDER.value,
                "type": "export" if getattr(distribution_channel, "code") == "30" else "domestic",
                "sold_to_code": get_sold_to_code_from_es26(es26_response),
                "po_date": datetime.strptime(_order_from_es26.get("poDates", None), date_format_es26).strftime(
                    date_format_to_database) if _order_from_es26.get("poDates", None) else None,
                "order_type": _order_from_es26["docType"],
                "total_price": _order_from_es26.get("orderAmtBeforeVat", None),
                "tax_amount": _order_from_es26.get("orderAmtVat", None),
                "total_price_inc_tax": _order_from_es26.get("orderAmtAfterVat", None),
                "unloading_point": _order_from_es26.get("unloadingPoint", None),
                "port_of_loading": order_text_mapping.get("000000", {}).get(
                    "port_of_loading"),
                "shipping_mark": order_text_mapping.get("000000", {}).get(
                    "shipping_mark"),
                "uom": order_text_mapping.get("000000", {}).get(
                    "uom"),
                "port_of_discharge": order_text_mapping.get("000000", {}).get(
                    "port_of_discharge"),
                "no_of_containers": order_text_mapping.get("000000", {}).get(
                    "no_of_containers"),
                "gw_uom": order_text_mapping.get("000000", {}).get(
                    "gw_uom"),
                "payment_instruction": order_text_mapping.get("000000", {}).get(
                    "payment_instruction"),
                "remark": order_text_mapping.get("000000", {}).get(
                    "remark"),
                "usage": _order_from_es26.get("usage"),
                "sales_employee": sales_employee,
                "payer": next(
                    (f"{x.get('partnerNo')} - {x.get('address', [])[0].get('name')}" for x in _order_partners_from_es26
                     if x.get("partnerRole") == "RG")),
                "description": _order_from_es26.get("description"),
                "etd": etd,
                "eta": eta,
                "dlc_expiry_date": dlc_expiry_date,
                "dlc_latest_delivery_date": dlc_latest_delivery_date,
                "dlc_no": order_text_mapping.get("000000", {}).get("dlc_no"),
            }
        )

        if is_created:
            logging.info(f"[Sync_ES26] order so_no: {so_no} is created newly: {is_created}")
            order.created_at = datetime.strptime(
                _order_from_es26["createDate"],
                date_format_es26).strftime(date_format_to_database)
            if order.contract is None:
                sync_contract_material(contract_no=contract_no, es26_response=es26_response, is_create=True)
                order.contract = get_contract_id_from_contract_no(contract_no)
                order.sold_to = get_sold_to_id_from_contract_no(contract_no)
            order.save()
        if not _order_lines_from_es26:
            order.product_group = None
            order.save()
        if _order_lines_from_es26:
            handle_order_lines_from_es26(order, es26_response, is_created)

        update_attention_items = sap_migration_models.OrderLines.objects.filter(order__so_no=order.so_no).exclude(
            item_status_en=IPlanOrderItemStatus.CANCEL.value)
        if update_attention_items:
            update_attention_type_r1(update_attention_items)
            update_attention_type_r3(update_attention_items)
            update_attention_type_r4(update_attention_items)
            sap_migration_models.OrderLines.objects.bulk_update(update_attention_items, fields=["attention_type"])
        return order
    except MultipleObjectsReturned:
        order = sap_migration_models.Order.objects.filter(so_no=so_no).first()
        return order


def sync_export_order_from_es26(es26_response):
    _order_from_es26 = es26_response["data"][0]["orderHeaderIn"]
    if not _order_from_es26:
        return
    return create_or_update_order(es26_response)


def handle_item_no_flag(order, params):
    res = {}
    lines = dictgetattrd(params, "input.lines", []) or dictgetattrd(params, "lines", [])
    exits_item_no = set(order.orderlines_set.all().values_list("item_no", flat=True))
    request_item_no = set(map(lambda x: x.get("item_no", 0), lines))
    if not request_item_no:
        return res
    union_item_no = exits_item_no.union(request_item_no)
    for item_no in union_item_no:
        if not item_no:
            continue
        if item_no in exits_item_no and item_no in request_item_no:
            res[item_no] = "U"
        elif item_no in request_item_no and item_no not in exits_item_no:
            res[item_no] = "I"
        else:
            res[item_no] = "D"
    return res


def mapping_new_item_no(lines, params):
    item_no_from_request = {line.get("id"): line.get("item_no") for line in params.get("lines", [])}
    res = []
    for line in lines:
        item_no = item_no_from_request.get(str(line.id), None)
        if not item_no:
            continue
        line.item_no = str(item_no_from_request.get(str(line.id)))
        res.append(line)
    return res


def get_order_header_es21(order: sap_migration_models.Order, updated_order: sap_migration_models.Order):
    order_header_in = {}
    order_header_in_x = {}
    order_header_with_field_mapped_model = {
        "request_date": "reqDate",
        "place_of_delivery": "Incoterms2",
        "po_no": "poNo",
        "description": "description",
        "unloading_point": "unloadingPoint",
        "usage": "usage"
    }
    model_fields = deepcopy(list(order_header_with_field_mapped_model.keys()))
    for k in model_fields:
        if getattr(order, k, None) == getattr(updated_order, k, None):
            del order_header_with_field_mapped_model[k]

    for update_field, param_field in order_header_with_field_mapped_model.items():
        field_data = getattr(updated_order, update_field, None)
        if field_data:
            if isinstance(field_data, date):
                field_data = field_data.strftime("%d/%m/%Y")
            order_header_in.update({param_field: field_data})
            order_header_in_x.update({param_field: True})

    return order_header_in, order_header_in_x


def getattrd(obj, name, default=None):
    try:
        return reduce(getattr, name.split("."), obj)
    except AttributeError:
        return default


def _is_updated(field: str, new_order_line, old_order_line) -> bool:
    return getattrd(new_order_line, field, None) != getattrd(old_order_line, field, None)


def _update_base(condition: bool, base: dict, field: str, data):
    if condition:
        base.update({field: data})


def create_es21_order_items(new_order_line: sap_migration_models.OrderLines,
                            old_order_line: sap_migration_models.OrderLines, flag="U", delete_flag=True):
    # check if field in order item is updated or item is created
    def _field_updated(field: str):
        return _is_updated(field, new_order_line, old_order_line) or flag == "I"

    material_code = new_order_line.material_variant.code if new_order_line.material_variant else ""
    item_no = new_order_line.item_no.zfill(6)
    order_item = {
        "itemNo": item_no,
        "material": material_code
    }

    if flag == "D" and delete_flag:
        order_item.update({"refDoc": new_order_line.ref_doc if new_order_line.ref_doc else ""})
        order_item.update(
            {"refDocIt": new_order_line.contract_material and new_order_line.contract_material.item_no or ""})
        order_item_inx = {
            "itemNo": item_no,
            "updateflag": "D"
        }
        return order_item, order_item_inx, {}, {}

    target_quantity = new_order_line.quantity or 0
    shipping_point = new_order_line.shipping_point.split("-")[0].strip() if new_order_line.shipping_point else ""
    route = new_order_line.route.split(" - ")[0] if new_order_line.route else ""
    po_no = new_order_line.po_no or ""
    reject_reason = "93" if new_order_line.reject_reason == "Yes" else ""
    _update_base(_field_updated("material_variant.code"), order_item, "material",
                 material_code)
    _update_base(_field_updated("quantity"), order_item, "targetQty",
                 target_quantity)
    _update_base(_field_updated("plant"), order_item, "plant", new_order_line.plant or "")
    _update_base(_field_updated("shipping_point"), order_item, "shippingPoint",
                 shipping_point)
    _update_base(_field_updated("route"), order_item, "route", route)
    _update_base(_field_updated("po_no"), order_item, "poNo", po_no)
    _update_base(_field_updated("delivery_tol_over"), order_item, "overdlvtol",
                 new_order_line.delivery_tol_over)
    _update_base(_field_updated("delivery_tol_unlimited"), order_item, "unlimitTol",
                 "X" if new_order_line.delivery_tol_unlimited else "")
    _update_base(_field_updated("delivery_tol_under"), order_item, "unddlvTol",
                 new_order_line.delivery_tol_under)
    _update_base(_field_updated("reject_reason"), order_item, "reasonReject",
                 reject_reason)
    _update_base(_field_updated("item_cat_eo"), order_item, "itemCategory",
                 new_order_line.item_cat_eo)

    order_item.update({"refDoc": new_order_line.ref_doc if new_order_line.ref_doc else ""})
    order_item.update({"refDocIt": new_order_line.contract_material and new_order_line.contract_material.item_no or ""})
    order_item.update({"saleUnit": new_order_line.sales_unit})

    if order_item.get("delivery_tol_unlimited", None) == "X":
        order_item.update({"delivery_tol_over": 0})
        order_item.update({"delivery_tol_under": 0})

    if not new_order_line.delivery_tol_over and not order_item.get("overdlvtol", None):
        order_item.pop("overdlvtol", None)
    if not new_order_line.delivery_tol_under and not order_item.get("unddlvTol", None):
        order_item.pop("unddlvTol", None)

    order_items_inx = {
        "itemNo": new_order_line.item_no.zfill(6),
        "updateflag": flag,
        "targetQty": True,
        "salesUnit": True,
        "plant": True,
        "shippingPoint": True,
        "route": True,
        "poNo": True,
        "overdlvtol": True,
        "unlimitTol": True,
        "unddlvTol": True,
        "reasonReject": True,
        "saleUnit": True,
        "itemCategory": True,
    }
    keys = deepcopy(list(order_items_inx.keys()))
    for k in keys:
        if k in ["itemNo", "updateflag"]:
            continue
        if order_item.get(k, None) is None:
            order_items_inx.pop(k)

    order_schedule = {
        "itemNo": item_no,
        "updateflag": flag
    }
    item_request_date = new_order_line.request_date.strftime("%d/%m/%Y") if new_order_line.request_date else ""
    _update_base(_field_updated("request_date"), order_schedule, "reqDate", item_request_date)
    quantity = new_order_line.quantity
    _update_base(_field_updated("quantity"), order_schedule, "reqQty", quantity)

    new_confirm_quanity = 0
    old_confirm_quantity = 0
    if new_order_line.item_cat_eo == ItemCat.ZKC0.value:
        new_confirm_quanity = new_order_line.quantity or 0
        old_confirm_quantity = old_order_line.quantity or 0

    if new_order_line.iplan:
        new_confirm_quanity = new_order_line.iplan.iplant_confirm_quantity or 0

    if getattrd(old_order_line, "iplan", None):
        old_confirm_quantity = old_order_line.iplan.iplant_confirm_quantity or 0

    _update_base(new_confirm_quanity != old_confirm_quantity or flag == "I", order_schedule, "confirmQty",
                 new_confirm_quanity)

    order_schedule_inx_params = {
        "requestDate": "reqDate",
        "requestQuantity": "reqQty",
        "confirmQuantity": "confirmQty"
    }

    order_schedule_inx = {
        "itemNo": item_no,
        "updateflag": flag,
        "requestDate": True,
        "requestQuantity": True,
        "confirmQuantity": True,
    }

    schedule_keys = deepcopy(list(order_schedule_inx.keys()))
    for k in schedule_keys:
        if k in ["itemNo", "updateflag", "scheduleLine"]:
            continue
        if order_schedule.get(order_schedule_inx_params[k], None) is None:
            del order_schedule_inx[k]

    return order_item, order_items_inx, order_schedule, order_schedule_inx


def change_order_request_es21(order, manager, sap_update_flag=None, updated_data=None, pre_update_lines={},
                              export_delete_flag=True, updated_items=[]):
    order_lines = updated_items or sap_migration_models.OrderLines.objects.filter(order=order)

    order_partners = []
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_text = []
    item_no_order_header = "000000"
    sold_to_code = order.sold_to.sold_to_code if order.sold_to else order.sold_to_code

    if order.payer:
        payer = order.payer.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(sold_to_code=sold_to_code,
                                                                          partner_code=payer).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "RG",
                    "partnerNumb": payer,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )

    if order.ship_to:
        ship_to = order.ship_to.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(sold_to_code=sold_to_code,
                                                                          partner_code=ship_to).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "WE",
                    "partnerNumb": ship_to,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )

    if order.bill_to:
        bill_to = order.bill_to.split("-")[0].strip()
        partner = master_models.SoldToChannelPartnerMaster.objects.filter(sold_to_code=sold_to_code,
                                                                          partner_code=bill_to).last()
        if partner:
            order_partners.append(
                {
                    "partnerRole": "RE",
                    "partnerNumb": bill_to,
                    "itemNo": item_no_order_header,
                    # "addressLink": partner.address_link
                }
            )
    for line in order_lines:
        remark = line.remark or ""

        # reject_reason = "93" if line.reject_reason == "Yes" else ""
        old_order_line = pre_update_lines.get(line.id)
        item_no = line.item_no.zfill(6)
        (
            order_item,
            order_item_in,
            order_schedule_in,
            order_schedule_inx
        ) = create_es21_order_items(line, old_order_line, sap_update_flag.get(str(line.item_no), "U"),
                                    delete_flag=export_delete_flag)

        order_items_in.append(order_item)
        order_items_inx.append(order_item_in)
        if order_schedule_in:
            order_schedules_in.append(order_schedule_in)
        if order_schedule_inx:
            order_schedules_inx.append(order_schedule_inx)

        handle_request_text_to_es21(order_text, remark, item_no, TextID.ITEM_REMARK.value)

    etd = datetime.strptime(order.etd, DATE_FORMAT_ISO).strftime(DATE_FORMAT) if order.etd else ""
    eta = datetime.strptime(str(order.eta), DATE_FORMAT_ISO).strftime(DATE_FORMAT) if order.eta else ""
    payment_instruction = order.payment_instruction or ""
    port_of_discharge = order.port_of_discharge or ""
    port_of_loading = order.port_of_discharge or ""
    no_of_containers = order.no_of_containers or ""
    dlc_expiry_date = order.dlc_expiry_date.strftime(DATE_FORMAT) if order.dlc_expiry_date else ""
    dlc_latest_delivery_date = order.dlc_latest_delivery_date.strftime(
        DATE_FORMAT) if order.dlc_latest_delivery_date else ""
    dlc_no = order.dlc_no or ""
    uom = order.uom or ""
    gw_uom = order.gw_uom or ""
    product_information = order.production_information or ""
    remark = order.remark or ""
    internal_comments_to_warehouse = order.internal_comment_to_warehouse or ""

    handle_request_text_to_es21(order_text, product_information, item_no_order_header, TextID.HEADER_PI.value)
    handle_request_text_to_es21(order_text, internal_comments_to_warehouse, item_no_order_header,
                                TextID.HEADER_ICTW.value)
    handle_request_text_to_es21(order_text, remark, item_no_order_header, TextID.HEADER_REMARK.value)
    handle_request_text_to_es21(order_text, payment_instruction, item_no_order_header, TextID.HEADER_PAYIN.value)
    handle_request_text_to_es21(order_text, etd, item_no_order_header, TextID.HEADER_ETD.value)
    handle_request_text_to_es21(order_text, eta, item_no_order_header, TextID.HEADER_ETA.value)
    handle_request_text_to_es21(order_text, port_of_discharge, item_no_order_header,
                                TextID.HEADER_PORT_OF_DISCHARGE.value)
    handle_request_text_to_es21(order_text, port_of_loading, item_no_order_header, TextID.HEADER_PORT_OF_LOADING.value)
    handle_request_text_to_es21(order_text, no_of_containers, item_no_order_header,
                                TextID.HEADER_NO_OF_CONTAINERS.value)
    handle_request_text_to_es21(order_text, dlc_expiry_date, item_no_order_header, TextID.HEADER_DLC_EXPIRY_DATE.value)
    handle_request_text_to_es21(order_text, dlc_latest_delivery_date, item_no_order_header,
                                TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value)
    handle_request_text_to_es21(order_text, dlc_no, item_no_order_header, TextID.HEADER_DLC_NO.value)
    handle_request_text_to_es21(order_text, uom, item_no_order_header, TextID.HEADER_UOM.value)
    handle_request_text_to_es21(order_text, gw_uom, item_no_order_header, TextID.HEADER_GW_UOM.value)

    order_header_in, order_header_in_x = get_order_header_es21(order=updated_data, updated_order=order)
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": {
            **order_header_in,
            "refDoc": order.contract.code if order.contract else "",
        },
        "orderHeaderInX": {
            **order_header_in_x,
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
    }
    if order_text:
        params["orderText"] = order_text

    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params,
        encode=True
    )

    return response


def handle_request_text_to_es21(request_texts, text_lines, item_no, text_id):
    text_line = list(filter(lambda x: len(x) > 0, (text_lines or "").split("\n")))
    if not text_line:
        text_line = [" "]
    request_texts.append(
        {
            "itemNo": item_no,
            "textId": text_id,
            "language": "EN",
            "textLineList": [
                {"textLine": item}
                for item in text_line
            ],
        }
    )


def update_status_item_from_es26(line_data, es26_order_line):
    delivery_status = es26_order_line.get("deliveryStatus", "")
    reason_reject = es26_order_line.get("reasonReject", "")
    list_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value
    if str(reason_reject) != "93":
        if delivery_status == 'A' or delivery_status == "":
            line_data["item_status_en"] = IPlanOrderItemStatus.ITEM_CREATED.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.ITEM_CREATED.value)
        elif delivery_status == DeliveryStatus.PARTIAL_DELIVERY.value:
            line_data["item_status_en"] = IPlanOrderItemStatus.PARTIAL_DELIVERY.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.PARTIAL_DELIVERY.value)
        elif delivery_status == DeliveryStatus.COMPLETED_DELIVERY.value:
            line_data["item_status_en"] = IPlanOrderItemStatus.COMPLETE_DELIVERY.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.COMPLETE_DELIVERY.value)
    else:
        line_data["item_status_en"] = IPlanOrderItemStatus.CANCEL.value
        line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.CANCEL.value)


def get_line_status_from_es26(line_data, es26_order_line):
    """
    Get status from ES26
    @param line_data: data update to eOrdering DB
    @param es26_order_line: line data from ES26
    @return:
    """
    delivery_status = es26_order_line.get("deliveryStatus", "")
    reason_reject = es26_order_line.get("reasonReject", "")
    list_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value
    current_item_status_en = line_data["item_status_en"]

    if not line_data["item_status_en"] and not line_data["item_status_th"]:
        if delivery_status == 'A' or delivery_status == "":
            line_data["item_status_en"] = IPlanOrderItemStatus.ITEM_CREATED.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.ITEM_CREATED.value)
        elif delivery_status == DeliveryStatus.PARTIAL_DELIVERY.value:
            line_data["item_status_en"] = IPlanOrderItemStatus.PARTIAL_DELIVERY.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.PARTIAL_DELIVERY.value)
        elif delivery_status == DeliveryStatus.COMPLETED_DELIVERY.value:
            line_data["item_status_en"] = IPlanOrderItemStatus.COMPLETE_DELIVERY.value
            line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.COMPLETE_DELIVERY.value)
        current_item_status_en = line_data["item_status_en"]

    if delivery_status == DeliveryStatus.PARTIAL_DELIVERY.value:
        line_data["item_status_en"] = IPlanOrderItemStatus.PARTIAL_DELIVERY.value
        line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.PARTIAL_DELIVERY.value)
    elif delivery_status == DeliveryStatus.COMPLETED_DELIVERY.value:
        line_data["item_status_en"] = IPlanOrderItemStatus.COMPLETE_DELIVERY.value
        line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.COMPLETE_DELIVERY.value)
    elif (not delivery_status) or (delivery_status == DeliveryStatus.CANCEL.value):
        if current_item_status_en in [
            IPlanOrderItemStatus.PARTIAL_DELIVERY.value,
            IPlanOrderItemStatus.COMPLETE_DELIVERY.value
        ]:
            line_data["item_status_en"] = line_data["item_status_en_rollback"] or current_item_status_en
            line_data["item_status_th"] = list_status_th.get(line_data["item_status_en"])

    if str(reason_reject) == "93":
        line_data["item_status_en"] = IPlanOrderItemStatus.CANCEL.value
        line_data["item_status_th"] = list_status_th.get(IPlanOrderItemStatus.CANCEL.value)

    if current_item_status_en not in [
        IPlanOrderItemStatus.PARTIAL_DELIVERY.value,
        IPlanOrderItemStatus.COMPLETE_DELIVERY.value,
    ]:
        line_data["item_status_en_rollback"] = current_item_status_en


def is_special_plant(plant):
    return plant in MaterialType.MATERIAL_OS_PLANT.value


def is_container(item_cat_eo):
    return item_cat_eo == ItemCat.ZKC0.value


def check_line_is_special_or_container(line: dict):
    if is_special_plant(line.get("plant")):
        return True
    if line.get("item_cat_eo") == ItemCat.ZKC0.value:
        return True
    return False


def default_param_es_21_add_new_item(so_no, contract_no):
    return {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": contract_no
        },
        "orderHeaderInX": {},
        "orderPartners": [],
        "orderItemsIn": [],
        "orderItemsInx": [],
        "orderSchedulesIn": [],
        "orderSchedulesInx": [],
        "orderText": []
    }


def get_weigh_domestic_by_material_variant_codes(list_material: object):
    result = {}
    conversions = (
        master_models.Conversion2Master.objects.filter(
            material_code__in=list_material
        )
        .order_by("material_code", "-id")
        .values("material_code", "to_unit", "calculation")
        .all()
    )

    for conversion in conversions:
        if not conversion["calculation"]:
            calculation = 0
        else:
            calculation = float(conversion["calculation"]) / 1000

        if not result.get(conversion["material_code"]):
            result[conversion["material_code"]] = {}
        result[conversion["material_code"]][conversion["to_unit"]] = calculation

    return result


def handle_contract_material(order_line, mapping_contract_material_code_with_contract_material, material_variant_code):
    contract_material = mapping_contract_material_code_with_contract_material.filter(
        item_no=order_line.get("contractItemNo", "")).first()
    if not contract_material:
        contract_material = mapping_contract_material_code_with_contract_material.filter(
            item_no=order_line.get("contractItemNo", ""), material_code=material_variant_code).first()
    if not contract_material:
        contract_material = mapping_contract_material_code_with_contract_material.filter(
            material_code=material_variant_code).first()

    return contract_material


def handle_sap_confirm_status_from_es26(order_line):
    order_quantity = round(order_line.get("orderQty", 0))
    confirm_quantity = round(order_line.get("comfirmQty", 0))
    non_confirm_quantity = order_quantity - confirm_quantity
    reason_reject = str(order_line.get("reasonReject", ""))
    if reason_reject != "93" and confirm_quantity > 0:
        return SapOrderConfirmationStatus.READY_TO_SHIP.value
    if reason_reject != "93" and non_confirm_quantity > 0 >= confirm_quantity:
        return SapOrderConfirmationStatus.QUEUE_FOR_PRODUCTION.value
    if reason_reject == "93":
        return SapOrderConfirmationStatus.CANCEL.value

    return ""


def handle_case_iplan_return_split_order(iplan_request_response, list_new_items, lines):
    mapping_item_no_input = {
        order_line_input['item_no']: order_line_input
        for order_line_input in list_new_items
    }
    max_item_no = 0
    result = {
        "failure": [],
        "header_code": iplan_request_response["DDQResponse"]["DDQResponseHeader"][0]["headerCode"]
    }
    new_lines = []
    mapping_split_item = {}
    for response_line in iplan_request_response["DDQResponse"]["DDQResponseHeader"][0]["DDQResponseLine"]:
        max_item_no = max(int(response_line["lineNumber"].split('.')[0]), max_item_no)
    for response_line in iplan_request_response["DDQResponse"]["DDQResponseHeader"][0]["DDQResponseLine"]:
        line_num = response_line["lineNumber"]
        original_item_no = response_line["lineNumber"].split('.')[0]
        if line_num in mapping_item_no_input:
            result[original_item_no] = response_line
            if original_item_no not in mapping_split_item:
                mapping_split_item[original_item_no] = []
            mapping_split_item[original_item_no].append((original_item_no, response_line))
        else:
            max_item_no += 10
            result[str(max_item_no)] = response_line
            if original_item_no not in mapping_split_item:
                mapping_split_item[original_item_no] = []
            mapping_split_item[original_item_no].append((str(max_item_no), response_line))
    for line in lines:
        item_no = line.get("item_no")
        if item_no in mapping_split_item:
            for new_item_no, split_item in mapping_split_item[item_no]:
                new_line = deepcopy(line)
                new_line["item_no"] = new_item_no
                new_line["quantity"] = split_item["quantity"]
                new_line["iplan_item_no"] = split_item["lineNumber"]
                new_lines.append(new_line)
        else:
            line["iplan_item_no"] = line["item_no"]
            new_lines.append(line)
    return result, new_lines


def create_new_order_line_in_database(original_item_no, so_no, new_item_no):
    order_line = sap_migration_models.OrderLines.all_objects.filter(item_no=original_item_no,
                                                                    order__so_no=so_no.zfill(10)).first()
    new_order_line_iplan = deepcopy(order_line.iplan)
    new_order_line_iplan.id = None
    new_order_line_iplan.save()
    new_order_line = deepcopy(order_line)
    new_order_line.item_no = new_item_no
    new_order_line.id = None
    new_order_line.iplan = new_order_line_iplan
    new_order_line.save()


def split_lines(lines):
    list_new_items_iplan = []
    list_special_items = []
    for line in lines:
        if check_line_is_special_or_container(line):
            list_special_items.append(line)
        else:
            list_new_items_iplan.append(line)
    return list_new_items_iplan, list_special_items


def get_sap_iso_date(vals, field_name, fmt_date, opts=None):
    target_val = vals and vals.get(field_name) or None
    if not target_val:
        return None
    target_date = None
    # TODO: add more format date
    for fmt in [DATE_FORMAT]:
        try:
            target_date = datetime.strptime(target_val, fmt).strftime(fmt_date)
            break
        except Exception:
            logging.warning(f"Error when convert {field_name}: {target_val} from format {fmt} to {fmt_date} // {opts}")
    return target_date


def save_original_request_date(lines):
    for line in lines:
        line["original_request_date"] = line.get("request_date")
    return lines
