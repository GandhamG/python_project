import datetime as datetime_lib
import logging
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from functools import reduce
from typing import Union

import pytz
from django.core.exceptions import ValidationError
from django.db.models import Q, IntegerField, Max
from django.db.models.functions import Cast
from django.utils import timezone

import sap_migration.models
from common.atp_ctp.enums import AtpCtpStatus
from common.enum import EorderingItemStatusEN, EorderingItemStatusTH
from common.enum import MulesoftServiceType, MulesoftFeatureType
from common.helpers import mock_confirm_date, get_data_path
from common.mulesoft_api import MulesoftApiRequest
from common.product_group import ProductGroup, SalesUnitEnum
from saleor.plugins.manager import get_plugins_manager
from saleor.settings import SAP_ENV
from sap_master_data import models as sap_master_data_models
from sap_master_data.models import SalesOrganizationMaster, SoldToChannelMaster
from sap_migration import models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import OrderType, InquiryMethodType
from scg_checkout.error_codes import ContractCheckoutErrorCode
from scg_checkout.graphql.enums import (
    IPlanOrderItemStatus,
    IPlanOrderStatus,
    InquiryMethodParameter,
    Es21Params,
    OrderEdit,
    ItemDetailsEdit,
    AtpCtpStatus,
    SapOrderConfirmationStatus,
    SapOrderConfirmationStatusParam,
    ReasonForChangeRequestDateEnum,
    ReasonForChangeRequestDateDescriptionEnum, AlternatedMaterialLogChangeError, AlternatedMaterialProductGroupMatch,
    EmailProductGroupConfig, EmailSaleOrgConfig, PP_BU
)
from scg_checkout.graphql.implementations.change_order_add_product import get_dict_material_code_to_weight
from scg_checkout.models import AlternatedMaterial
from scgp_export.graphql.enums import SapEnpoint, IPlanEndPoint, ItemCat
from scgp_po_upload.graphql.enums import IPlanAcknowledge
from scgp_require_attention_items.graphql.enums import IPlanEndpoint
from scgp_require_attention_items.graphql.helper import add_class_mark_into_order_line
from scgp_require_attention_items.graphql.helper import (
    prepare_customer_list_for_es25,
    prepare_customer_po_no_for_es25,
    convert_date_to_fit_params_in_es25,
    prepare_material_for_es25,
    prepare_material_group_1_for_es25,
    prepare_sale_org_list_for_es25_order_confirmation,
    update_attention_type_r5, get_filter_source_of_app,
)
from scgp_user_management.models import (
    EmailConfigurationExternal,
    EmailConfigurationInternal, EmailInternalMapping,
)
from utils.enums import IPlanInquiryMethodCode

TARGET_QTY_DECIMAL_DIGITS_TO_ROUND_UP = 3
PAYMENT_TERM_MAPPING = {
    "AP00": "Advance Pmnt before production",
    "AS00": "Advance Pmnt. before Shipment",
    "BE30": "ตั๋วแลกเงิน 30 วัน",
    "BE45": "ตั๋วแลกเงิน 45 วัน",
    "BE60": "ตั๋วแลกเงิน 60 วัน",
    "BE75": "ตั๋วแลกเงิน 75 วัน",
    "BE90": "ตั๋วแลกเงิน 90 วัน",
    "BS30": "ตั๋วแลกเงินล่วงหน้า 30 วัน",
    "BS60": "ตั๋วแลกเงินล่วงหน้า 60 วัน",
    "DA2A": "D/A120 days after B/L date",
    "DA30": "D/A 30 days after B/L date",
    "DA45": "D/A 45 days after B/L date",
    "DA60": "D/A 60 days after B/L date",
    "DA75": "D/A 75 days after B/L date",
    "DA8A": "D/A180 days after B/L date",
    "DA90": "D/A 90 days after B/L date",
    "DP00": "Document against payment",
    "DP07": "D/P 7 days after B/L date",
    "DP15": "D/P 15 days after B/L date",
    "DP30": "D/A 30 days after B/L date",
    "DP45": "D/A 45 days after B/L date",
    "DPAV": "Document against payment",
    "FCA3": "เงินสด - HSBC",
    "FCB3": "เงินสด - KBANK",
    "FCC3": "เงินสด - TMB",
    "FDA3": "เงินสด - HSBC",
    "FDB3": "เงินสด - KBANK",
    "FDC3": "เงินสด - TMB",
    "LB0A": "L/C 100 DAYS AFTER B/L DATE",
    "LB14": "L/C 14 DAYS AFTER B/L DATE",
    "LB2A": "L/C 120 DAYS AFTER B/L DATE",
    "LB30": "L/C 30 DAYS AFTER B/L DATE",
    "LB35": "L/C 35 DAYS AFTER B/L DATE",
    "LB40": "L/C 40 DAYS AFTER B/L DATE",
    "LB45": "L/C 45 DAYS AFTER B/L DATE",
    "LB4B": "L/C 240 DAYS AFTER B/L DATE",
    "LB5A": "L/C 150 DAYS AFTER B/L DATE",
    "LB60": "L/C 60 DAYS AFTER B/L DATE",
    "LB75": "L/C 75 DAYS AFTER B/L DATE",
    "LB8A": "L/C 180 DAYS AFTER B/L DATE",
    "LB90": "L/C 90 DAYS AFTER B/L DATE",
    "LC00": "L/C immediately",
    "LC2A": "L/C 120 days.",
    "LC30": "L/C 30 days.",
    "LC45": "L/C 45 days.",
    "LC60": "L/C 60 days.",
    "LC75": "L/C 75 days.",
    "LC8A": "L/C 180 days.",
    "LC90": "L/C 90 days.",
    "LD00": "D-L/C at sight",
    "LD07": "D-L/C 7 วัน",
    "LD15": "D-L/C 15 วัน",
    "LD30": "D-L/C 30 วัน",
    "LD60": "D-L/C 60 วัน",
    "LD90": "D-L/C 90 วัน",
    "LE30": "L/C 30 DAYS AFTER B/L DATE",
    "LE60": "L/C 60 DAYS AFTER B/L DATE",
    "LE90": "L/C 90 DAYS AFTER B/L DATE",
    "LT00": "L/C AT SIGHT",
    "LT30": "L/C 30 DAYS AFTER B/L DATE",
    "LT45": "L/C 45 DAYS AFTER B/L DATE",
    "LT60": "L/C 60 DAYS AFTER B/L DATE",
    "LT90": "L/C 90 DAYS AFTER B/L DATE",
    "NE30": "เงินเชื่อ 30 วัน (NE)",
    "NE45": "เงินเชื่อ 45 วัน (NE)",
    "NE60": "เงินเชื่อ 60 วัน (NE)",
    "NH07": "ภายใน 7 วันหลังจากส่งของ",
    "NH10": "ภายใน 10 วันหลังจากส่งของ",
    "NH15": "ภายใน 15 วันหลังจากส่งของ",
    "NH30": "ภายใน 30 วันหลังจากส่งของ",
    "NH045": "ภายใน 45 วันหลังจากส่งของ",
    "NH047": "ภายใน 47 วันหลังจากส่งของ",
    "NH060": "ภายใน 60 วันหลังจากส่งของ",
    "NH75": "ภายใน 75 วันหลังจากส่งของ",
    "NH8A": "ภายใน 180 วันหลังจากส่งของ",
    "NH90": "ภายใน 90 วันหลังจากส่งของ",
    "NM01": "เงินสด 1 วัน",
    "NM02": "เงินสด 2 วัน",
    "NM07": "เงินสด 7 วัน",
    "NM15": "เงินสด 15 วัน",
    "NM30": "เงินสด 30 วัน",
    "NT00": "เงินสด",
    "NT01": "เงินเชื่อ 1 วัน",
    "NT02": "เงินเชื่อ 2 วัน",
    "NT03": "เงินเชื่อ 3 วัน",
    "NT04": "เงินเชื่อ 4 วัน",
    "NT05": "เงินเชื่อ 5 วัน",
    "NT07": "เงินเชื่อ 7 วัน",
    "NT0A": "เงินเชื่อ 100 วัน",
    "NT10": "เงินเชื่อ 10 วัน",
    "NT14": "เงินเชื่อ 14 วัน",
    "NT15": "เงินเชื่อ 15 วัน",
    "NT1A": "เงินเชื่อ 110 วัน",
    "NT20": "เงินเชื่อ 20 วัน",
    "NT2A": "เงินเชื่อ 120 วัน",
    "NT30": "เงินเชื่อ 30 วัน",
    "NT3G": "เงินเชื่อ 135 วัน",
    "NT40": "เงินเชื่อ 40 วัน",
    "NT45": "เงินเชื่อ 45 วัน",
    "NT5A": "เงินเชื่อ 150 วัน",
    "NT60": "เงินเชื่อ 60 วัน",
    "NT6C": "เงินเชื่อ 360 วัน",
    "NT70": "เงินเชื่อ 70 วัน",
    "NT75": "เงินเชื่อ 75 วัน",
    "NT8A": "เงินเชื่อ 180 วัน",
    "NT90": "เงินเชื่อ 90 วัน",
    "TC03": "30% T/T ADV , 70%  L/C SIGHT",
    "TC05": "50% T/T ADV , 50% T/T AT SIGHT",
    "TL03": "T / T 3 days after B / L date",
    "TL05": "T / T 5 days after B / L date",
    "TL07": "T / T 7 days after B / L date",
    "TL10": "T / T 10 days after B / L date",
    "TL14": "T / T 14 days after B / L date",
    "TL15": "T / T 15 days after B / L date",
    "TL21": "T / T 21 days after B / L date",
    "TL2A": "T / T 120 days after B / L date",
    "TL30": "T / T 30 days after B / L date",
    "TL35": "T / T 35 days after B / L date",
    "TL3G": "T / T 135 days after B / L date",
    "TL45": "T / T 45 days after B / L date",
    "TL60": "T / T 60 days after B / L date",
    "TL75": "T / T 75 days after B / L date",
    "TL8A": "T / T 180 days after B / L date",
    "TL90": "T / T 90 days after B / L date",
    "TP00": "T / T against shipping documents",
    "TS00": "T / T before shipment.",
    "TT00": "T / T at sight",
    "TT15": "T / T on 15th day next month",
    "TT25": "T / T on 25th day next month",
    "TT60": "T / T on 60th day next month",
    "TV00": "T / T after invoice, B / L, AWB date",
    "TV07": "T / T 7 days after inv., B / L,AWB",
    "TV10": "T / T 10 days after inv., B / L,AWB",
    "TV14": "T / T 14 days after inv., B / L,AWB",
    "TV15": "T / T 15 days after inv., B / L,AWB",
    "TV20": "T / T 20 days after inv., B / L,AWB",
    "TV2A": "T / T 120 days after inv., B / L,AWB",
    "TV30": "T / T 30 days after inv., B / L,AWB",
    "TV45": "T / T 45 days after inv., B / L,AWB",
    "TV60": "T / T 60 days after inv., B / L,AWB",
    "TV6C": "T / T 360 days after inv., B / L,AWB",
    "TV75": "T / T 75 days after inv., B / L,AWB",
    "TV90": "T / T 90 days after inv., B / L,AWB",
    "TW07": "T/T 7 days after AWB date.",
    "TW14": "T/T 14 days after AWB date.",
    "TW30": "T/T 30 days after AWB date.",
    "TW45": "T/T 45 days after AWB date.",
    "TW60": "T/T 60 days after AWB date.",
    "TW75": "T/T 75 days after AWB date.",
    "TW90": "T/T 90 days after AWB date.",
}

'''
SEO-4808: irrespective of the type of order items in an order,
        always have to get the plant info from the 1st item (after excluding Container order items) will be set as Default plant to Container 
'''

DUPLICATE_ALT_MAT_MAPPING_ERR_MSG = """
เนื่องจากมี Material Master นี้ในระบบแล้ว
กรุณากลับไปหน้าค้นหา เพื่อเพิ่มหรือแก้ไขข้อมูล
""".strip()


def update_plant_for_container_order_lines(container_order_lines, qs_order_lines):
    qs_order_lines_plant = list(
        filter(lambda x: (x not in container_order_lines and x.plant), qs_order_lines))
    if qs_order_lines_plant:
        first_plant = qs_order_lines_plant[0].plant
        for container_order_line in container_order_lines:
            container_order_line.plant = first_plant
        sap_migration_models.OrderLines.objects.bulk_update(container_order_lines, ["plant"])


def update_plant_for_container_order_lines_for_eo_upload(container_order_lines, qs_order_lines):
    qs_order_lines_plant = list(
        filter(lambda x: (x not in container_order_lines and x.plant), qs_order_lines))
    if qs_order_lines_plant:
        min_qs_order_lines_plant = min(qs_order_lines_plant, key=lambda x: x.item_no)
        plant = min_qs_order_lines_plant.plant
        first_plant = plant if plant else ""
        for container_order_line in container_order_lines:
            container_order_line.plant = first_plant
        sap_migration_models.OrderLines.objects.bulk_update(container_order_lines, ["plant"])


def convert_date_with_timezone(date_value: datetime_lib.datetime, timezone: Union[int, float]) -> datetime_lib.datetime:
    new_date = date_value - timedelta(hours=timezone)
    return new_date


def update_date_range_with_timezone(date_range: dict, timezone: Union[int, float]) -> dict:
    for k, v in date_range.items():
        v = datetime(day=v.day, year=v.year, month=v.month)
        if k == 'lte':
            v = datetime(day=v.day, year=v.year, month=v.month, hour=23, minute=59, second=59, microsecond=999)
        date_range[k] = convert_date_with_timezone(v, timezone)
    return date_range


# Order Status helper
def update_order_status(order_id):
    # SEO-4576,SEO-4933: Exclude Container Items to decide Order status from Order Items Status only for export orders
    order_line_status = list(
        models.OrderLines.objects.filter(order_id=order_id).exclude(Q(status__in=["Disable", "Delete", ""]) |
                                                                    Q(Q(item_cat_eo__in=[
                                                                        ItemCat.ZKC0.value]) & Q(
                                                                        type__in=[
                                                                            OrderType.EXPORT.value]))).values_list(
            'item_status_en', flat=True))
    if not order_line_status or None in order_line_status:
        order_status = IPlanOrderStatus.RECEIVED_ORDER.value
        return order_status, IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)

    count_complete = 0
    count_cancel = 0
    count_full_committed_order = 0

    for status in order_line_status:
        if status == IPlanOrderItemStatus.CANCEL.value:
            count_cancel += 1
            count_complete += 1
            count_full_committed_order += 1
            if count_cancel >= len(order_line_status):
                order_status = IPlanOrderStatus.CANCEL.value
                return (
                    order_status,
                    IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
                )
            _validate_order_status_complete_and_full_committed(count_complete, count_full_committed_order,
                                                               order_line_status)
            continue
        if status == IPlanOrderItemStatus.COMPLETE_DELIVERY.value:
            count_complete += 1
            if count_complete >= len(order_line_status):
                order_status = IPlanOrderStatus.COMPLETED_DELIVERY.value
                return (
                    order_status,
                    IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
                )
            continue
        if status == IPlanOrderItemStatus.PARTIAL_DELIVERY.value:
            order_status = IPlanOrderStatus.PARTIAL_DELIVERY.value
            return (
                order_status,
                IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
            )
        if status == IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value:
            count_full_committed_order += 1
            if count_full_committed_order >= len(order_line_status):
                order_status = IPlanOrderStatus.FULL_COMMITTED_ORDER.value
                return (
                    order_status,
                    IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
                )

    if 1 <= count_full_committed_order < len(
            order_line_status) and IPlanOrderStatus.FULL_COMMITTED_ORDER.value in order_line_status:
        order_status = IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value
        return (
            order_status,
            IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
        )

    if all(order == IPlanOrderStatus.FULL_COMMITTED_ORDER.value or order == IPlanOrderItemStatus.CANCEL.value for order
           in order_line_status):
        order_status = IPlanOrderStatus.FULL_COMMITTED_ORDER.value
        return (
            order_status,
            IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
        )

    if count_complete >= len(order_line_status) and IPlanOrderStatus.COMPLETED_DELIVERY.value in order_line_status:
        order_status = IPlanOrderStatus.COMPLETED_DELIVERY.value
        return order_status, IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
    else:
        order_status = IPlanOrderStatus.RECEIVED_ORDER.value
        return order_status, IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)


def get_list_email_by_so_no(sold_to_codes, sale_orgs, bu, feature, so_no):
    return get_list_email_by_mapping(sold_to_codes, sale_orgs, bu, feature, [], so_no=so_no, order_confirmation=True
                                     )


def get_list_email_by_product_group(sold_to_codes, sale_orgs, bu, feature, product_group):
    list_to, list_cc = get_list_email_by_mapping(sold_to_codes, sale_orgs, bu, feature, product_group, [],
                                                 pending_order=True)
    return list_to, list_cc


def get_email_configuration_internal(order_confirmation, pending_order):
    if order_confirmation:
        return EmailConfigurationInternal.objects.filter(order_confirmation=True)
    elif pending_order:
        return EmailConfigurationInternal.objects.filter(pending_order=True)


def get_list_email_by_mapping(sold_to_codes, sale_orgs, bu, feature, product_group, so_no, order_confirmation=False,
                              pending_order=False):
    orders = sap_migration_models.Order.objects.filter(so_no__in=so_no)
    product_group = list(map(lambda x: x.lower(), product_group))
    product_group.extend(
        list(map(lambda order: order.product_group.lower() if order.product_group else "", orders)))
    list_cc, list_to = compute_to_and_cc_list(feature, order_confirmation, pending_order, product_group, sale_orgs,
                                              sold_to_codes, bu)
    return " , ".join(set(list_to)), " , ".join(set(list_cc))


def compute_to_and_cc_list(feature, order_confirmation, pending_order, product_group, sale_orgs, sold_to_codes,
                           bu=PP_BU):
    list_to = []
    list_cc = get_internal_emails_by_config(feature, sale_orgs, product_group, bu)
    list_to, list_cc = get_email_to_and_cc(sold_to_codes, feature, product_group, list_to, list_cc)
    return list_cc, list_to


def get_email_to_and_cc(sold_to_codes, feature, product_group, list_to, list_cc):
    product_group_upper = [group.upper() for group in product_group] + ["", " ", "All"]
    email_settings = EmailConfigurationExternal.objects.filter(
        sold_to_code__in=sold_to_codes,
        product_group__in=product_group_upper,
        feature=feature.value,
    )
    if not email_settings and list_to and list_cc:
        return "", ""

    for setting in email_settings:
        if setting.mail_to:
            list_to.append(setting.mail_to)
        if setting.cc_to:
            list_cc.append(setting.cc_to)
    list_to = list(set(list_to))
    list_cc = list(set(list_cc))
    return list_to, list_cc


def add_sale_org_prefix(sale_orgs):
    result = []
    for sale_org in sale_orgs:
        if sale_org[0] == "0":
            result.append(sale_org.lstrip("0"))
        result.append(sale_org)
    return result


def get_text_credit_status_of_document_from_code(code):
    mapping_code_with_document = {
        "A": "Approved",
        "B": "Not approved",
        "C": "Approved, part relsd",
        "D": "Released",
        "Y": "Released",
        "Z": "Not approved"
    }
    return mapping_code_with_document.get(code, "Not performed")


def get_text_order_status_sap(code, distribution_channel):
    order_type = "export"
    if distribution_channel != "30":
        order_type = "domestic"
    export = "export"
    domestic = "domestic"
    mapping_text_with_status = {
        "C": {export: "Completed", domestic: "Completed"},
        "A": {export: "Open", domestic: "Open"},
        "B": {export: " Being processed", domestic: "Being processed"},
        "": {export: "May not occur", domestic: "May not occur"}
    }
    return mapping_text_with_status.get(code, {}).get(order_type, "")


def make_order_for_change_order(order, order_in_database, mapping_code_with_name, mapping_org_with_bu,
                                filter_in_database=False, filter_input=None):
    distribution_channel = filter_input.get('channel', "")
    if filter_in_database and not order_in_database:
        return
    return {
        "so_no": order.get("sdDoc", ""),
        "po_no": order.get("poNo", ""),
        "contract_no": order.get("contractNo", ""),
        "sold_to_party": f'{order.get("soldTo", "")} - {order.get("soldToName1", "")}',
        "ship_to": f'{order.get("shipTo", "")} - \n{order.get("shipToName1", "")}',
        "country": order.get("countryName", ""),
        "incoterm": order.get("incoterms1", ""),
        "payment": order.get("paymentTerm", ""),
        "bu": mapping_org_with_bu.get(str(order.get("salesOrg", ""))) or "",
        "project_name": order.get("descriptionInContract", ""),
        "company": mapping_code_with_name.get(str(order.get("salesOrg", "")), None),
        "payment_terms": PAYMENT_TERM_MAPPING.get(order.get("paymentTerm")),
        "credit_status_of_document": get_text_credit_status_of_document_from_code(order.get("creditStatus", "")),
        "order_date": order.get("createDate", ""),
        "order_status_sap": get_text_order_status_sap(order.get("status", ""),
                                                      distribution_channel),
        "order_status_e_ordering": getattr(order_in_database, "status", ""),
        "sales_org_code": order.get("salesOrg", ""),
        "sold_to_code": order.get("soldTo", ""),
        "is_not_ref": order.get("is_not_ref", False)
    }


def from_api_response_es25_to_change_order(data, input_filter):
    filter_in_database = False
    result = []
    list_so_no = [order.get("sdDoc") for order in data if order.get("sdDoc")]
    kwargs_filter = Q(**{"so_no__in": list_so_no})
    status = input_filter.get("order_status")
    if status:
        kwargs_filter &= Q(**{"status__in": status})
        filter_in_database = True
    mapping_so_no_with_order_in_database = sap_migration_models.Order.objects.filter(kwargs_filter).distinct(
        "so_no").in_bulk(field_name="so_no")
    if filter_in_database and not mapping_so_no_with_order_in_database:
        return result
    mapping_code_with_sales_organization = sap_master_data_models.SalesOrganizationMaster.objects.distinct(
        "code").in_bulk(field_name="code")
    mapping_code_with_name = {}
    mapping_org_with_bu = {}
    for code, obj in mapping_code_with_sales_organization.items():
        mapping_code_with_name[code] = code + ' - ' + (getattr(obj, "name", "") or "")
        bu_name = obj.business_unit and obj.business_unit.name or ""
        mapping_org_with_bu[code] = bu_name
    for order_response in data:
        row = make_order_for_change_order(order_response,
                                          mapping_so_no_with_order_in_database.get(order_response.get("sdDoc", None)),
                                          mapping_code_with_name, mapping_org_with_bu, filter_in_database, input_filter)
        if row:
            result.append(row)
    return result


def from_api_response_es26_to_change_order(info, key_order, key_rs=None):
    sap_order_response = info.variable_values.get("sap_order_response")
    try:
        order_texts = {}
        data = sap_order_response.get("data", [])[0]
        if key_order == "orderHeaderIn":
            result = data.get(key_order)

            return result.get(key_rs, "")

        if key_order == "orderItems":
            results = data.get(key_order, [])
            order_texts_sap = data.get("orderText")
            order_partner_sap = (data.get("orderPartners"))
            mapping_order_partner = {}
            for partner in order_partner_sap:
                if partner.get('partnerRole') == 'WE' and partner.get('itemNo'):
                    ship_to = make_ship_to_from_order_partner(partner)
                    mapping_order_partner[partner.get('itemNo')] = ship_to
            for order_text in order_texts_sap:
                if not order_texts.get(order_text.get("ItemNo")):
                    order_texts[order_text.get("ItemNo")] = [order_text]
                else:
                    order_texts[order_text.get("ItemNo")].append(order_text)

            # inject order_line here to optimize query db
            so_no = data["orderHeaderIn"]["saleDocument"]
            list_item_no = [item["itemNo"].lstrip("0") for item in results]
            order_lines = sap_migration_models.OrderLines.objects \
                .filter(order__so_no=so_no) \
                .filter(item_no__in=list_item_no)
            item_no_to_order_line = {order_line.item_no: order_line for order_line in order_lines}
            ####################################################################################

            for result in results:
                result.update(get_data_from_order_text(order_texts.get(result.get("itemNo"))))
                if result['itemNo'] in mapping_order_partner:
                    result['shipTo'] = mapping_order_partner[result['itemNo']]
                result["itemNo"] = result["itemNo"].lstrip("0")

                # inject order line instance
                result["order_line_instance"] = item_no_to_order_line.get(result["itemNo"])
                result["original_request_date"] = result.get("shiptToPODate")
            return results

        if key_order == "orderCondition":
            results = data.get(key_order, [])
            for result in results:
                # SEO-4289, given SAP ES-26 response, orderCondition[0] doesn't have itemNo hence the check before accessing
                if result.get("itemNo"):
                    result["itemNo"] = result["itemNo"].lstrip("0")

            return results

        return data.get(key_order, [])

    except:
        return ""


def get_name1_from_sold_to(code):
    if not code or '-' in code:
        return code

    sold_to = get_sold_to_partner(code)
    return f'{code} - {getattr(sold_to, "name1", "")}'


def get_name1_from_partner_code(code):
    if not code or '-' in code:
        return code
    sold_to = sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(partner_code=code).first()
    return f'{code} - {getattr(sold_to, "name1", "")}'


def prepare_param_for_es25_order_confirmation(filter_input):
    create_date_from = ""
    create_date_to = ""
    source_of_app = get_filter_source_of_app(filter_input)
    if date_input := filter_input.get('create_date'):
        if date_from_input := date_input.get('gte'):
            create_date_from = convert_date_to_fit_params_in_es25(str(date_from_input))
        if date_to_input := date_input.get('lte'):
            create_date_to = convert_date_to_fit_params_in_es25(str(date_to_input))

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesOrderNo": filter_input.get('so_no', ""),
        "salesOrgList": prepare_sale_org_list_for_es25_order_confirmation(filter_input),
        "customerList": [{"customer": customer} for customer in
                         prepare_customer_list_for_es25(filter_input.get('sold_to'))],
        "customerPoNo": prepare_customer_po_no_for_es25(filter_input.get('po_no')),
        "createDateFrom": create_date_from,
        "createDateTo": create_date_to,
        "material": prepare_material_for_es25(filter_input.get('material_no_material_description')),
        "materialGroup1": prepare_material_group_1_for_es25(filter_input.get('product_group')),
        "flgItem": "X",
        "flgConfirm": filter_input.get("status") or "",
        "sourceApplication": source_of_app
    }
    final_params = {key: val for key, val in params.items() if val and val != ""}
    return final_params


def get_data_from_order_text(order_texts):
    result = {}
    mapping = {
        "Z001": "internal_comments_to_warehouse",
        "Z002": "external_comments_to_customer",
        "ZK02": "internal_comments_to_logistics",
        "0006": "production_information",
        "Z004": "shipping_mark"
    }
    if not order_texts:
        return result
    for text in order_texts:
        if text.get("textId") in mapping:
            text_lines = text.get("textLine", "")
            result[mapping.get(text.get('textId'))] = "\n".join(
                str(text_line.get('text', '')) if isinstance(text_line, dict) else ""
                for text_line in text_lines
            )
            mapping.pop(text.get("textId"))
    return result


def convert_date_time_timezone_asia(date_time):
    if date_time:
        return date_time.astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d.%m.%Y/%H:%M:%S")
    else:
        return None


def convert_date_time_to_timezone_asia(date_time):
    if date_time:
        return date_time.astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d.%m.%Y/%H:%M:%S")
    else:
        return None


def get_date_time_now_timezone_asia():
    return timezone.now().astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d.%m.%Y/%H:%M:%S")


def get_date_time_now_timezone_asia_Preview_order_pdf():
    return timezone.now().astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M:%S")


def get_id_of_object_model_from_code(model, code):
    if not code:
        return None
    obj = model.filter(code=code).first()
    if obj:
        return obj.id
    return None


def resolve_ref_pi_no(so_no):
    order = models.Order.objects.filter(so_no=so_no).first()
    return deepgetattr(order, "ref_pi_no", "")


def make_ship_to_from_order_partner(order_partner):
    address = order_partner.get("address", [])
    if not address:
        return ''
    address = address[0]
    return f'{order_partner.get("partnerNo")} - {address.get("name", "")} \n {address.get("street", "")} {address.get("district", "")} {address.get("city", "")} {address.get("postCode", "")}'


def update_order_lines_item_status_en_and_item_status_th(order, order_lines, item_status_en, item_status_th):
    update_order_lines = []
    for order_line in order_lines:
        order_line.refresh_from_db()
        order_line.item_status_en = item_status_en
        order_line.item_status_th = item_status_th
        if order_line.iplan and order_line.iplan.order_type:
            _handle_item_status_trigger_from_i_plan(order_line)
        update_order_lines.append(order_line)
    sap_migration_models.OrderLines.all_objects.bulk_update(update_order_lines, ['item_status_en', 'item_status_th'])
    status_en, status_thai = update_order_status(order.id)
    order.status = status_en
    order.status_thai = status_thai
    order.save()


def add_item_to_dict_with_index(mydict, index, key, value):
    pos = list(mydict.keys()).index(index)
    items = list(mydict.items())
    items.insert(pos, (key, value))
    mydict = dict(items)
    return mydict


def prepare_param_es21_order_text_for_change_order_domestic(order, order_lines, order_lines_change_request_date=None,
                                                            dtr_dtp_update=False):
    if order_lines_change_request_date is None:
        order_lines_change_request_date = set()
    order_text = []
    mapping_order = {
        "internal_comments_to_logistic": "Z002",
        "internal_comments_to_warehouse": "Z001",
        "external_comments_to_customer": "Z067",
        "product_information": "ZK08"
    }

    for attr in mapping_order:
        text_line_attr = getattr(order, attr, "") or ""
        order_text.append(
            {
                "itemNo": "000000",
                "textId": mapping_order.get(attr),
                "textLineList": [{"textLine": text} for text in text_line_attr.split("\n")]
            }
        )
    for line in order_lines:
        order_text.append(
            {
                "itemNo": line.item_no,
                "textId": "Z001",
                "textLineList": [{"textLine": text} for text in
                                 getattr(line, "internal_comments_to_warehouse", "").split("\n")]
                if getattr(line, "internal_comments_to_warehouse", "") else []
            }
        )
        order_text.append(
            {
                "itemNo": line.item_no,
                "textId": "Z002",
                "textLineList": [{"textLine": text} for text in
                                 getattr(line, "external_comments_to_customer", "").split("\n")]
                if getattr(line, "external_comments_to_customer", "") else []
            }
        )
        if line.item_no in order_lines_change_request_date:
            # UI is passing only value as either C4 or C3
            text_line = "Logistic" if \
                order_lines_change_request_date[line.item_no] == ReasonForChangeRequestDateEnum.C4.value else "Customer"
            order_text.append(
                {
                    "itemNo": line.item_no,
                    "textId": "Z004",
                    "textLineList": [{"textLine": text_line}]
                }
            )
            # add_lang_to_sap_text_field( order, order_text, "Z004", line.item_no )

        '''
        SEO-4953: While processing ES38 (dtr_dtp_update is 'True') 
            Send DTR, DTP & Class mark together to SAP ES21 for Domestic orders
        '''
        if line.type in [OrderType.DOMESTIC.value, OrderType.CUSTOMER.value] and dtr_dtp_update:
            if line.dtr:
                # dtr
                order_text.append(
                    {
                        "itemNo": line.item_no,
                        "textId": "Z018",
                        "textLineList": [{"textLine": line.dtr}] if line.dtr else [{"textLine": " "}]
                    }
                )
            if line.dtp:
                # dtp
                order_text.append(
                    {
                        "itemNo": line.item_no,
                        "textId": "Z019",
                        "textLineList": [{"textLine": line.dtp}] if line.dtp else [{"textLine": " "}]
                    }
                )
            if line.dtr and line.dtp and line.actual_gi_date:
                # classmark
                order_text.append(
                    {
                        "itemNo": line.item_no,
                        "textId": "Z020",
                        "textLineList": [{"textLine": line.remark}] if line.remark else [{"textLine": " "}]
                    }
                )
        if line.type == OrderType.EXPORT.value and not dtr_dtp_update:
            send_class_mark_to_sap_flag = False
            if line.remark:
                remark_list = [rm.strip() for rm in line.remark.split(",") if rm.strip()]
                for _remark_list in remark_list:
                    if _remark_list in any(["C1", "C2", "C3", "C4"]):
                        send_class_mark_to_sap_flag = True
                        break
                if send_class_mark_to_sap_flag:
                    order_text.append(
                        {
                            "itemNo": line.item_no,
                            "textId": "Z020",
                            "textLineList": [{"textLine": line.remark}] if line.remark else [{"textLine": " "}]
                        }
                    )
    return order_text


def append_order_schedule_with_confirm_qty(origin_item_db, split_items, original_order_schedule_in,
                                           original_order_schedule_inx):
    assigned_quantity = origin_item_db.assigned_quantity or 0
    if assigned_quantity == 0:
        return
    split_quantity = sum(item["quantity"] for item in split_items)
    original_confirm_quantity = round_qty_decimal(assigned_quantity - split_quantity)
    original_order_schedule_in["confirmQty"] = original_confirm_quantity
    original_order_schedule_inx["confirmQuantity"] = True


def prepare_param_for_yt65838(so_no, origin_item, split_items, origin_item_db, info):
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    order_line_split_parts = []
    order_partners = []
    hour_add = "T00:00:00Z"

    original_order_item_in = {
        "itemNo": origin_item_db.item_no.zfill(6),
        "material": origin_item_db.material_variant.code,
        "targetQty": round_qty_decimal(origin_item.get("quantity")),
        "refDoc": origin_item_db.order.contract.code,
        "refDocIt": origin_item_db.ref_doc_it if origin_item_db.ref_doc_it else origin_item_db.contract_material and origin_item_db.contract_material.item_no.zfill(
            6) or ""
    }

    original_order_item_inx = {
        "itemNo": origin_item.get("item_no", "").zfill(6),
        "updateflag": "U",
        "targetQty": True,
    }

    original_order_schedule_in = {
        "itemNo": origin_item.get("item_no", "").zfill(6),
        "scheduleLine": "0001",
        "reqQty": round_qty_decimal(origin_item.get("quantity")),
    }

    original_order_schedule_inx = {
        "itemNo": origin_item.get("item_no").zfill(6),
        "scheduleLine": "0001",
        "updateflag": "U",
        "requestQuantity": True,
    }
    recheck_param_inx(original_order_item_in, original_order_item_inx)
    recheck_param_inx(original_order_schedule_in, original_order_schedule_inx)

    append_order_schedule_with_confirm_qty(origin_item_db, split_items, original_order_schedule_in,
                                           original_order_schedule_inx)

    order_line_split_part = {
        "orderCode": so_no.lstrip("0"),
        "lineCode": origin_item_db.item_no,
        "requestDate": str(origin_item_db.request_date) + hour_add,
        "confirmedDate": str(origin_item_db.request_date) + hour_add,
        "dispatchDate": str(origin_item_db.request_date) + hour_add,
        "deliveryDate": str(origin_item_db.request_date) + hour_add,
        "quantity": round_qty_decimal(origin_item.get("quantity")),
        "unit": origin_item_db.sales_unit,
    }

    order_items_in.append(original_order_item_in)
    order_items_inx.append(original_order_item_inx)
    order_schedules_in.append(original_order_schedule_in)
    order_schedules_inx.append(original_order_schedule_inx)
    order_line_split_parts.append(order_line_split_part)

    for split_item in split_items:
        split_order_item_in = {
            "itemNo": split_item.item_no.zfill(6),
            "material": origin_item_db.material_variant.code,
            "targetQty": round_qty_decimal(split_item.quantity),
            "salesUnit": origin_item_db.sales_unit,
            "plant": origin_item_db.plant,
            "shippingPoint": origin_item_db.shipping_point,
            "route": origin_item_db.route.split(" - ")[0] if origin_item_db.route else "",
            "purchaseNoC": origin_item_db.po_no if origin_item_db.po_no else "",
            "itemCategory": origin_item_db.item_category,
            "poDate": origin_item_db.original_request_date.strftime(
                "%d/%m/%Y") if origin_item_db.original_request_date else "",
            "overdlvtol": origin_item_db.delivery_tol_over if origin_item_db.delivery_tol_over else 0,
            "unlimitTol": "",
            "unddlvTol": origin_item_db.delivery_tol_under if origin_item_db.delivery_tol_under else 0,
            "refDoc": origin_item_db.order.contract.code,
            "refDocIt": origin_item_db.ref_doc_it if origin_item_db.ref_doc_it else origin_item_db.contract_material and origin_item_db.contract_material.item_no.zfill(
                6) or ""
        }
        if split_order_item_in["overdlvtol"] == 0 and split_order_item_in["unddlvTol"] == 0:
            split_order_item_in["unlimitTol"] = "X"
        split_order_item_inx = {
            "itemNo": split_item.item_no.zfill(6),
            "updateflag": "I",
            "targetQty": True,
            "salesUnit": True,
            "plant": True,
            "shippingPoint": True,
            "route": True,
            "custPoNo": True,
            "itemCategory": True,
            "poDate": True,
            "overdlvtol": True,
            "unlimitTol": True,
            "unddlvTol": True
        }

        split_order_schedule_in = {
            "itemNo": split_item.item_no.zfill(6),
            "scheduleLine": "0001",
            "reqDate": split_item.request_date.strftime("%d/%m/%Y"),
            "reqQty": round_qty_decimal(split_item.quantity),
            "confirmQty": split_item.quantity,
        }

        split_order_schedule_inx = {
            "itemNo": split_item.item_no.zfill(6),
            "scheduleLine": "0001",
            "updateflag": "I",
            "requestDate": True,
            "requestQuantity": True,
            "confirmQuantity": True,
        }

        order_line_split_part = {
            "orderCode": so_no.lstrip("0"),
            "lineCode": split_item.item_no,
            "requestDate": str(split_item.get("request_date")) + hour_add,
            "confirmedDate": str(split_item.get("request_date")) + hour_add,
            "dispatchDate": str(split_item.get("request_date")) + hour_add,
            "deliveryDate": str(split_item.get("request_date")) + hour_add,
            "quantity": round_qty_decimal(split_item.quantity),
            "unit": origin_item_db.sales_unit
        }

        order_partner = {
            "partnerRole": "WE",
            "partnerNumb": origin_item_db.ship_to.split(" - ")[0],
            "itemNo": split_item.item_no.zfill(6)
        } if origin_item_db.ship_to else None

        order_items_in.append(split_order_item_in)
        order_items_inx.append(split_order_item_inx)
        order_schedules_in.append(split_order_schedule_in)
        order_schedules_inx.append(split_order_schedule_inx)
        order_line_split_parts.append(order_line_split_part)
        if order_partner:
            order_partners.append(order_partner)

    order_line_split_request = {
        "updateId": str(uuid.uuid1().int),
        "orderCode": so_no.lstrip("0"),
        "lineCode": origin_item.get("item_no"),
        "OrderLineSplitPart": order_line_split_parts
    }

    order_header_in = {
        "refDoc": origin_item_db.order.contract.code
    }

    params = {
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
        "OrderLineSplitRequest": order_line_split_request
    }
    scgp_user = info.context.user.scgp_user
    if scgp_user and scgp_user.sap_id:
        params["sapId"] = scgp_user.sap_id

    if not order_partners:
        params.pop("orderPartners")

    return params


def call_yt65838_split_order(so_no, origin_item, split_items, origin_item_db, info):
    param = prepare_param_for_yt65838(so_no, origin_item, split_items, origin_item_db, info)
    product_group = origin_item_db.order.product_group
    if is_other_product_group(product_group):
        param.pop("OrderLineSplitRequest")
        logging.info(f"[Domestic Split item] For order so_no: {so_no}"
                     f" Called ES21 by skipping YT-65838 for the product group: {product_group}")
        return call_sap_api_for_split_order(so_no, origin_item, split_items, origin_item_db, param)

    log_val = {
        "order_number": so_no,
        "orderid": origin_item_db.order.id,
    }
    try:
        logging.info(f"[Domestic Split item] called YT-65838 for order so_no {so_no}")
        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value,
                                               **log_val).request_mulesoft_post(
            IPlanEndPoint.I_PLAN_SPLIT.value,
            param
        )
        return response

    except ValidationError as e:
        logging.error(f"[Domestic Split item] ValidationError occurred for the order so_no {so_no}, error: {e}")
        error_src_list = [error_src.upper() for error_src in e.args[0].get("error_src", [""])]
        if ("IPLAN" in error_src_list) or (str(e.args[0].get("error_src", "")).upper() == "IPLAN"):
            update_attention_type_r5([origin_item_db])
        raise e


def call_sap_api_for_split_order(so_no, origin_item, split_items, origin_item_db, param):
    log_val = {
        "order_number": so_no,
        "orderid": origin_item_db.order.id,
    }

    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value,
                                           **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        param
    )
    return response


def gen_param_es21(order, sap_update_flag=None):
    if sap_update_flag is None:
        sap_update_flag = {}
    order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    order_partners = []
    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    # order_conditions_in = []
    # order_conditions_inx = []
    ship_to_partners = {}
    confirm_quantity = 0
    sold_to_code = order.sold_to.sold_to_code if order.sold_to else order.sold_to_code

    for order_line in order_lines:
        if order_line.ship_to:
            ship_to_partners[order_line.item_no] = order_line.ship_to.split(" - ")[0]
    partners = sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
        sold_to_code=sold_to_code, partner_code__in=ship_to_partners.values(), partner_role="WE").distinct(
        "partner_code").in_bulk(field_name="partner_code")

    for line in order_lines:
        if ship_to_partners.get(line.item_no):
            order_partners.append(
                {
                    "partnerRole": "WE",
                    "partnerNumb": ship_to_partners[line.item_no],
                    "itemNo": line.item_no,
                    "addressLink": partners[ship_to_partners[line.item_no]].address_link
                }
            )

    for line in order_lines:
        item_no = line.item_no.zfill(6)
        request_items_base = {
            "itemNo": item_no,
            "material": line.material_variant.code
            if line.material_variant.code
            else "",
            "targetQty": line.target_quantity if line.target_quantity else 0,
            "salesUnit": "ROL",
            "plant": line.plant or "",
            "route": line.route.split(" - ")[0] if line.route else "",
            "purchaseNoC": "MPS/PO/SKT023/21",
            "poItemNo": line.po_item_no if line.po_item_no else "",
            "itemCategory": line.item_cat_eo or "",
            "priceGroup1": "",
            "priceGroup2": "",
            "poNo": line.po_no if line.po_no else "",
            "poitemNoS": line.purch_nos if line.purch_nos else "",  # Not sure
            "usage": "100",
            "overdlvtol": line.delivery_tol_over,
            "unlimitTol": "",
            "unddlvTol": line.delivery_tol_under,
            "reasonReject": "",
            "paymentTerms": line.payment_term_item
            if line.payment_term_item
            else "",
            "denominato": 1,
            "numconvert": 1000,
            "refDoc": line.ref_doc if line.ref_doc else "",
            "refDocIt": line.contract_material and line.contract_material.item_no or "",
            "flgUpdateContract": "",
        }

        if line.delivery_tol_unlimited:
            request_items_base["overdlvtol"] = 0
            request_items_base["unlimitTol"] = "X"
            request_items_base["unddlvTol"] = 0

        if not line.delivery_tol_over:
            request_items_base.pop("overdlvtol")

        if not line.delivery_tol_under:
            request_items_base.pop("unddlvTol")

        order_items_in.append(request_items_base)

        order_items_inx.append(
            {
                "itemNo": item_no,
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                "targetQty": True,
                "salesUnit": True,
                "plant": True,
                "route": True,
                "poItemNo": True,
                "itemCategory": False,
                "priceGroup1": False,
                "priceGroup2": False,
                "poNo": True,
                "poitemNoS": True,
                "usage": True,
                "overdlvtol": True,
                "unlimitTol": True,
                "unddlvTol": True,
                "reasonReject": True,
                "paymentTerms": True,
                "denominato": True,
                "numconvert": True,
            }
        )
        if line.iplan:
            confirm_quantity = line.iplan.iplant_confirm_quantity if line.i_plan_on_hand_stock else 0

        if line.item_cat_eo == ItemCat.ZKC0.value:
            confirm_quantity = line.quantity or 0

        order_schedules_in.append(
            {
                "itemNo": item_no,
                "scheduleLine": "0001",
                "reqDate": line.request_date.strftime("%d/%m/%Y") if line.request_date else "",
                "reqQty": line.quantity,
                "confirmQty": confirm_quantity or 0
            }
        )
        order_schedules_inx.append(
            {
                "itemNo": item_no,
                "scheduleLine": "0001",
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                "scheduleLinecate": False,
                "requestDate": True,
                "requestQuantity": True,
                "confirmQuantity": True,
            }
        )
    order_text = prepare_param_es21_order_text_for_change_order_domestic(order, order_lines, dtr_dtp_update=True)
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": {
            "reqDate": order.request_date.strftime("%d/%m/%Y")
            if order.request_date
            else "",
            "incoterms1": order.incoterms_1.code if order.incoterms_1 else "",
            # "incoterms2": order.incoterms_2 if order.incoterms_2 else "",
            "poNo": order.po_no if order.po_no else "",
            "purchaseDate": order.po_date.strftime("%d/%m/%Y") if order.po_date else "",
            "priceGroup": order.price_group if order.price_group else "",
            "priceDate": order.price_date.strftime("%d/%m/%Y")
            if order.price_date
            else "",
            "currency": order.currency and order.currency.code or order.doc_currency or "",
            "customerGroup": order.customer_group.code if order.customer_group else "",
            "salesDistrict": "",
            "shippingCondition": order.shipping_condition
            if order.shipping_condition
            else "",
            "customerGroup1": order.customer_group_1.code
            if order.customer_group_1
            else "",
            "customerGroup2": order.customer_group_2.code
            if order.customer_group_2
            else "",
            "customerGroup3": order.customer_group_3.code
            if order.customer_group_3
            else "",
            "customerGroup4": order.customer_group_4.code
            if order.customer_group_4
            else "",
            "refDoc": order.contract.code if order.contract else "",
        },
        "orderHeaderInX": {
            "reqDate": True,
            "incoterms1": True,
            "incoterms2": False,
            "poNo": True,
            "purchaseDate": True,
            "priceGroup": True,
            "priceDate": True,
            "currency": True,
            "customerGroup": True,
            "salesDistrict": True,
            "shippingCondition": True,
            "customerGroup1": True,
            "customerGroup2": True,
            "customerGroup3": True,
            "customerGroup4": True,
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
        "orderText": order_text,
        # "orderConditionsIn": order_conditions_in,
        # "orderConditionsInX": order_conditions_inx,
    }
    return params


def update_dtr_dtp_to_sap(list_so_no):
    orders = sap_migration.models.Order.objects.filter(so_no__in=list_so_no).all()
    for order in orders:
        param = gen_param_es21(order)
        log_val = {
            "orderid": order.id,
            "order_number": order.so_no,
            "feature": MulesoftFeatureType.DTR_DTP.value,
        }
        MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
            SapEnpoint.ES_21.value,
            param
        )
    return True


def deepgetattr(obj, attr, default_value=None):
    try:
        result = reduce(getattr, attr.split("."), obj)
        return result or default_value
    except AttributeError:
        return default_value


def deepget(obj, attr, default_value=None):
    try:
        return reduce(dict.get, attr.split("."), obj)
    except TypeError as e:
        return default_value


def add_param_to_i_plan_request(change_order_mapping, params):
    sold_to_code = deepget(change_order_mapping["order_input"], "fixed_data.sold_to_code")
    order_in_database = change_order_mapping["order_in_database"]
    for item_no, order_line_input in change_order_mapping["yt65156"].items():
        inquiry_method = order_line_input.get("iplan_details", {}).get("input_parameter") or "Domestic"
        inquiry_method_params = get_inquiry_method_params(inquiry_method)
        request_date = "-".join(order_line_input["order_information"]["request_date"].split("/")[::-1])
        request_line = {
            "lineNumber": item_no,
            "locationCode": sold_to_code.lstrip("0"),
            "consignmentOrder": False,
            "productCode": order_line_input["order_information"]["material_code"],
            "requestDate": f'{request_date}T00:00:00.000Z',
            "inquiryMethod": inquiry_method_params["inquiry_method"],
            "quantity": str(order_line_input["order_information"]["quantity"]),
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
            "fixSourceAssignment": order_line_input["order_information"]["plant"] or "",
            "requestType": "AMENDMENT",
            "consignmentLocation": order_line_input.get("iplan_details", {}).get("consignment_location", "").lstrip(
                '0') or order_in_database.sale_group_code or "",
            "DDQSourcingCategories": [
                {
                    "categoryCode": order_in_database.sale_group_code or ""
                },
                {
                    "categoryCode": order_in_database.sale_org_code or ""
                }
            ]
        }
        params["DDQRequest"]["DDQRequestHeader"][0]["DDQRequestLine"].append(request_line)
        order_line_input["request_type"] = request_line["requestType"]


def add_cancel_item_to_i_plan_request(change_order_mapping, params):
    sold_to_code = deepget(change_order_mapping["order_input"], "fixed_data.sold_to_code")
    for item_no, order_line_input in change_order_mapping["order_lines_cancel"].items():
        request_date = "-".join(order_line_input["order_information"]["request_date"].split("/")[::-1])
        request_line = {
            "lineNumber": item_no,
            "locationCode": sold_to_code,
            "productCode": order_line_input["order_information"]["material_code"],
            "requestDate": f'{request_date}T00:00:00.000Z',
            "inquiryMethod": IPlanInquiryMethodCode.JITCP.value,
            "quantity": str(order_line_input["order_information"]["quantity"]),
            "unit": "ROL",
            "transportMethod": "Truck",
            "typeOfDelivery": "E",
            "singleSourcing": False,
            "requestType": "DELETE"
        }
        params["DDQRequest"]["DDQRequestHeader"][0]["DDQRequestLine"].append(request_line)


def default_param_i_plan_request(so_no):
    return {
        "DDQRequest": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQRequestHeader": [
                {
                    "headerCode": so_no.lstrip("0"),
                    "autoCreate": False,
                    "DDQRequestLine": [
                    ]
                }
            ]
        }
    }


def default_param_es_21(so_no):
    return {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": so_no,
        "testrun": False,
        "orderHeaderIn": {},
        "orderHeaderInX": {},
        "orderPartners": [],
        "orderItemsIn": [],
        "orderItemsInx": [],
        "orderSchedulesIn": [],
        "orderSchedulesInx": [],
        "orderText": []
    }


def default_param_es_21_add_new_item(order_header):
    return {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order_header["so_no"],
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": order_header["contract_no"]
        },
        "orderHeaderInX": {},
        "orderPartners": [],
        "orderItemsIn": [],
        "orderItemsInx": [],
        "orderSchedulesIn": [],
        "orderSchedulesInx": [],
        "orderText": []
    }


def default_param_i_plan_rollback(so_no):
    return {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": so_no.lstrip("0"),
                    "originalHeaderCode": so_no.lstrip("0"),
                    "DDQConfirmLine": []
                }
            ]
        }
    }


def default_param_i_plan_confirm(so_no):
    return {
        "DDQConfirm": {
            "requestId": str(uuid.uuid1().int),
            "sender": "e-ordering",
            "DDQConfirmHeader": [
                {
                    "headerCode": so_no.lstrip("0"),
                    "originalHeaderCode": so_no.lstrip("0"),
                    "DDQConfirmLine": []
                }
            ]
        }
    }


def default_param_yt_65838(so_no):
    return {
        "OrderLineSplitRequest": {
            "updateId": str(uuid.uuid1().int),
            "orderCode": so_no,
            "lineCode": "",
            "OrderLineSplitPart": [
            ]
        }
    }


def default_param_yt_65217(so_no):
    return {
        "OrderUpdateRequest": {
            "updateId": str(uuid.uuid1().int),
            "OrderUpdateRequestLine": []
        }
    }


def get_inquiry_method_params(inquiry_method=InquiryMethodType.DOMESTIC.value):
    inquiry_method = inquiry_method.lower()
    if inquiry_method == InquiryMethodType.DOMESTIC.value.lower() or inquiry_method == InquiryMethodType.CUSTOMER.value.lower():
        return InquiryMethodParameter.DOMESTIC.value.copy()
    elif inquiry_method == InquiryMethodType.EXPORT.value.lower():
        return InquiryMethodParameter.EXPORT.value.copy()
    return InquiryMethodParameter.ASAP.value.copy()


def add_order_header_to_es_21(change_order_mapping, params):
    class Temp:
        def __init__(self, code):
            self.code = code

    sold_to_code = deepget(change_order_mapping["order_input"], OrderEdit.FIELDS.value.get("sold_to_code"))
    new_ship_to = deepget(change_order_mapping["order_input"], OrderEdit.FIELDS.value.get("ship_to"))
    new_bill_to = deepget(change_order_mapping["order_input"], OrderEdit.FIELDS.value.get("bill_to"))
    ship_to = (
        sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code,
            partner_code=new_ship_to,
            distribution_channel_code__in=[10, 20],
            partner_role='WE')
        .first()
    )
    ship_to_address_link = deepgetattr(ship_to, "address_link", "")

    bill_to = (
        sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(
            sold_to_code=sold_to_code,
            partner_code=new_bill_to,
            distribution_channel_code__in=[10, 20],
            partner_role='RE')
        .first()
    )
    bill_to_address_link = deepgetattr(bill_to, "address_link", "")
    mapping = {
        "incoterms1": "incoterms_1_id",
        "customer_group_1": "customer_group_1_id",
        "customer_group_2": "customer_group_2_id",
        "customer_group_3": "customer_group_3_id",
        "customer_group_4": "customer_group_4_id",
    }
    cus_1 = sap_master_data_models.CustomerGroup1Master.objects.in_bulk(field_name="pk")
    cus_2 = sap_master_data_models.CustomerGroup2Master.objects.in_bulk(field_name="pk")
    cus_3 = sap_master_data_models.CustomerGroup3Master.objects.in_bulk(field_name="pk")
    cus_4 = sap_master_data_models.CustomerGroup4Master.objects.in_bulk(field_name="pk")
    inco_1 = sap_master_data_models.Incoterms1Master.objects.in_bulk(field_name="pk")
    mapping_with_table = {
        "customer_group_1_id": cus_1,
        "customer_group_2_id": cus_2,
        "customer_group_3_id": cus_3,
        "customer_group_4_id": cus_4,
        "incoterms_1_id": inco_1,
    }
    field_order_header_change = change_order_mapping["order_header"]
    order_input = change_order_mapping["order_input"]
    for field_input, field_in_es_21 in Es21Params.ORDER_HEADER_LN.value.items():
        if field_order_header_change.get(field_input):
            field_input = mapping.get(field_input) or field_input
            value_input = deepget(order_input, OrderEdit.FIELDS.value[field_input], "")
            if value_input and field_input != "po_no" and value_input.isnumeric():
                value_input = int(value_input)
            params["orderHeaderIn"][field_in_es_21] = (
                    deepgetattr(mapping_with_table.get(field_input, {None: Temp(code=None)}).get(value_input),
                                "code", "") or value_input)

            params["orderHeaderInX"][field_in_es_21] = True
    params["orderHeaderIn"]["refDoc"] = deepget(order_input, "fixed_data.contract_no", "")

    for field_input, field_in_es_21 in Es21Params.ORDER_PARTNER.value.items():
        if field_order_header_change.get(field_input):
            new_data = deepget(order_input, OrderEdit.FIELDS.value[field_input], "")
            params["orderPartners"].append(
                make_order_partner_es_21(field_in_es_21, new_data))

    for field_input, text_id in Es21Params.ORDER_TEXT.value.items():
        if field_order_header_change.get(field_input):
            list_text = split_text_lines(deepget(order_input, OrderEdit.FIELDS.value[field_input], ""))
            order_text = {
                "itemNo": "000000",
                "textId": text_id,
                "textLineList": [{"textLine": text} for text in list_text]
            }
            params["orderText"].append(order_text)


def make_order_partner_es_21(field_name, new_data, item_no="00"):
    return {
        "partnerRole": field_name,
        "partnerNumb": new_data,
        "itemNo": item_no.zfill(6)
    }


def add_split_item_to_es_21(change_order_mapping, params):
    order_lines_original = change_order_mapping["order_lines_split"]
    order_lines_input = change_order_mapping["order_lines_input"]
    for item_no_original, order_lines_split in order_lines_original.items():
        for item_no, field_update in order_lines_split.items():
            order_line_in = {
                "itemNo": item_no
            }
            order_line_inx = {
                "itemNo": item_no,
                "updateflag": "I",
            }
            for field_name_input, field_in_es21 in Es21Params.ORDER_ITEMS.value.items():
                if field_name_input == "material_code":
                    order_line_in[field_in_es21] = deepget(order_lines_input[item_no],
                                                           ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input], "")
                    continue
                if field_name_input in field_update:
                    order_line_in[field_in_es21] = deepget(order_lines_input[item_no],
                                                           ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input], "")
                    order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
            params["orderItemsIn"].append(order_line_in)
            params["orderItemsInx"].append(order_line_inx)


def add_update_item_to_es_21(change_order_mapping, params, need_iplan_integration, contract_details=None, order=None):
    order_lines_update = change_order_mapping["order_lines_update"]
    order_lines_input = change_order_mapping["order_lines_input"]

    mapping_order_text = {
        "internal_comments_to_warehouse": "Z001",
        "external_comments_to_customer": "Z002",
        "ship_to_party": True,
        "reason_for_change_request_date": "Z004",
        "shipping_mark": "Z004"
    }
    reason_for_change_request_date_order_text = {
        "C3": "Logistic",
        "C4": "Customer",
    }

    for item_no, field_update in order_lines_update.items():
        order_line_in = {
            "itemNo": item_no.zfill(6)
        }
        order_line_inx = {
            "itemNo": item_no,
            "updateflag": "U"
        }

        order_schedules_in = {
            "itemNo": item_no.zfill(6),
            "scheduleLine": "0001"
        }
        order_schedules_inx = {
            "itemNo": item_no.zfill(6),
            "updateflag": "U"
        }

        for field_name_input, field_in_es21 in Es21Params.ORDER_ITEMS.value.items():
            if field_name_input == "material_code":
                order_line_in[field_in_es21] = deepget(order_lines_input[item_no],
                                                       ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input], "")
                continue
            if field_name_input == "quantity" and change_order_mapping.get("responseIPlan"):
                response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
                order_line_in[field_in_es21] = response_i_plan.get("quantity", None) or \
                                               change_order_mapping["order_lines_input"].get(item_no, {})[
                                                   "order_information"].get("quantity", None)
                order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
                continue
            if field_name_input in field_update:
                if field_name_input == "unlimited":
                    if deepget(order_lines_input[item_no], ItemDetailsEdit.NEW_ITEMS.value[field_name_input], ""):
                        order_line_in[field_in_es21] = "X"
                    else:
                        order_line_in[field_in_es21] = ""
                    order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
                    continue

                order_line_in[field_in_es21] = deepget(order_lines_input[item_no],
                                                       ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input], "")
                if "plant" in order_line_in and order_line_in.get("plant", None) == '':
                    # prod issue SEO-6479
                    update_item_value = ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input]
                    logging.info(
                        f"item_no: {item_no} and details: {order_lines_input[item_no]} "
                        f"/ update value :{update_item_value} / field_name_input : {field_name_input}"
                    )
                if not order_line_in[field_in_es21] and field_name_input not in ("over", "under"):
                    order_line_in[field_in_es21] = ''
                order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
                if field_name_input == "over" and "unlimited" not in field_update:
                    order_line_in["unlimitTol"] = ""
                    order_line_inx["unlimitTol"] = True

        order_line_in["refDoc"] = deepget(change_order_mapping["order_input"],
                                          OrderEdit.FIELDS.value.get("contract__code"))
        order_line_in["refDocIt"] = change_order_mapping['order_lines_in_database'][item_no].ref_doc_it

        params["orderItemsIn"].append(order_line_in)
        params["orderItemsInx"].append(order_line_inx)

        request_date = order_lines_update[item_no].get("request_date")
        quantity = order_lines_update[item_no].get("quantity")
        plant = order_lines_update[item_no].get("plant")
        if request_date or quantity:
            for field_name_input, field_in_es21 in Es21Params.ORDER_SCHEDULE.value.items():
                response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
                if field_name_input == "quantity" and (need_iplan_integration or quantity):

                    if not need_iplan_integration:
                        handle_quantity_order_schedule_without_plan(change_order_mapping, order_schedules_in,
                                                                    order_schedules_inx, item_no)
                    else:
                        order_schedules_in[field_in_es21] = response_i_plan.get("quantity", None) or \
                                                            change_order_mapping["order_lines_input"].get(item_no, {})[
                                                                "order_information"].get("quantity", None)
                        order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True

                    continue
                if field_name_input == "request_date" and (need_iplan_integration or request_date):
                    request_date_value = response_i_plan.get("request_date", None) or \
                                         change_order_mapping["order_lines_input"].get(item_no, {})[
                                             "order_information"].get("request_date", None)
                    '''
                        For Special Plants/Containers order_line_i_plan is empty hence didn't segregate the logic of dispatch date
                    '''
                    # SEO-6239: Remove request date compare logic and reqDate will be request date from UI
                    order_schedules_in[field_in_es21] = request_date_value
                    order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True
                    continue
                if field_name_input in field_update:
                    order_schedules_in[field_in_es21] = deepget(order_lines_input[item_no],
                                                                ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input],
                                                                "")
                    order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True
        if plant:
            response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
            if not order_schedules_in.get("reqQty") and need_iplan_integration:
                order_schedules_in["reqQty"] = response_i_plan.get("quantity", None) or \
                                               change_order_mapping["order_lines_input"].get(item_no, {})[
                                                   "order_information"].get("quantity", None)
                order_schedules_inx["requestQuantity"] = True

            if not order_schedules_in.get("reqDate") and need_iplan_integration:
                request_date_value = response_i_plan.get("request_date", None) or \
                                     change_order_mapping["order_lines_input"].get(item_no, {})[
                                         "order_information"].get("request_date", None)

                # SEO-6239: Remove compare request date with dispatch date logic & reqDate will be request date from UI
                order_schedules_in["reqDate"] = request_date_value
                order_schedules_inx["requestDate"] = True
        handle_confirm_quantity_order_schedule(change_order_mapping, item_no, order_schedules_in,
                                               order_schedules_inx)
        params["orderSchedulesIn"].append(order_schedules_in)
        params["orderSchedulesInx"].append(order_schedules_inx)

        for field_input, text_id in mapping_order_text.items():
            if field_input in field_update:
                if field_input == "shipping_mark":
                    order_text = {
                        "itemNo": item_no.zfill(6),
                        "textId": text_id,
                        "textLineList": [
                            {"textLine":
                                 deepget(order_lines_input[item_no],
                                         ItemDetailsEdit.FIELDS.value["shipping_mark"],
                                         "")}
                        ]
                    }

                    # add_lang_to_sap_text_field( order, order_text, text_id,order_line_in["refDocIt"]  )
                    params["orderText"].append(order_text)
                    continue

                if field_input == "reason_for_change_request_date":
                    """[SEO-7048] Skip sending textId Z004 when there is change in reason_for_change_request_date 
                    Z004 is using for both ‘Remark’ and ‘Reason for Change Request Date'  and getting appended while 
                    displaying in UI in the Remark field of 'Additional Data’ tab. Note: This logic can be used in 
                    future if BA provides new textId to send reason_for_change_request_date to sap"""
                    # reason_for_change = reason_for_change_request_date_order_text.get(
                    #     deepget(order_lines_input[item_no], OrderEdit.FIELDS.value[field_input], ""))
                    # if reason_for_change:
                    #     order_text = {
                    #         "itemNo": item_no.zfill(6),
                    #         "textId": text_id,
                    #         "language": "EN",
                    #         "textLineList": [
                    #             {"textLine": reason_for_change}
                    #         ]
                    #     }
                    #     params["orderText"].append(order_text)

                    add_class_mark_to_es21(change_order_mapping["order_lines_in_database"].get(item_no, None), params)
                    continue
                if field_input == "ship_to_party":
                    value = deepget(order_lines_input[item_no], "additional_data.ship_to_party")
                    order_partner = {
                        "partnerRole": "WE",
                        "partnerNumb": value,
                        "itemNo": item_no.zfill(6),
                    }
                    params["orderPartners"].append(order_partner)
                    continue
                list_text = split_text_lines(
                    deepget(order_lines_input[item_no], OrderEdit.FIELDS.value[field_input], ""))
                order_text = {
                    "itemNo": item_no.zfill(6),
                    "textId": text_id,
                    "textLineList": [
                        {"textLine": text} for text in list_text
                    ]
                }
                params["orderText"].append(order_text)
        params["orderHeaderIn"]["refDoc"] = deepget(change_order_mapping["order_input"], "fixed_data.contract_no", "")


def add_class_mark_to_es21(order_line, params):
    if order_line:
        class_mark = order_line.class_mark
        if class_mark and re.search(r"C3|C4", class_mark):
            # class mark
            params["orderText"].append({
                "itemNo": order_line.item_no.zfill(6),
                "textId": "Z020",
                "language": "EN",
                "textLineList": [{"textLine": order_line.class_mark}]
            })


def add_new_item_to_es_21(change_order_mapping, params):
    order_lines_new = change_order_mapping["order_lines_new"]
    mapping_order_text = {
        "internal_comments_to_warehouse": "Z001",
        "external_comments_to_customer": "Z002",
    }
    for item_no, field_input in order_lines_new.items():
        order_line_in = {
            "itemNo": item_no
        }
        order_line_inx = {
            "itemNo": item_no,
            "updateflag": "I"
        }
        order_schedules_in = {
            "itemNo": item_no.zfill(6),
            "scheduleLine": "0001"
        }
        order_schedules_inx = {
            "itemNo": item_no.zfill(6),
            "updateflag": "I"
        }
        fields_to_skip = ["po_no", "item_category", "shipping_point", "route"]
        for field_name_input, field_in_es21 in Es21Params.ORDER_ITEMS.value.items():
            if field_name_input == "quantity":
                response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
                order_line_in[field_in_es21] = round_qty_decimal(response_i_plan.get("quantity", None) or \
                                                                 change_order_mapping["order_lines_new"].get(item_no,
                                                                                                             {})[
                                                                     "order_information"].get("quantity", None))
                order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
                continue
            if field_name_input == "material_code":
                order_line_in[field_in_es21] = deepget(field_input,
                                                       ItemDetailsEdit.UPDATE_ITEMS.value[field_name_input], "")
                continue
            if field_name_input in fields_to_skip:
                continue

            order_line_in[field_in_es21] = deepget(order_lines_new[item_no],
                                                   ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "")
            order_line_inx[Es21Params.ORDER_ITEMS_INX.value.get(field_name_input)] = True
        if order_line_in.get("unlimitTol") == True:
            order_line_in["unlimitTol"] = "X"
        order_line_in["poDate"] = change_order_mapping["order_lines_in_database"].get(
            field_input.get("item_no")).original_request_date.strftime("%d/%m/%Y")
        order_line_inx["poDate"] = True
        order_line_in["refDoc"] = deepget(change_order_mapping["order_input"],
                                          OrderEdit.FIELDS.value.get("contract__code"))
        order_line_in["refDocIt"] = order_lines_new[item_no]["refDocIt"]
        params["orderItemsIn"].append(order_line_in)
        params["orderItemsInx"].append(order_line_inx)
        for field_name_input, field_in_es21 in Es21Params.ORDER_SCHEDULE.value.items():
            if field_name_input == "quantity":
                response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
                order_schedules_in[field_in_es21] = round_qty_decimal(response_i_plan.get("quantity", None) or \
                                                                      change_order_mapping["order_lines_new"].get(
                                                                          item_no, {})[
                                                                          "order_information"].get("quantity", None))
                order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True
                continue
            if field_name_input == "request_date":
                req_date = deepget(order_lines_new[item_no], ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "")
                try:
                    order_schedules_in[field_in_es21] = datetime.strptime(req_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                except ValueError:
                    order_schedules_in[field_in_es21] = req_date
                order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True
                continue

            order_schedules_in[field_in_es21] = deepget(order_lines_new[item_no],
                                                        ItemDetailsEdit.NEW_ITEMS.value[field_name_input], "")
            order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get(field_name_input)] = True
        handle_new_confirm_quantity_order_schedule(change_order_mapping, item_no, order_schedules_in,
                                                   order_schedules_inx)
        handle_new_delivery_block_order_schedule(change_order_mapping, item_no, order_schedules_inx)
        params["orderSchedulesIn"].append(order_schedules_in)
        params["orderSchedulesInx"].append(order_schedules_inx)
        for field, value in field_input.get("additional_data", {}).items():
            if field == "ship_to_party" and value:
                order_partner = {
                    "partnerRole": "WE",
                    "partnerNumb": value,
                    "itemNo": item_no.zfill(6),
                }
                params["orderPartners"].append(order_partner)
                continue
            text_id = mapping_order_text.get(field, None)
            if (text_id):
                order_text = {
                    "itemNo": item_no.zfill(6),
                    "textId": text_id,
                    "textLineList": [
                        {"textLine": text} for text in value.split("\n")
                    ]
                }
                params["orderText"].append(order_text)


def make_order_text_mapping(order_texts):
    mapping_code_order = {
        '000000': {
            "Z001": "internal_comments_to_warehouse",
            "Z002": "internal_comments_to_logistic",
            "Z067": "external_comments_to_customer",
            "ZK08": "product_information",
            "Z014": "port_of_loading",
            "Z004": "shipping_mark",
            "Z019": "uom",
            "Z013": "port_of_discharge",
            "Z022": "no_of_containers",
            "ZK35": "gw_uom",
            "Z012": "payment_instruction",
            "Z016": "remark",
            "Z008": "surname",
            "Z038": "etd",
            "Z066": "eta",
            "Z223": "dlc_expiry_date",
            "Z222": "dlc_no",
            "Z224": "dlc_latest_delivery_date",
        }
    }
    mapping_code_order_line = {
        "Z001": "internal_comments_to_warehouse",
        "Z002": "external_comments_to_customer",
        "Z004": "shipping_mark",
    }
    result = {}
    for order_text in order_texts:
        if order_text.get("textId") in mapping_code_order["000000"]:
            item_no = order_text.get("ItemNo")
            if item_no not in result:
                result[item_no] = {}
            label = mapping_code_order.get(item_no, mapping_code_order_line).get(order_text.get("textId"))
            language = order_text.get("language", "")
            if label not in result[item_no]:
                result[item_no][label] = (
                    join_order_text_line(order_text.get("textLine", ""))
                )
            if language == "EN":
                result[item_no][label] = (
                    join_order_text_line(order_text.get("textLine", ""))
                )
    return result


def join_order_text_line(texts_line):
    rs = ""
    for text_line in texts_line:
        rs += text_line["text"] + '\n'
    return rs[:-1]


def split_text_lines(texts_line):
    if not texts_line:
        return [""]
    return texts_line.split('\n')


def add_param_to_i_plan_rollback(change_order_mapping, params, item_error=[]):
    for item_no, order_line_input in change_order_mapping["yt65156"].items():
        if item_no not in item_error:
            confirm_line = {
                "lineNumber": item_no,
                "originalLineNumber": item_no,
                "status": "ROLLBACK",
                "DDQOrderInformationType": []
            }
            params["DDQConfirm"]["DDQConfirmHeader"][0]["DDQConfirmLine"].append(confirm_line)


def add_cancel_item_to_es_21(change_order_mapping, params):
    for item_no, order_line_input in change_order_mapping["order_lines_cancel"].items():
        order_items_in = {
            "itemNo": item_no,
            "material": order_line_input["order_information"]["material_code"],
            "targetQty": order_line_input["order_information"]["quantity"],
            "salesUnit": order_line_input["order_information"]["unit"],
            "reasonReject": "93",
            "refDoc": change_order_mapping["order_in_database"].so_no,
            "refDocIt": item_no
        }
        order_items_inx = {
            "itemNo": item_no,
            "updateflag": "U",
            "reasonReject": True
        }
        if order_line_input["cancel_item"] == "Delete":
            order_items_in.pop("reasonReject")
            order_items_inx["updateflag"] = "D"
        params["orderItemsIn"].append(order_items_in)
        params["orderItemsInx"].append(order_items_inx)


def add_param_to_i_plan_confirm(change_order_mapping, params):
    for item_no, order_line_input in change_order_mapping["responseIPlan"].items():
        if item_no in change_order_mapping["yt65217"]:
            continue
        item_no_rjust = item_no.rjust(6, "0")
        on_hand_quantity_confirmed = "0" if not change_order_mapping["responseIPlan"][item_no][
            "onHandStock"] else str(change_order_mapping["responseES21"][item_no_rjust]["confirmQuantity"])
        confirm_line = {
            "lineNumber": item_no,
            "originalLineNumber": change_order_mapping["responseIPlan"][item_no]["lineNumber"],
            "onHandQuantityConfirmed": on_hand_quantity_confirmed,
            "unit": "ROL",
            "status": "COMMIT",
            "DDQOrderInformationType": []
        }
        params["DDQConfirm"]["DDQConfirmHeader"][0]["DDQConfirmLine"].append(confirm_line)


def add_param_iplan_65217(change_order_mapping, params):
    for item_no, order_line_input in change_order_mapping["yt65217"].items():
        request_date = "-".join(order_line_input["order_information"]["request_date"].split("/")[::-1])
        update_line = {
            "orderNumber": change_order_mapping["order_input"]["fixed_data"]["so_no"].lstrip("0"),
            "lineCode": item_no,
            "requestDate": f'{request_date}T00:00:00.000Z',
            "quantity": order_line_input["order_information"]["quantity"],
            "unit": order_line_input["order_information"]["unit"],
            "deliveryDate": change_order_mapping["order_lines_in_database"][item_no].confirmed_date and
                            change_order_mapping["order_lines_in_database"][item_no].confirmed_date.strftime(
                                '%Y-%m-%dT%H:%M:%SZ') or f'{request_date}T00:00:00.000Z'
        }
        params["OrderUpdateRequest"]["OrderUpdateRequestLine"].append(update_line)


def check_order_line_need_update_status(order_lines_update, order_so_no):
    pass


def handle_quantity_order_schedule_without_plan(change_order_mapping, order_schedules_in, order_schedules_inx, item_no):
    quantity = round_qty_decimal(
        change_order_mapping["order_lines_input"].get(item_no, {})["order_information"].get("quantity", None))
    order_schedules_in[Es21Params.ORDER_SCHEDULE.value.get("quantity")] = quantity
    order_schedules_inx[Es21Params.ORDER_SCHEDULE_INX.value.get("quantity")] = True

    order_schedules_in["confirmQty"] = quantity
    order_schedules_inx["confirmQuantity"] = True


def resolve_order_line_confirm_qty_after_i_plan_call(order_line_qty, order_schedules_in, order_schedules_inx,
                                                     on_hand_stock=None):
    """
       if we call YT-65217 then on_hand_stock is None
       else, on_hand_stock is boolean (i.e., either True or False)
    """
    if on_hand_stock is None:
        return
    if on_hand_stock is False:
        order_schedules_in["confirmQty"] = 0
    else:
        order_schedules_in["confirmQty"] = round_qty_decimal(order_line_qty)
    order_schedules_inx["confirmQuantity"] = True


def handle_confirm_quantity_order_schedule(change_order_mapping, item_no, order_schedules_in, order_schedules_inx):
    response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
    order_line_qty = response_i_plan.get("quantity", None) or \
                     change_order_mapping["order_lines_input"].get(item_no, {})["order_information"].get("quantity",
                                                                                                         None)
    resolve_order_line_confirm_qty_after_i_plan_call(order_line_qty, order_schedules_in, order_schedules_inx,
                                                     response_i_plan.get("onHandStock"))


def handle_new_confirm_quantity_order_schedule(change_order_mapping, item_no, order_schedules_in, order_schedules_inx):
    response_i_plan = change_order_mapping["responseIPlan"].get(item_no, {})
    order_line_qty = response_i_plan.get("quantity", None) or \
                     change_order_mapping["order_lines_new"].get(item_no, {})["order_information"].get("quantity",
                                                                                                       None)
    resolve_order_line_confirm_qty_after_i_plan_call(order_line_qty, order_schedules_in, order_schedules_inx,
                                                     response_i_plan.get("onHandStock"))


def handle_new_delivery_block_order_schedule(change_order_mapping, item_no, order_schedules_inx):
    response_i_plan = change_order_mapping["responseIPlan"][item_no]
    if response_i_plan.get("dispatchDate") != deepget(change_order_mapping["order_lines_new"].get(item_no),
                                                      ItemDetailsEdit.NEW_ITEMS.value["request_date"], ""):
        order_schedules_inx["deliveryBlock"] = True


def call_i_plan_request_get_response(manager, params, order=None):
    log_val = {
        "orderid": order and order.id or None,
        "order_number": order and order.so_no or None,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value, **log_val).request_mulesoft_post(
        IPlanEndpoint.REQUEST_URL.value,
        params
    )


def call_iplan_65217(manager, params, order=None):
    log_val = {
        "orderid": order and order.id or None,
        "order_number": order and order.so_no or None,
        "feature": MulesoftFeatureType.CHANGE_ORDER.value,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value, **log_val).request_mulesoft_post(
        IPlanEndpoint.I_PLAN_UPDATE_ORDER.value,
        params
    )


def call_es21_get_response(manager, params, order=None):
    so_no = params.get("salesdocumentin")
    log_val = {
        "orderid": order and order.id or None,
        "order_number": so_no or (order and order.so_no or None),
        "feature": MulesoftFeatureType.CHANGE_ORDER.value,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params
    )


def call_i_plan_rollback_get_response(manager, params):
    so_no = get_data_path(params, "orderHeaderIn.refDoc")
    log_val = {
        "order_number": so_no,
        "feature": MulesoftFeatureType.CHANGE_ORDER.value,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params
    )


def call_i_plan_confirm(manager, params, order=None):
    log_val = {
        "order_number": order and order.so_no or None,
        "orderid": order and order.id or None,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value, **log_val).request_mulesoft_post(
        IPlanEndpoint.IPLAN_CONFIRM_URL.value,
        params,
        encode=True
    )


def get_iplan_error_messages(iplan_response):
    is_iplan_full_success = True
    i_plan_error_messages = []

    response_lines = []
    if iplan_response.get("DDQResponse"):
        # case iplan request
        response_lines = iplan_response.get("DDQResponse").get("DDQResponseHeader")[0].get("DDQResponseLine")
    elif iplan_response.get("DDQAcknowledge"):
        # case iplan confirm
        response_lines = iplan_response.get("DDQAcknowledge").get("DDQAcknowledgeHeader")[0].get("DDQAcknowledgeLine")
    else:
        return False, []

    for line in response_lines:
        if line.get("returnStatus").lower() == IPlanAcknowledge.FAILURE.value.lower():
            # is_iplan_full_success = False
            return_code = line.get("returnCode")
            i_plan_error_messages.append({
                "item_no": line.get("lineNumber", "").lstrip("0"),
                "first_code": return_code and return_code[18:24] or "0",
                "second_code": return_code and return_code[24:32] or "0",
                "message": line.get("returnCodeDescription"),
            })

    return is_iplan_full_success, i_plan_error_messages


def make_order_header_text_mapping(order_texts):
    # Add items which comes here as 000000
    mapping_code_0 = {
        "Z001": "internal_comments_to_warehouse",
        "Z002": "internal_comments_to_logistic",
        "Z067": "external_comments_to_customer",
        "ZK08": "production_information",

    }
    # Add items which comes here as 000010
    mapping_code_10 = {
        "Z004": "remark"
    }
    result = {}
    extract_header_text(mapping_code_10, order_texts, result, '000010')
    extract_header_text(mapping_code_0, order_texts, result, '000000')
    return result


def extract_header_text(mapping_code, order_texts, result, itemNo):
    for key, value in mapping_code.items():
        order_text_data = sorted(
            list(filter(
                lambda order_text: order_text['textId'] == key and order_text.get('itemNo') == itemNo,
                order_texts
            )),
            key=lambda d: d.get('lang', "")
        )
        order_text_obj = next(iter(order_text_data), {})
        order_text_list = order_text_obj.get('headerTextList', [])
        result[value] = "\n".join((x.get('headerText') for x in order_text_list)) or None
        result[value + '_lang'] = order_text_obj.get('lang', None)


def extract_item_text_data_sap_es14(mapping_code, order_texts, result, item_no):
    for key, value in mapping_code.items():
        order_text_data = sorted(
            list(filter(
                lambda order_text: order_text['textId'] == key and order_text.get('itemNo') == item_no,
                order_texts
            )),
            key=lambda d: d.get('lang', "")
        )
        order_text_obj = next(iter(order_text_data), {})
        order_text_list = order_text_obj.get('headerTextList', [])
        result[value] = "\n".join((x.get('headerText') for x in order_text_list)) or None


def call_i_plan_confirm_get_response(manager, params, order=None):
    log_val = {
        "order_number": order and order.so_no or None,
        "orderid": order and order.id or None,
    }
    return MulesoftApiRequest.instance(service_type=MulesoftServiceType.IPLAN.value, **log_val).request_mulesoft_post(
        IPlanEndpoint.IPLAN_CONFIRM_URL.value,
        params
    )


def remapping_i_plan_request(i_plan_request_response):
    result = {"failure": [],
              "header_code": i_plan_request_response["DDQResponse"]["DDQResponseHeader"][0]["headerCode"]}
    for response_line in i_plan_request_response["DDQResponse"]["DDQResponseHeader"][0]["DDQResponseLine"]:
        result[response_line["lineNumber"]] = response_line
    return result


def update_order_price_details_post_es21(order, response_es21):
    order_header_out = response_es21.get("orderHeaderOut", {})
    if order_header_out:
        order.total_price = order_header_out.get("orderAmtBeforeVat", order.total_price)
        order.total_price_inc_tax = order_header_out.get("orderAmtAfterVat", order.total_price_inc_tax)
        order.tax_amount = order_header_out.get("orderAmtVat", order.tax_amount)
        order.save()
    return order


def save_i_plan_request_response_to_db(i_plan_request_response_origin, list_new_items, response_es21):
    iplan_lines_db_update = []
    order_lines_db_update = []
    order_schedules_out_dict = {}
    list_update_iplan = [
        "block",
        "run",
        "iplant_confirm_quantity",
        "item_status",
        "order_type",
        "iplant_confirm_date",
        "paper_machine",
        "plant",
        "on_hand_stock",
        "item_no",
        "atp_ctp",
        "atp_ctp_detail"
    ]
    order_schedules_out_list = response_es21["orderSchedulesOut"]
    for order_schedules_out in order_schedules_out_list:
        order_schedules_out_dict[order_schedules_out["itemNo"].lstrip("0")] = order_schedules_out
    i_plan_request_response = deepcopy(i_plan_request_response_origin)
    i_plan_request_response.pop("failure")
    so_no = i_plan_request_response.pop("header_code").zfill(10)
    list_item_no_split = [key.split('.')[0] for key in i_plan_request_response.keys()]
    lines_db_id = sap_migration.models.OrderLines.all_objects.filter(order__so_no=so_no,
                                                                     item_no__in=list_item_no_split).distinct("item_no")
    for line in lines_db_id:
        line.draft = False
    sap_migration.models.OrderLines.all_objects.bulk_update(lines_db_id, ["draft"])

    lines_db = sap_migration.models.OrderLines.all_objects.filter(order__so_no=so_no,
                                                                  item_no__in=list_item_no_split).distinct(
        "item_no").in_bulk(
        field_name="item_no")
    item_no_to_line_input = {item["item_no"]: item for item in list_new_items}
    for key, value in i_plan_request_response.items():
        item_no = key.split('.')[0]
        if item_no not in lines_db:
            logging.error(f"Key '{item_no}' not found in lines_db. Skipping further processing.")
            continue
        order_line = lines_db[item_no]
        item_status = i_plan_request_response[key]["status"]
        confirm_quantity = order_schedules_out_dict.get(item_no, {}).get("confirmQuantity", 0)

        line_input = item_no_to_line_input[key.split('.')[0]]
        confirm_date_str = i_plan_request_response[key]["dispatchDate"]
        if not confirm_date_str:
            request_date_str = line_input["order_information"]["request_date"]
            request_date_str = datetime.strptime(request_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            confirm_date_str = mock_confirm_date(request_date_str, item_status)

        iplan = order_line.iplan

        if response_operation := i_plan_request_response[key]["DDQResponseOperation"] or {}:
            response_operation = response_operation[0]
        i_plan_on_hand_stock = i_plan_request_response[key]["onHandStock"]
        assigned_quantity = 0
        if i_plan_on_hand_stock:
            assigned_quantity = confirm_quantity
        order_line.original_request_date = "-".join(item_no_to_line_input[order_line.item_no][
                                                        'order_information']["request_date"].split("/")[::-1])
        order_line.assigned_quantity = assigned_quantity
        order_line.confirmed_date = confirm_date_str
        order_line.request_date = confirm_date_str
        order_line.plant = i_plan_request_response[key]["warehouseCode"]
        order_line.quantity = i_plan_request_response[key]["quantity"]
        iplan.block = response_operation.get("blockCode")
        iplan.run = response_operation.get("runCode")
        iplan.iplant_confirm_quantity = i_plan_request_response[key]["quantity"]
        iplan.item_status = item_status
        iplan.order_type = i_plan_request_response[key]["orderType"]
        iplan.atp_ctp = i_plan_request_response[key]["orderType"].split(" ")[0]
        iplan.atp_ctp_detail = i_plan_request_response[key]["orderType"]
        iplan.iplant_confirm_date = confirm_date_str
        iplan.paper_machine = response_operation.get("workCentreCode")
        iplan.plant = i_plan_request_response[key]["warehouseCode"]
        iplan.on_hand_stock = i_plan_request_response[key]["onHandStock"]
        iplan.item_no = i_plan_request_response[key]["lineNumber"]
        iplan_lines_db_update.append(iplan)
        order_lines_db_update.append(order_line)

    sap_migration.models.OrderLineIPlan.objects.bulk_update(iplan_lines_db_update, list_update_iplan)
    sap_migration.models.OrderLines.objects.bulk_update(
        order_lines_db_update,
        [
            "confirmed_date",
            "assigned_quantity",
            "original_request_date",
            "request_date",
            "plant",
            "quantity"
        ])
    order = sap_migration_models.Order.objects.filter(so_no=so_no).first()
    order = update_order_price_details_post_es21(order, response_es21)
    order_lines = sap_migration_models.OrderLines.all_objects.filter(
        order__so_no=so_no,
        item_no__in=[item.get("item_no") for item in list_new_items]
    )
    update_order_lines_item_status_en_and_item_status_th(
        order,
        order_lines,
        IPlanOrderItemStatus.ITEM_CREATED.value,
        IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            IPlanOrderItemStatus.ITEM_CREATED.value
        ),
    )
    return 1


def remapping_es21(response_es21):
    return {
        order_line["itemNo"].lstrip("0"): order_line for order_line in response_es21["orderSchedulesOut"]
    }


def get_order_id_and_so_no_of_order(id):
    order = sap_migration_models.Order.objects.filter(id=id).first()
    if order:
        return id, order.so_no
    order = sap_migration_models.Order.objects.filter(so_no=id).first()
    return order.id, id


def update_plant_for_container_line_input(lines: list, eo_no):
    order_lines = sap_migration_models.OrderLines.objects.filter(
        Q(Q(order__eo_no=eo_no) | Q(order__so_no=eo_no)) & ~Q(item_category=ItemCat.ZKC0.value)).order_by(
        'item_no').first()
    if order_lines:
        for line in lines:
            if line["item_cat_eo"] == ItemCat.ZKC0.value:
                line["plant"] = order_lines.plant
    return lines


def recheck_param_inx(param_in, param_inx):
    for key, value in param_in.items():
        if value not in [""] and key not in ("itemNo", "", "overdlvtol", "unlimitTol", "unddlvTol"):
            if not value or value == "":
                param_inx.pop(key, None)


def update_order_line_when_call_es21_success(need_iplan_integration, data_input, new_items, order_items_out=None):
    so_no = data_input["input"]["order_headers"]["so_no"]
    order_lines = sap_migration_models.OrderLines.all_objects.filter(
        order__so_no=so_no,
        item_no__in=[item.get("item_no") for item in new_items]
    )
    mapping_item_no_with_order_lines_input = {
        order_line.get("item_no"): order_line
        for order_line in new_items
    }
    # Create a dictionary to store the fields to update for each item_no
    fields_to_update_dict = {}
    if order_items_out:
        for item in order_items_out:
            item_no = item["itemNo"].lstrip("0")
            order_line = order_lines.filter(item_no=item_no)
            if order_line:
                fields_to_update = {
                    'weight_unit_ton': item.get("weightUnitTon"),
                    'weight_unit': item.get("weightUnit"),
                    'net_weight_ton': item.get("netWeightTon"),
                    'gross_weight_ton': item.get("grossWeightTon")
                }

                # Bulk update the fields for the order_line object
                fields_to_update_dict[item_no] = fields_to_update
    for order_line in order_lines:
        iplan = order_line.iplan
        order_line.draft = False
        order_line.shipping_mark = deepget(
            mapping_item_no_with_order_lines_input.get(order_line.item_no, {}),
            "additional_data.shipping_mark")
        if not need_iplan_integration:
            request_date = datetime.strptime(deepget(
                mapping_item_no_with_order_lines_input.get(order_line.item_no, {}),
                "order_information.request_date"), "%d/%m/%Y")
            order_line.confirmed_date = request_date
            order_line.request_date = request_date
            order_line.original_request_date = request_date
            order_line.plant = deepget(
                mapping_item_no_with_order_lines_input.get(order_line.item_no, {}),
                "order_information.plant")
        else:
            order_line.confirmed_date = iplan.iplant_confirm_date
            order_line.plant = iplan.plant

        order_line.return_status = iplan.item_status

        order_line.weight_display = deepget(
            mapping_item_no_with_order_lines_input.get(order_line.item_no, {}),
            "order_information.weight_unit",
            "TON"
        )
        order_line.i_plan_on_hand_stock = iplan.on_hand_stock  # this one used in SEO-1181
        order_line.i_plan_operations = {"blockCode": iplan.block}  # this one used in SEO-1181
        fields_to_update = fields_to_update_dict.get(order_line.item_no, {})
        order_line.weight_unit_ton = fields_to_update.get('weight_unit_ton')
        order_line.weight_unit = fields_to_update.get('weight_unit')
        order_line.net_weight_ton = fields_to_update.get('net_weight_ton')
        order_line.gross_weight_ton = fields_to_update.get('gross_weight_ton')
        if is_order_contract_project_name_special(order_line.order):
            order_line.remark = update_remark_order_line(order_line.remark, "C1")
    fields = [
        "confirmed_date",
        "return_status",
        "plant",
        "weight_display",
        "i_plan_on_hand_stock",
        "i_plan_operations",
        "shipping_mark",
        "draft",
        "shipping_mark",
        "weight_unit_ton",
        "weight_unit",
        "net_weight_ton",
        "gross_weight_ton"
    ]

    if not need_iplan_integration:
        fields.extend(["request_date", "original_request_date"])
    sap_migration_models.OrderLines.all_objects.bulk_update(order_lines, fields=fields)


def update_order_when_call_es21_success(order, order_header_out):
    if order_header_out and order:
        order.total_price = order_header_out.get("orderAmtBeforeVat", order.total_price)
        order.total_price_inc_tax = order_header_out.get("orderAmtAfterVat", order.total_price_inc_tax)
        order.tax_amount = order_header_out.get("orderAmtVat", order.tax_amount)
        order.save()


def _handle_item_status_trigger_from_i_plan(order_line):
    if order_line.iplan.order_type == AtpCtpStatus.ATP_ON_HAND.value:
        order_line.item_status_en = IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value
        order_line.item_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value)
    if order_line.iplan.order_type == AtpCtpStatus.ATP_FUTURE.value:
        order_line.item_status_en = IPlanOrderItemStatus.PLANNING_OUTSOURCING.value
        order_line.item_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            IPlanOrderItemStatus.PLANNING_OUTSOURCING.value)


def _update_status_for_order(order, order_lines):
    is_lines_full_committed = all(
        line.item_status_en == IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value for line in order_lines)
    is_lines_planning_outsourcing = all(
        line.item_status_en == IPlanOrderItemStatus.PLANNING_OUTSOURCING.value for line in order_lines)
    if is_lines_full_committed:
        order.status = IPlanOrderStatus.READY_FOR_DELIVERY.value
        order.save()
    if is_lines_planning_outsourcing:
        order.status = IPlanOrderStatus.PARTIAL_COMMITTED_ORDER.value
        order.save()


def save_i_plan_request_response_to_db_for_update_case(i_plan_request, change_order_mapping):
    iplan_lines_db_update = []
    order_lines_db_update = []
    list_update_iplan = [
        "block",
        "run",
        "iplant_confirm_quantity",
        "item_status",
        "order_type",
        "iplant_confirm_date",
        "paper_machine",
        "plant",
        "on_hand_stock",
        "item_no",
        "atp_ctp",
        "atp_ctp_detail",
        "request_type"
    ]
    i_plan_request_response = deepcopy(i_plan_request)
    i_plan_request_response.pop("failure")
    so_no = i_plan_request_response.pop("header_code").zfill(10)
    list_item_no = [key for key in change_order_mapping["responseIPlan"].keys()]
    lines_db_id = sap_migration.models.OrderLines.all_objects.filter(order__so_no=so_no,
                                                                     item_no__in=list_item_no).distinct("item_no")
    for line in lines_db_id:
        line.draft = False
    sap_migration.models.OrderLines.all_objects.bulk_update(lines_db_id, ["draft"])

    lines_db = sap_migration.models.OrderLines.all_objects.filter(order__so_no=so_no,
                                                                  item_no__in=list_item_no).distinct("item_no").in_bulk(
        field_name="item_no")
    for key, value in change_order_mapping["responseIPlan"].items():
        if key in change_order_mapping["yt65217"]:
            continue
        if key not in lines_db:
            logging.error(f"Key '{key}' not found in lines_db. Skipping further processing.")
            continue
        order_line = lines_db[key]
        line_number = value["lineNumber"]
        order_type = i_plan_request_response[line_number]["orderType"]
        if AtpCtpStatus.ATP_ON_HAND.value == order_type:
            order_line.item_status_en = EorderingItemStatusEN.FULL_COMMITTED_ORDER.value
            order_line.item_status_th = EorderingItemStatusTH.FULL_COMMITTED_ORDER.value
        if AtpCtpStatus.ATP_FUTURE.value == order_type:
            order_line.item_status_en = EorderingItemStatusEN.PLANNING_OUTSOURCING.value
            order_line.item_status_th = EorderingItemStatusTH.PLANNING_OUTSOURCING.value
        if order_type == AtpCtpStatus.CTP.value:
            order_line.item_status_en = EorderingItemStatusEN.ITEM_CREATED.value
            order_line.item_status_th = EorderingItemStatusTH.ITEM_CREATED.value

        item_status = i_plan_request_response[line_number]["status"]

        confirm_date_str = i_plan_request_response[line_number].get("dispatchDate", None)
        iplan = order_line.iplan

        if response_operation := i_plan_request_response[line_number]["DDQResponseOperation"] or {}:
            response_operation = response_operation[0]
        i_plan_on_hand_stock = i_plan_request_response[line_number]["onHandStock"]
        assigned_quantity = 0
        if i_plan_on_hand_stock and i_plan_request_response[line_number]["orderType"] != AtpCtpStatus.CTP.value:
            assigned_quantity = i_plan_request_response[line_number].get("quantity", 0)
        logging.info(
            f"[Domestic change order] item {line_number} DB assigned_quantity : {order_line.assigned_quantity} "
            f"updated to {assigned_quantity}")
        order_line.assigned_quantity = assigned_quantity
        '''
             SEO-5403: For Order line Item's in UNPLANNED or TENTATIVE reqDate is sent to SAP with mock confirm date. Hence instead of mocking again at the time of persisting using the request date if confirm date in IPLAN is None
         '''
        request_date = change_order_mapping["order_lines_input"].get(key, {}).get("order_information", {}).get(
            'request_date', None)
        confirmed_date = confirm_date_str or mock_confirm_date(request_date, item_status)
        logging.info(f"[Domestic change order] item {line_number} DB confirmed_date : {order_line.confirmed_date} "
                     f"updated to {confirmed_date}")
        order_line.confirmed_date = confirmed_date
        iplan.block = response_operation.get("blockCode", "")
        iplan.run = response_operation.get("runCode", "")
        iplan.iplant_confirm_quantity = i_plan_request_response[line_number]["quantity"]
        iplan.item_status = item_status
        iplan.order_type = i_plan_request_response[line_number]["orderType"]
        iplan.atp_ctp = i_plan_request_response[line_number]["orderType"].split(" ")[0]
        iplan.atp_ctp_detail = i_plan_request_response[line_number]["orderType"]
        iplan.iplant_confirm_date = confirm_date_str
        iplan.paper_machine = response_operation.get("workCentreCode", "")
        iplan.plant = i_plan_request_response[line_number]["warehouseCode"]
        iplan.on_hand_stock = i_plan_request_response[line_number]["onHandStock"]
        iplan.item_no = i_plan_request_response[line_number]["lineNumber"]
        iplan.request_type = "AMENDMENT"
        iplan_lines_db_update.append(iplan)
        order_lines_db_update.append(order_line)

    sap_migration.models.OrderLineIPlan.objects.bulk_update(iplan_lines_db_update, list_update_iplan)
    sap_migration.models.OrderLines.objects.bulk_update(order_lines_db_update,
                                                        ["confirmed_date", "assigned_quantity", "item_status_en",
                                                         "item_status_th"])
    return 1


def get_item_no_max_order_line(order_id):
    return (
        sap_migration_models.OrderLines.objects.filter(order_id=order_id)
        .annotate(item_no_int=Cast('item_no', output_field=IntegerField()))
        .aggregate(Max('item_no_int')).get("item_no_int__max", 0)
    )


def call_rollback_change_order(change_order_mapping, param_es_i_plan_rollback, manager, message_error_es21,
                               flag_es21=True, exception=False, item_error=[], order=None):
    add_param_to_i_plan_rollback(change_order_mapping, param_es_i_plan_rollback, item_error)
    # Skip calling /confirm (rollback) when all items failed from iplan
    if param_es_i_plan_rollback["DDQConfirm"]["DDQConfirmHeader"][0]["DDQConfirmLine"]:
        call_i_plan_confirm_get_response(manager, param_es_i_plan_rollback, order=order)
    if exception:
        raise ValidationError(
            {
                "sap": ValidationError(
                    message=message_error_es21,
                    code=ContractCheckoutErrorCode.INVALID,
                )
            }
        )


def get_warehouse_code_from_iplan_request(response_i_plan, item_no):
    for key, val in response_i_plan.items():
        if item_no in key:
            return val["warehouseCode"]
    return ""


def update_order_information(mapping_item_no_input, item_no, response_line):
    new_quantity = str(response_line["quantity"])
    new_product_code = response_line.get("productCode")
    mapping_item_no_input[item_no]['order_information'].quantity = new_quantity
    mapping_item_no_input[item_no]["order_information"].material_code = new_product_code
    # to update JSON
    mapping_item_no_input[item_no]['order_information']["quantity"] = new_quantity
    mapping_item_no_input[item_no]["order_information"]["material_code"] = new_product_code


def process_original_item_no_not_in_result(e_ordering_order_lines, mapping_item_no_input, mapping_item_no_order_lines,
                                           new_product_code, new_quantity, original_item_no, response_line, result):
    result[original_item_no] = response_line
    e_ordering_order_line = mapping_item_no_order_lines[original_item_no]
    e_ordering_order_line.material_code = new_product_code
    e_ordering_order_line.quantity = new_quantity
    e_ordering_order_lines.append(e_ordering_order_line)
    update_order_information(mapping_item_no_input, original_item_no, response_line)


def process_original_item_no_in_result(list_new_items, mapping_item_no_input, mapping_item_no_order_lines, max_item_no,
                                       new_order_lines, new_product_code, new_quantity, original_item_no, response_line,
                                       result):
    max_item_no += 10
    result[str(max_item_no)] = response_line
    new_order_line = create_new_order_line_in_database(original_item_no, result["header_code"], max_item_no)
    new_order_line_input = deepcopy(mapping_item_no_input[original_item_no])
    new_order_line_input['order_information'].quantity = new_quantity
    mapping_item_no_input[str(max_item_no)] = new_order_line_input
    order_line_split_input = deepcopy(mapping_item_no_input[original_item_no])
    order_line_split_input['item_no'] = str(max_item_no)
    order_line_split_input['order_information'].quantity = new_quantity
    order_line_split_input["order_information"].material_code = new_product_code
    # to update JSON
    order_line_split_input['order_information']["quantity"] = new_quantity
    order_line_split_input["order_information"]["material_code"] = new_product_code
    mapping_item_no_input[str(max_item_no)] = order_line_split_input
    list_new_items.append(order_line_split_input)
    # required for ALT MAT FEATURE
    new_order_line.item_no = str(max_item_no)
    new_order_line.original_item_no = original_item_no
    new_order_line.material_code = new_product_code
    new_order_line.quantity = new_quantity
    new_order_lines.append(new_order_line)
    return max_item_no


def update_list_new_items_input_data(list_new_items, mapping_item_no_input, e_ordering_order_lines, new_order_lines):
    lines = e_ordering_order_lines + new_order_lines
    for order_line_input in list_new_items:
        item_no = order_line_input["item_no"]
        for line in lines:
            if line.item_no == item_no:
                order_line_input["order_information"].ref_doc_it = line.ref_doc_it
                mapping_item_no_input[item_no]['ref_doc_it'] = line.ref_doc_it
                break
        order_line_input["order_information"].material_code = \
            mapping_item_no_input[item_no]['order_information'].material_code
        order_line_input['order_information'].quantity = float(
            mapping_item_no_input[item_no]['order_information'].quantity)
        order_line_input["order_information"]["material_code"] = \
            mapping_item_no_input[item_no]['order_information']["material_code"]
        order_line_input['order_information']["quantity"] = float(
            mapping_item_no_input[item_no]['order_information']["quantity"]
        )


def handle_case_iplan_return_split_order(iplan_request_response, list_new_items, qs_new_order_lines, order=None,
                                         alt_mat_i_plan_dict=None, alt_mat_variant_obj_dict=None):
    mapping_item_no_order_lines = {
        qs_order_line_new.item_no: qs_order_line_new
        for qs_order_line_new in qs_new_order_lines
    }

    mapping_item_no_input = {
        order_line_input['item_no']: order_line_input
        for order_line_input in list_new_items
    }
    new_order_lines = []
    e_ordering_order_lines = []
    max_item_no = 0
    result = {
        "failure": [],
        "header_code": iplan_request_response["DDQResponse"]["DDQResponseHeader"][0]["headerCode"]
    }
    iplan_request_response_line = sorted(
        iplan_request_response["DDQResponse"]["DDQResponseHeader"][0]["DDQResponseLine"], key=lambda x: x["lineNumber"])
    for response_line in iplan_request_response_line:
        max_item_no = max(int(response_line["lineNumber"].split('.')[0]), max_item_no)

    for response_line in iplan_request_response_line:
        original_item_no = response_line["lineNumber"].split('.')[0]
        new_quantity = str(response_line["quantity"])
        new_product_code = response_line.get("productCode")
        key = f"{order.id}_{original_item_no}"
        update_mat_own(response_line, key, alt_mat_i_plan_dict)
        if original_item_no not in result:
            process_original_item_no_not_in_result(e_ordering_order_lines, mapping_item_no_input,
                                                   mapping_item_no_order_lines, new_product_code, new_quantity,
                                                   original_item_no, response_line, result)
        else:
            max_item_no = process_original_item_no_in_result(list_new_items, mapping_item_no_input,
                                                             mapping_item_no_order_lines,
                                                             max_item_no, new_order_lines, new_product_code,
                                                             new_quantity,
                                                             original_item_no, response_line, result)

    alt_mat_log_changes = []
    derive_and_compute_alt_mat_info(e_ordering_order_lines, alt_mat_variant_obj_dict, alt_mat_i_plan_dict,
                                    alt_mat_log_changes)
    if new_order_lines:
        derive_and_compute_alt_mat_info(new_order_lines, alt_mat_variant_obj_dict, alt_mat_i_plan_dict,
                                        alt_mat_log_changes, True)
    # update list_new_items input data
    update_list_new_items_input_data(list_new_items, mapping_item_no_input, e_ordering_order_lines, new_order_lines)
    return result, e_ordering_order_lines, new_order_lines, alt_mat_log_changes


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
    return sap_migration_models.OrderLines.all_objects.filter(item_no=new_item_no,
                                                              order__so_no=so_no.zfill(10)).first()


def get_list_status_from_es25_data_item(data_item):
    # https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/625181706/Inquiry+-+Order+Confirmation+Display+Item+Status+Logic
    reason_reject = data_item.get("reasonReject")
    list_status = []
    if reason_reject == 93:
        list_status.append(SapOrderConfirmationStatusParam.REJECT)
    else:
        if round(data_item.get("confirmQty", -1)) > 0:
            list_status.append(SapOrderConfirmationStatusParam.CONFIRM)
        if round(data_item.get("nonConfirmQty", -1)) > 0 >= round(data_item.get("confirmQty", 0)):
            list_status.append(SapOrderConfirmationStatusParam.NON_CONFIRM)

    return list_status


def sort_order_confirmation_data_item_by_status(data_items):
    # https://scgdigitaloffice.atlassian.net/wiki/spaces/EO/pages/625181706/Inquiry+-+Order+Confirmation+Display+Item+Status+Logic
    priority = {
        SapOrderConfirmationStatus.READY_TO_SHIP.value: 1,
        SapOrderConfirmationStatus.QUEUE_FOR_PRODUCTION.value: 2,
        SapOrderConfirmationStatus.CANCEL.value: 3
    }
    data_items.sort(key=lambda item: priority.get(item["status"], 99))


def prepare_param_for_api_get_gps_report(data_filter, info):
    user_key = "test_gpstracking"
    if SAP_ENV == "PROD":
        user_key = "gpstracking"

    params = {
        "piMessageId": str(uuid.uuid4().int),
        "user_key": user_key,
        "source": "e-ordering",
        "GPSTracking": True,
    }
    order_tracking_input = [{
        "dp": data_filter.get("dp", ""),
        "shippingpoint": data_filter.get("shipping_point", ""),
        "soldto": data_filter.get("sold_to", ""),
    }]
    params["orderTrackingInput"] = order_tracking_input
    web_user = handle_web_user_for_api_get_lms_report(info)
    add_key_and_value_into_params_for_api_get_lms_report("webUser", web_user, params)
    return params


def query_sales_org_by_sold_to(sold_to_code):
    if sold_to_code:
        result = list(SalesOrganizationMaster.objects.filter
                      (code__in=SoldToChannelMaster.objects.filter
                      (sold_to_code=sold_to_code).values("sales_organization_code").distinct()).all())
        return result
    else:
        return list(SalesOrganizationMaster.objects.all())


def prepare_param_for_api_get_lms_report(data_filter, info):
    user_key = "test_gpstracking"
    if SAP_ENV == "PROD":
        user_key = "gpstracking"

    params = {
        "piMessageId": str(uuid.uuid4().int),
        "userKey": user_key,
        "source": "e-ordering",
        "itemFlg": "X",
        "itemDeliveryFlg": "X",
        "matGroup1": ["K01", "K09", "K02", "K04", "K06", "K10", "K11", "K12"],
    }

    sold_to_code = data_filter.get('sold_to_code', "")
    mat_no = data_filter.get('mat_no', "")
    sale_org_code = data_filter.get('sale_org_code', "")
    so_no = data_filter.get('so_no', "")
    po_no = data_filter.get('po_no', "")
    from_date = data_filter.get('delivery_date', {}).get('gte', "")
    to_date = data_filter.get('delivery_date', {}).get('lte', "")
    delivery_from = "" if from_date is None else str(from_date)
    delivery_to = "" if to_date is None else str(to_date)

    web_user = handle_web_user_for_api_get_lms_report(info)
    if len(so_no) > 10:
        raise ValidationError("The length of SO No. can't greater than 10 character!")
    if len(po_no) > 35:
        raise ValidationError("The length of PO No. can't greater than 35 character!")
    if so_no:
        so_no = so_no.zfill(10)

    add_key_and_value_into_params_for_api_get_lms_report("soldTo", sold_to_code, params)
    add_key_and_value_into_params_for_api_get_lms_report("matNo", mat_no, params)
    add_key_and_value_into_params_for_api_get_lms_report("deliveryFrom", delivery_from, params)
    add_key_and_value_into_params_for_api_get_lms_report("deliveryTo", delivery_to, params)

    if sale_org_code and sale_org_code.upper() == "ALL":
        sales_organization_master_rows = query_sales_org_by_sold_to(sold_to_code)
        sales_organization_codes = []
        for sales_organization_master_row in sales_organization_master_rows:
            sales_organization_codes.append(sales_organization_master_row.code)
        add_key_and_value_into_params_for_api_get_lms_report("saleOrg", sales_organization_codes, params)

    else:
        add_key_and_value_into_params_for_api_get_lms_report("saleOrg", sale_org_code, params)
    add_key_and_value_into_params_for_api_get_lms_report("soNo", so_no, params)
    add_key_and_value_into_params_for_api_get_lms_report("poNo", po_no, params)
    add_key_and_value_into_params_for_api_get_lms_report("webUser", web_user, params)

    return params


def add_key_and_value_into_params_for_api_get_lms_report(key, value, params):
    if not value:
        return
    params[key] = value


def from_response_get_lms_report_to_result(response):
    response = response.get("orderTrackingOutput", [])
    if not response:
        raise ValidationError("SAP does not return data")
    result = []
    for order in response:
        items = make_delivery_report_data(order)
        result.append(items)
    return result


def make_delivery_report_data(out_put):
    return {
        "dn_no": out_put.get("dnNo", ""),
        "data_item": out_put.get("dataItem", ""),
        "sold_to_code": out_put.get("soldTo", ""),
        "destination_name": out_put.get("destinationName", ""),
        "cut_off_date": out_put.get("cutOffDate", ""),
        "cut_off_time": out_put.get("cutOffTime", ""),
        "truck_no": out_put.get("truckNo", ""),
        "origin_name": out_put.get("originname", ""),
        "plan_delivery": out_put.get("plandelivery", ""),
        "status_id": out_put.get("statusId", ""),
        "box_position": out_put.get("boxposition", ""),
        "eta_distance": out_put.get("etadistance", ""),
        "estimated_time": out_put.get("estimatedtime", ""),
        "carrier_name": out_put.get("carrierName", ""),
        "box_speed": out_put.get("boxspeed", ""),
        "box_gps_time": out_put.get("boxGpsTime", ""),
        "shipment": out_put.get("shipment", ""),
        "acc_distance": out_put.get("accDistance", ""),
        "good_issue_time": out_put.get("goodIssueTime", ""),
        "destination_inbound": out_put.get("destinationInbound", ""),
        "eta": out_put.get("eta", ""),
        "eta_duration": out_put.get("etaduration", ""),
        "status": out_put.get("status", ""),
        "message": out_put.get("message", ""),
        "shipping_point": out_put.get("shippingPoint", ""),
        "return_flag": out_put.get("returnFlag", ""),
        "phone_no": out_put.get("phoneNo", ""),
        "contract_id": out_put.get("contractId", ""),
        "contract_abbr": out_put.get("contractABBR", ""),
        "gi_time": out_put.get("giTime", ""),
    }


def save_reason_for_change_request_date(order_lines, data_input):
    # order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    for item_no, line in order_lines.items():
        data = data_input.get(item_no, None)
        if data:
            flag = data["order_information"].get("reason_for_change_request_date", None)
            if ReasonForChangeRequestDateEnum.C3.value == flag:
                line.request_date_change_reason = ReasonForChangeRequestDateDescriptionEnum.C3.value
            elif ReasonForChangeRequestDateEnum.C4.value == flag:
                line.request_date_change_reason = ReasonForChangeRequestDateDescriptionEnum.C4.value
            else:
                line.request_date_change_reason = None
                line.save()
                continue
            add_class_mark_into_order_line(line, flag, "C", 1, 4)


def handle_web_user_for_api_get_lms_report(info):
    user = info.context.user
    if user and user.is_anonymous:
        return "anonymous"
    email = user.email
    if email:
        email = email.split("@")[0]
        if len(email) > 16:
            email = email[:16]
    return email


def _validate_order_status_complete_and_full_committed(count_complete, count_full_committed_order, order_line_status):
    if count_complete >= len(order_line_status):
        order_status = IPlanOrderStatus.COMPLETED_DELIVERY.value
        return (
            order_status,
            IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
        )
    if count_full_committed_order >= len(order_line_status):
        order_status = IPlanOrderStatus.FULL_COMMITTED_ORDER.value
        return (
            order_status,
            IPlanOrderStatus.IPLAN_ORDER_STATUS_TH.value.get(order_status)
        )


def is_order_contract_project_name_special(order: sap_migration.models.Order) -> bool:
    project_name = order.contract.project_name or ""
    if len(project_name) < 2:
        return False
    if project_name[0:2] in ["DS", "DG", "DW"]:
        return True

    return False


def update_remark_order_line(order_line_remark, remark):
    if not order_line_remark:
        return remark
    if remark not in order_line_remark:
        return ', '.join(map(lambda x: x.strip(), f"{order_line_remark}, {remark}".split(",")))
    return order_line_remark


def update_order_line_after_sap_es17(qs_order_lines, order):
    updated_line = []
    for order_line in qs_order_lines:
        # Update the request date and confirmed date
        compute_confirm_and_request_date(order_line, updated_line, order.type)
    if order.type == OrderType.DOMESTIC.value and not ProductGroup.is_iplan_integration_required(order):
        logging.debug(f"Skipping updates {qs_order_lines}")
    else:
        sap_migration_models.OrderLines.objects.bulk_update(
            updated_line,
            ["request_date", "confirmed_date"],
        )


def compute_confirm_and_request_date_iplan_skipped(order_line, updated_lines, order_type):
    if OrderType.DOMESTIC.value == order_type:
        updated_lines.append(order_line)


def compute_confirm_and_request_date(order_line, updated_lines, order_type):
    if order_line.item_cat_eo == ItemCat.ZKC0.value:
        updated_lines.append(order_line)
        return
    if OrderType.EXPORT.value == order_type and (order_line.plant in ["754F", "7531", "7533"]):
        order_line.confirmed_date = order_line.request_date
    else:
        order_line_obj_i_plan = order_line.iplan
        dispatch_date = (
            order_line_obj_i_plan.iplant_confirm_date
            if order_line_obj_i_plan and order_line_obj_i_plan.iplant_confirm_date
            else None
        )
        if not dispatch_date:
            dispatch_date = mock_confirm_date(
                order_line.request_date, order_line_obj_i_plan.item_status
            )
        order_line.confirmed_date = dispatch_date
        order_line.request_date = order_line.confirmed_date
    if OrderType.CUSTOMER.value == order_type and order_line.original_request_date != order_line.confirmed_date:
        order_line.class_mark = update_remark_order_line(order_line.class_mark, "C1")
    updated_lines.append(order_line)


def remove_padding_zero_from_ship_to(ship_to: str):
    ship_to_code = ship_to.split('-')[0].strip()
    flag = False
    for x in ship_to_code:
        flag = flag or (x < '0' or x > '9')
    return ship_to.lstrip('0') if flag else ship_to


def get_error_order_lines_from_iplan_response(order_lines, iplan_response):
    error_order_lines = []
    _, iplan_error_messages = get_iplan_error_messages(iplan_response)
    error_item_no = [iplan_error_message.get("item_no") for iplan_error_message in iplan_error_messages]
    for order_line in order_lines:
        if order_line.item_no in error_item_no:
            error_order_lines.append(order_line)
    return error_order_lines


def validate_item_status_scenario2_3(item_status):
    item_status_scenario_2_3 = [
        IPlanOrderItemStatus.PLANNING_CLOSE_LOOP.value,
        IPlanOrderItemStatus.PLANNING_ALLOCATED_X_TRIM.value,
        IPlanOrderItemStatus.PRODUCING.value,
        IPlanOrderItemStatus.FULL_COMMITTED_ORDER.value,
        IPlanOrderItemStatus.COMPLETED_PRODUCTION.value
    ]
    return item_status in item_status_scenario_2_3


def update_mat_own(i_plan_line, key, alt_mat_i_plan_dict):
    if alt_mat_i_plan_dict.get(key, {}).get('alt_mat_codes', []):
        value = alt_mat_i_plan_dict[key]
        if i_plan_line.get("productCode"):
            if "i_plan_product" in value:
                value["i_plan_product"].append(i_plan_line.get("productCode"))
            else:
                value["i_plan_product"] = [i_plan_line.get("productCode")]


def get_order_line_key(is_split, line):
    if is_split:
        line_id_original_item = line.original_item_no.split('.')[0]
        return f"{line.order_id}_{line_id_original_item}"
    return f"{line.order_id}_{line.item_no}"


def update_order_line_with_alt_mat_info(line, new_product, is_new_product_variant=False):
    line.material_variant_id = new_product.id
    """
    If Alt Mat is of Variant Type then Contract Material Id should be using Grade gram of it
    """
    if is_new_product_variant:
        contract_material = sap_migration_models.ContractMaterial.objects.filter(
            contract_id=line.order.contract.id, material_code=new_product.code[:10]
        ).first()
    else:
        contract_material = sap_migration_models.ContractMaterial.objects.filter(
            contract_id=line.order.contract.id, material_id=new_product.material_id
        ).first()
    line.contract_material_id = contract_material.id
    line.material_id = contract_material.material_id
    line.ref_doc_it = contract_material.item_no


def prepare_alt_mat_log(line, result, new_product=None, error_type=None):
    alternated_material_args = {
        "order_line": line,
        "order": line.order,
        "old_product": line.material_variant,
    }

    if new_product:
        alternated_material_args["new_product"] = new_product
    elif error_type:
        alternated_material_args["error_type"] = error_type

    result.append(AlternatedMaterial(**alternated_material_args))


def compute_alt_mat_info(alt_mat_i_plan_value, alt_mat_products, alt_mat_variant_obj_dict,
                         i_plan_response_products, line, result):
    """
        Iplan (YT-65156) response product is same as Mat Input then stamp error 'No Stock Alternated Material'
    """
    i_plan_product_code_line = line.material_code
    order_line_mat_input_code = alt_mat_i_plan_value.get('order_line_obj').material_variant.code
    if order_line_mat_input_code == i_plan_product_code_line:
        logging.info(f"[ALT MAT FEATURE] Order line item_no: {line.item_no} with id# {line.id} "
                     f"is created with Mat Own:{line.material_code} hence stamping error "
                     f" 'No Stock Alternated Material'")
        prepare_alt_mat_log(line, result, None, AlternatedMaterialLogChangeError.NO_STOCK_ALT_MAT.value)
    else:
        i_plan_response_product_intersection = i_plan_response_products.intersection(alt_mat_products)
        if i_plan_product_code_line in i_plan_response_product_intersection:
            new_product = alt_mat_variant_obj_dict.get(i_plan_product_code_line)
            is_new_product_variant = alt_mat_i_plan_value.get('is_es_15_required') and \
                                     new_product.code[:10] in alt_mat_i_plan_value.get('alt_grade_gram_codes')
            logging.info(f"[Alt Mat Feature] Order line item_no: {line.item_no} with id# {line.id} "
                         f" is created with Mat OS:{new_product.code} and is it of variant type:"
                         f" {is_new_product_variant} ")
            prepare_alt_mat_log(line, result, new_product)
            update_order_line_with_alt_mat_info(line, new_product, is_new_product_variant)


def derive_and_compute_alt_mat_info(order_lines, alt_mat_variant_obj_dict, alt_mat_i_plan_dict, result,
                                    is_split=False):
    for line in order_lines:
        order_line_key = get_order_line_key(is_split, line)
        alt_mat_i_plan_value = alt_mat_i_plan_dict.get(order_line_key, {})
        if not alt_mat_i_plan_value:
            continue
        i_plan_response_products = set(alt_mat_i_plan_value.get('i_plan_product', []))
        alt_mat_products = set(alt_mat_i_plan_value.get('alt_mat_codes', []))
        if not (i_plan_response_products and alt_mat_products):
            continue
        compute_alt_mat_info(alt_mat_i_plan_value, alt_mat_products, alt_mat_variant_obj_dict,
                             i_plan_response_products, line, result)


def update_mat_info_and_log_mat_os_after_sap_success(order, response_es21, alt_mat_log_changes, e_ordering_order_lines,
                                                     new_order_lines):
    sap_migration_models.OrderLines.all_objects.bulk_update(
        e_ordering_order_lines,
        fields=[
            "material_code",
            "material_id",
            "material_variant_id",
            "contract_material_id",
            "ref_doc_it",
        ],
    )
    if new_order_lines:
        sap_migration_models.OrderLines.all_objects.bulk_update(
            new_order_lines,
            fields=[
                "material_code",
                "material_id",
                "material_variant_id",
                "contract_material_id",
                "ref_doc_it",
            ],
        )
    if alt_mat_log_changes:
        log_alt_mat_errors(alt_mat_log_changes)
    update_log_mat_os_quantity_details(order, response_es21)


def update_log_mat_os_quantity_details(order, response):
    if OrderType.DOMESTIC.value == order.type or OrderType.CUSTOMER.value == order.type:
        order_items_out = response.get("orderItemsOut")
        alternated_materials = AlternatedMaterial.objects.filter(order=order, new_product__isnull=False,
                                                                 order_line__isnull=False).all()

        if alternated_materials and order_items_out:
            mapping_order_item_out = {
                order_item_out['itemNo'].lstrip("0"): order_item_out
                for order_item_out in order_items_out
            }
            material_code_to_weight = get_dict_material_code_to_weight(
                [alternated_material.new_product.code for alternated_material in alternated_materials]
            )
            for alternated_material in alternated_materials:
                order_item_out = mapping_order_item_out.get(alternated_material.order_line.item_no)
                target_qty = order_item_out.get("targetQuantity", None)
                net_weight = order_item_out.get("netWeight", None)
                # Get info from SAP response . in ES21 netWeight is not there so use conversion factor to compute
                if net_weight:
                    alternated_material.quantity_change_of_ton = net_weight
                if target_qty:
                    alternated_material.quantity_change_of_roll = target_qty
                    if not net_weight:
                        alternated_material.quantity_change_of_ton = target_qty * material_code_to_weight.get(
                            alternated_material.new_product.code)
            AlternatedMaterial.objects.bulk_update(alternated_materials,
                                                   ["quantity_change_of_roll", "quantity_change_of_ton"])


def perform_rounding_on_iplan_qty_with_decimals(i_plan_response):
    manager = get_plugins_manager()
    _plugin = manager.get_plugin("scg.settings")
    config = _plugin.config
    if not config.enable_target_qty_decimal_round_up:
        return
    if i_plan_response.get("DDQResponse"):
        i_plan_response_header = i_plan_response.get("DDQResponse").get("DDQResponseHeader")
        if len(i_plan_response_header):
            i_plan_order = i_plan_response_header[0]
            i_plan_order_lines = i_plan_order.get("DDQResponseLine")
            for i_plan_response_line in i_plan_order_lines:
                i_plan_response_line["quantity"] = round(i_plan_response_line.get("quantity"),
                                                         TARGET_QTY_DECIMAL_DIGITS_TO_ROUND_UP)


def get_summary_details_from_data(data):
    total_qty = None
    total_qty_ton = None
    sales_unit = None
    if data:
        for item in data:
            if item["qty"]:
                total_qty = (
                    float(item["qty"])
                    if total_qty is None
                    else total_qty + float(item["qty"])
                )
            if item["qty_ton"]:
                total_qty_ton = (
                    float(item["qty_ton"])
                    if total_qty_ton is None
                    else total_qty_ton + float(item["qty_ton"])
                )
            if not sales_unit:
                sales_unit = item["sales_unit"]
    if not sales_unit:
        sales_unit = "ROL"
    total_qty_ton = f"{total_qty_ton:.3f}" if total_qty_ton else ""
    total_qty = f"{total_qty:.3f}" if total_qty is not None and SalesUnitEnum.is_qty_conversion_to_decimal(
        sales_unit) \
        else int(total_qty) if total_qty is not None else ""
    return sales_unit, total_qty, total_qty_ton


def get_order_type_desc(type):
    mapping_code_with_order_type = {
        "ZBV": "ZBV (เงินสด)",
        "ZOR": "ZOR (เงินเชื่อ)"
    }
    return mapping_code_with_order_type.get(type, "")


def is_default_sale_unit_from_contract(product_group):
    if product_group in ProductGroup.get_product_group_1().value:
        return False
    return True


def is_other_product_group(product_group):
    return product_group in ProductGroup.get_product_group_2().value


def is_materials_product_group_matching(order_product_group, contract_materials, order_type):
    contract_materials_to_compare = get_non_container_materials_from_contract_materials(contract_materials) \
        if order_type == OrderType.EXPORT.value else contract_materials
    if not contract_materials_to_compare:
        return True
    product_group = order_product_group or contract_materials_to_compare[0].mat_group_1
    return all(material.mat_group_1 == product_group for material in contract_materials_to_compare)


def get_non_container_materials_from_contract_materials(contract_materials):
    if not contract_materials:
        return []
    return [material for material in contract_materials if material.mat_type != '83']


def update_order_product_group(order_id, product_group):
    sap_migration_models.Order.objects.filter(id=order_id).update(
        product_group=product_group
    )


def map_variant_data_for_alt_mat(es_15_variant_data):
    """
    Prepare dict from ES15 response with key: productCode, value: list of Variants
    grade_gram_es_15_dict = {'Z02CA-125D': ['Z02CA-125D0930117N', 'Z02CA-125D0980117N', 'Z02CA-125D1030117N',
                                        'Z02CA-125D1080117N', 'Z02CA-125D1230117N', 'Z02CA-125D1440117N',
                                        'Z02CA-125D1490117N', 'Z02CA-125D1590117N', 'Z02CA-125D1690117N',
                                        'Z02CA-125D1740117N', 'Z02CA-125D1760117N', 'Z02CA-125D1980117N']}
    """
    grade_gram_es_15_dict = {}
    for item in es_15_variant_data:
        if not grade_gram_es_15_dict.get(item.get('productCode')):
            grade_gram_es_15_dict[item.get('productCode')] = []
        grade_gram_es_15_dict[item.get('productCode')].extend(list(
            map(lambda material: material.get("matCode") if material.get("markFlagDelete") is not True else None,
                item.get('matStandard', []))))
        grade_gram_es_15_dict[item.get('productCode')].extend(list(
            map(lambda material: material.get("matCode") if material.get("markFlagDelete") is not True else None,
                item.get('matNonStandard', []))))

    return grade_gram_es_15_dict


def stamp_error_for_no_material_in_contract(alt_grade_gram_codes, alt_mat_codes, is_product_group_match,
                                            alt_mat_mappings_key_not_in_contract, key, alt_mat_errors, value):
    """
        if Material and Grade Gram alt mat mapping of Order line not found in table: Contract Material
        (as it is updated by ES-14 response) and Product group is NA
        then Stamp Error 'No Material in ref. contract'
    """
    if not alt_mat_codes and not alt_grade_gram_codes \
            and AlternatedMaterialProductGroupMatch.NA.value == is_product_group_match:
        order_line_obj = value.get("order_line_obj")
        logging.info(f"[ALT MAT FEATURE] Stamp Error 'No Material in ref. contract' on "
                     f" Order Line {order_line_obj.id} with item_no {order_line_obj.item_no}")
        alt_mat_mappings_key_not_in_contract.append(key)
        alt_mat_errors.append(AlternatedMaterial(
            order_line=order_line_obj,
            order=order_line_obj.order,
            old_product=order_line_obj.material_variant,
            error_type=AlternatedMaterialLogChangeError.NO_MATERIAL_CONTRACT.value
        ))


def stamp_error_for_product_group_mismatch(alt_grade_gram_codes, alt_mat_codes, is_product_group_match,
                                           alt_mat_mappings_key_not_in_contract,
                                           key, alt_mat_errors, value):
    """
        Material and Grade Gram alt mat mapping of Order line found in table: Contract Material
            (as it is updated by ES-14 response) but Product group is NOT_MATCHED.
            Hence, alt_grade_gram_codes, alt_mat_codes are empty.
            Stamp Error 'Alternated materials found in different product group'
    """
    if not alt_mat_codes and not alt_grade_gram_codes \
            and AlternatedMaterialProductGroupMatch.NOT_MATCHED.value == is_product_group_match:
        order_line_obj = value.get("order_line_obj")
        logging.info(f"[ALT MAT FEATURE] Stamp Error 'Alternated materials found in different product group' on "
                     f" Order Line {order_line_obj.id} with item_no {order_line_obj.item_no}")
        alt_mat_mappings_key_not_in_contract.append(key)
        alt_mat_errors.append(AlternatedMaterial(
            order_line=order_line_obj,
            order=order_line_obj.order,
            old_product=order_line_obj.material_variant,
            error_type=AlternatedMaterialLogChangeError.NOT_FOUND_SAME_PRODUCT_GROUP.value
        ))


def stamp_error_for_no_material_determination(alt_grade_gram_codes, alt_mat_mappings_key_not_in_contract, key,
                                              alt_mat_errors, value):
    """
        if Grade Gram alt mat mapping of Order line is found in table: Contract Material
        (as it is updated by ES-14 response) but not full mat codes found in ES-15 and no alt material_codes
        available for order line then Stamp Error 'Not found material determination'
    """
    if not value.get('alt_mat_codes', []) and len(alt_grade_gram_codes) > 0:
        order_line_obj = value.get("order_line_obj")
        logging.info(f"[ALT MAT FEATURE] Stamp Error 'Not found material determination' on "
                     f" Order Line {order_line_obj.id} with item_no {order_line_obj.item_no}")
        alt_mat_mappings_key_not_in_contract.append(key)
        alt_mat_errors.append(AlternatedMaterial(
            order_line=order_line_obj,
            order=order_line_obj.order,
            old_product=order_line_obj.material_variant,
            error_type=AlternatedMaterialLogChangeError.NOT_FOUND_MATERIAL_DETERMINATION.value
        ))


def stamp_error_for_not_enough_qty_in_contract(alt_mat_errors, alt_mat_mappings_key_not_in_contract, key, line, value):
    """
        if there is no enough qty for none of the alt mat mappings in contract on which order is being created
        then Stamp Error 'Not enough Remaining Qty in ref. contract'
    """
    if not value.get('alt_mat_codes', []):
        logging.info(f"[ALT MAT FEATURE] Stamp Error 'Not enough Remaining Qty in ref. contract' on "
                     f" Order Line {line.id} with item_no {line.item_no}")
        alt_mat_mappings_key_not_in_contract.append(key)
        alt_mat_errors.append(AlternatedMaterial(
            order_line=line,
            order=line.order,
            old_product=line.material_variant,
            error_type=AlternatedMaterialLogChangeError.NOT_ENOUGH_QTY_IN_CONTRACT.value
        ))


def log_alt_mat_errors(alt_mat_errors: list):
    order_lines = [alt_mat_obj.order_line for alt_mat_obj in alt_mat_errors]
    alternated_materials = AlternatedMaterial.objects.filter(order_line__in=order_lines).order_by('order_line')
    alt_mat_update, alt_mat_create = [], []
    if alternated_materials:
        existing_order_lines = [alt_mat_obj.order_line for alt_mat_obj in alternated_materials]
        for alt_error in alt_mat_errors:
            if alt_error.order_line in existing_order_lines:
                alt_mat_update.append(alt_error)
            else:
                alt_mat_create.append(alt_error)
    else:
        alt_mat_create.extend(alt_mat_errors)

    if alt_mat_update:
        AlternatedMaterial.objects.bulk_update(alt_mat_errors,
                                               fields=["order", "order_line", "old_product", "new_product",
                                                       "error_type", "quantity_change_of_roll",
                                                       "quantity_change_of_ton"])
    if alt_mat_create:
        AlternatedMaterial.objects.bulk_create(alt_mat_errors)


def get_alternated_material_errors(order):
    alt_mat_error_msgs = []
    if order.id:
        alternated_materials = AlternatedMaterial.objects.filter(
            order=order,
            error_type__in=[
                AlternatedMaterialLogChangeError.NO_MATERIAL_CONTRACT.value,
                AlternatedMaterialLogChangeError.NOT_FOUND_SAME_PRODUCT_GROUP.value,
                AlternatedMaterialLogChangeError.NOT_FOUND_MATERIAL_DETERMINATION.value,
                AlternatedMaterialLogChangeError.NOT_ENOUGH_QTY_IN_CONTRACT.value
            ]
        ).order_by('order_line')
        alt_mat_error_msgs = [
            {
                "item_no": line.order_line.item_no,
                "material_description": get_mat_desc_from_master_for_alt_mat_old(line.old_product),
                "error": line.error_type
            }
            for line in alternated_materials
        ]
    return alt_mat_error_msgs


def get_mat_desc_from_master_for_alt_mat_old(mat_variant: sap_migration_models.MaterialVariantMaster):
    try:
        """
            Querying Material Master with Mat code instead of using Material Id from Material Variant table for below reasons:
            1. Material Variant table has duplicate record for same Material code
            2. sometimes material id will be pointing to Grade Gram Materials instead of complete Mat Code
        """
        mat_master = sap_master_data_models.MaterialMaster.objects.filter(
            material_code=mat_variant.code
        ).first()
        # Use description_en if available, else use material_code
        mat_description = mat_master.description_en if mat_master and mat_master.description_en else mat_variant.code
        return mat_description
    except sap_master_data_models.MaterialMaster.DoesNotExist:
        return None


def get_alternated_material_related_data(order_line, material_description):
    alternated_materials = (AlternatedMaterial.objects.filter(
        Q(order_line=order_line)
        & (Q(error_type=AlternatedMaterialLogChangeError.NO_STOCK_ALT_MAT.value)
           | Q(error_type__isnull=True))
    ).order_by('id').first())
    # If no alternated_materials found, return the original material_description
    if not alternated_materials:
        return material_description
    # If new_product exists in alternated_materials, update old_product_description
    if alternated_materials.new_product:
        old_product_description = get_mat_desc_from_master_for_alt_mat_old(alternated_materials.old_product)
    else:
        old_product_description = alternated_materials.error_type
    return f"{material_description} \n({old_product_description})" if old_product_description else material_description


def compute_iplan_confirm_error_response_and_flag_r5(e, iplan_confirm_failed_errors, order_lines):
    logging.info("Iplan confirm failed :", e)
    iplan_confirm_failed_errors.append({"field": "IPLAN", "message": str(e.args[0].get("i_plan", ""))})
    update_attention_type_r5(order_lines)


def delete_order_in_db_to_avoid_duplication(sap_order_number):
    # Fetch orders with the given SAP order number
    orders = sap_migration_models.Order.objects.filter(so_no=sap_order_number).all()
    if not orders:
        return
    # Collect IDs of orders to avoid multiple queries
    order_ids = [order.id for order in orders]
    # Fetch order lines related to the orders
    order_lines_in_db = sap_migration_models.OrderLines.all_objects.filter(order_id__in=order_ids)
    # Fetch iPlan entries related to the collected order lines
    order_lines_iplan_in_db = sap_migration_models.OrderLineIPlan.objects.filter(
        id__in=order_lines_in_db.values('iplan_id')
    ).all()
    # Delete order lines and iPlan entries
    order_lines_in_db.delete()
    order_lines_iplan_in_db.delete()
    # Delete the orders
    orders.delete()


def round_qty_decimal(quantity, round_factor=TARGET_QTY_DECIMAL_DIGITS_TO_ROUND_UP):
    if quantity:
        quantity = round(quantity, round_factor)
    return quantity


def alt_mat_mapping_duplicate_validation(material_own_id, sale_organization_id, sold_to_id, edit_material=None):
    material_own = sap_migration_models.AlternateMaterial.objects.filter(
        sales_organization__id=sale_organization_id,
        sold_to__id=sold_to_id,
        material_own__id=material_own_id
    ).first()
    if not material_own:
        # Add alt mat - non duplicate case
        return
    if edit_material:
        if material_own.id == edit_material.id:
            # Edit alt mat - non duplicate case
            return
    raise ValidationError(
        {
            "material_own_id": ValidationError(
                DUPLICATE_ALT_MAT_MAPPING_ERR_MSG,
                code=ContractCheckoutErrorCode.INVALID.value,
            )
        }
    )


def get_order_line_material_type(line, material_variant):
    material_type = line.material.material_type if line.material else None
    if not material_type:
        if material_variant and material_variant.material:
            material_type = material_variant.material.material_type
        elif line.contract_material and line.contract_material.material:
            material_type = line.contract_material.material.material_type
    return material_type


def update_active_for_missing_contract_materials(contract_materials, contract_material_pks):
    inactive_contract_materials = []
    for material in contract_materials:
        if material.pk not in contract_material_pks:
            material.is_active = False
            inactive_contract_materials.append(material)
    if inactive_contract_materials:
        sap_migration_models.ContractMaterial.objects.bulk_update(
            inactive_contract_materials, ["is_active"]
        )


def get_parent_directory(directory, levels=1):
    """
    Get the parent directory of the specified directory.
    :param directory: The starting directory.
    :param levels: The number of levels to go up in the directory tree.
    :return: The parent directory.
    """
    parent = directory
    for _ in range(levels):
        parent = os.path.dirname(parent)
    return parent


def get_name_from_sold_to_partner_address_master(sold_to_code):
    sold_to_code_formatted = sold_to_code.lstrip("0")
    partner = sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(sold_to_code=sold_to_code,
                                                                               partner_role='AG').first()
    sold_to_partner_address_names = sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(
        sold_to_code=sold_to_code, address_code=partner.address_link, partner_code=partner.partner_code).values("name1",
                                                                                                                "name2",
                                                                                                                "name3",
                                                                                                                "name4").first()
    if sold_to_partner_address_names:
        name1, name2, name3, name4 = sold_to_partner_address_names.values()
        sold_to_name = f"{name1 or ''}{name2 or ''}{name3 or ''}{name4 or ''}"
        return f"{sold_to_code_formatted}-{sold_to_name}"
    else:
        return sold_to_code_formatted or ""


def get_sold_to_partner(sold_to_code):
    if not sold_to_code:
        return None
    partner = sap_master_data_models.SoldToChannelPartnerMaster.objects.filter(sold_to_code=sold_to_code,
                                                                               partner_role='AG').first()
    if not partner:
        return None
    return sap_master_data_models.SoldToPartnerAddressMaster.objects.filter(sold_to_code=sold_to_code,
                                                                            address_code=partner.address_link,
                                                                            partner_code=partner.partner_code).first()


def mapping_order_partners(order_partners):
    result = {
        "order": {},
        "order_lines": {}
    }
    mapping_partner_role_with_name = {
        "AG": "sold_to",
        "WE": "ship_to",
        "RE": "bill_to"
    }

    for order_partner in order_partners:
        partner_role = order_partner.get("partnerRole", "")
        if partner_role in mapping_partner_role_with_name:
            item_no = order_partner.get("itemNo", False)
            if item_no:
                if item_no not in result["order_lines"]:
                    result["order_lines"][item_no] = {}
                result["order_lines"][item_no][
                    mapping_partner_role_with_name[partner_role]] = make_ship_to_from_order_partner(order_partner)
                continue
            result["order"][mapping_partner_role_with_name[partner_role]] = make_ship_to_from_order_partner(
                order_partner)
    return result


def get_internal_emails_by_config(feature_name, sale_org, product_group, bu=PP_BU, **kwargs):
    exclude_sale_org_and_product_group_filter = kwargs.get('exclude_sale_org_and_product_group_filter', False)
    query_bu = Q()
    for bu in EmailConfigurationInternal.objects.filter(**{f"{feature_name}": True}, bu__in=bu) \
            .values_list('bu', flat=True):
        query_bu |= Q(bu__iexact=bu.strip())

    query_team = Q()
    for team in EmailConfigurationInternal.objects.filter(**{f"{feature_name}": True}).values_list('team', flat=True):
        query_team |= Q(team__iexact=team.strip())

    query_product_group = Q()
    """
    exclude_sale_org_and_product_group_filter = True for EO Upload Summary Email. 
    As success and failure cases together. And it applies to only Phase1 products i.e., K01 & K09.
    In failure cases we can have undefined product group or sale org or both. 
    Hence no filter is applied on product group & sale org explicitly.
    """
    if exclude_sale_org_and_product_group_filter:
        email_mappings = EmailInternalMapping.objects.filter(
            query_bu,
            query_team,
        )
    else:
        if product_group:
            if type(product_group) == list:
                for pg in product_group:
                    query_product_group |= Q(product_group__iexact=pg.strip())
            elif type(product_group) == str:
                query_product_group |= Q(product_group__iexact=product_group.strip())
            query_product_group |= Q(product_group__iexact=EmailProductGroupConfig.ALL.value)
        else:
            query_product_group |= Q(product_group__iexact=EmailProductGroupConfig.UNDEFINED.value)

        sale_org_query = Q()
        if sale_org:
            if type(sale_org) == list:
                for org in sale_org:
                    sale_org_query |= Q(sale_org__regex=r'^0*' + org.lstrip('0') + '$')
            else:
                sale_org_query = Q(sale_org__regex=r'^0*' + sale_org.lstrip('0') + '$')
            sale_org_query |= Q(sale_org__iexact=EmailSaleOrgConfig.ALL.value)
        else:
            sale_org_query |= Q(sale_org__iexact=EmailSaleOrgConfig.UNDEFINED.value)

        email_mappings = EmailInternalMapping.objects.filter(
            query_product_group,
            query_bu,
            query_team,
            sale_org_query,
        )

    mails = list(set(email_mapping.email.replace(' ', '') for email_mapping in email_mappings if
                     email_mapping.email and email_mapping.email.strip()))
    mails = list(set([item for mail in mails for item in mail.split(",")]))
    return mails


def get_product_group_from_es_17(sap_response):
    if not sap_response:
        return None

    order_items_out = sap_response.get('orderItemsOut')
    if not order_items_out:
        return None

    return next((item.get('prcGroup1') for item in order_items_out if item.get('prcGroup1')), None)
