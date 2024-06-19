import copy
import logging
import re
import uuid
from datetime import datetime

from common.enum import MulesoftServiceType, MulesoftFeatureType
from common.helpers import mock_confirm_date, DateHelper
from common.mulesoft_api import MulesoftApiRequest
from sap_master_data import mulesoft_api
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import CreatedFlow
from sap_migration.graphql.enums import OrderType
from sap_migration.models import OrderLines, Order
from scg_checkout.graphql.enums import (
    MaterialType,
    PaymentTerm,
    DocType,
    LanguageCode,
    IPlanOrderItemStatus, )
from scg_checkout.graphql.helper import add_item_to_dict_with_index, round_qty_decimal
from scg_checkout.graphql.helper import (
    update_order_status,
    prepare_param_es21_order_text_for_change_order_domestic,
    deepgetattr
)
from common.util.utility import get_order_text_language, get_lang_by_order_text_lang_db
from scgp_eo_upload.implementations.helpers import eo_upload_send_email_when_call_api_fail
from scgp_export.graphql.enums import (
    SapEnpoint,
    ItemCat,
    TextID, text_id_list_eo,
)
from scgp_export.graphql.helper import change_order_request_es21
from scgp_po_upload.graphql.enums import SAP21, SAP27, BeingProcessConstants, SapType, MessageErrorItem
from scgp_po_upload.graphql.helpers import load_error_message, validate_order_msg
from scgp_require_attention_items.graphql.enums import SourceOfAppData
from scgp_require_attention_items.graphql.helper import update_attention_type_r5
from sap_master_data import models as sap_master_data_models

DYNAMIC_VALUE = "&"
DYNAMIC_VALUE1 = "&1"
DYNAMIC_VALUE2 = "&2"
DYNAMIC_VALUE3 = "&3"
DYNAMIC_VALUE4 = "&4"


def get_order_partner(order, order_lines):
    order_partners = []
    mapping_addresses = {
        "WE": str(order.ship_to).split(" - ")[0],
        "AG": str(order.sold_to.sold_to_code),
    }
    if order.type.lower() == "export":
        mapping_addresses = {
            **mapping_addresses,
            "RE": str(order.bill_to or "").split(" - ")[0] or "",
            "RG": str(order.payer or "").split(" - ")[0] or "",
            "VE": str(order.sales_employee or "").split(" - ")[0] or "",
            "AP": str(order.contact_person or "").split(" - ")[0] or "",
            "AU": str(order.author or "").split(" - ")[0] or "",
            "ZI": str(order.end_customer or "").split(" - ")[0] or ""
        }
    if (
            order.type.lower() == "domestic" and order.created_by_flow == CreatedFlow.DOMESTIC_EORDERING.value) or order.type.lower() == "customer":
        mapping_addresses = {
            **mapping_addresses,
            "RE": str(order.bill_to).split(" - ")[0] or "",
        }

    if order.type.lower() == OrderType.DOMESTIC.value and order.created_by_flow != CreatedFlow.DOMESTIC_EORDERING.value:
        mapping_addresses = {
            **mapping_addresses,
            "RE": str(order.bill_to).split(" - ")[0] or "",
            "RG": str(order.payer or "").split(" - ")[0] or "",
        }

    # if order.eo_upload_log:
    for partner_role, partner_no in mapping_addresses.items():
        if not partner_no:
            continue
        order_partners.append(
            {
                "partnerRole": partner_role,
                "partnerNo": partner_no,
            }
        )
    if order_lines:
        for line in order_lines:
            if line.ship_to:
                order_partners.append(
                    {
                        "partnerRole": "WE",
                        "partnerNo": line.ship_to.split(" - ")[0].lstrip(),
                        "itemNo": line.item_no
                    }
                )
    return order_partners


def get_po_number_from_order(order):
    if order.type == "domestic" or order.type == "customer":
        po_number = order.po_number
    else:
        po_number = order.po_no
    return po_number if po_number else ""


def process_export_order_header_data(order_header_updated_data, contract_details, order, ignore_blank):
    export_order_text_lists = []
    item_no = "000000"

    header_mapping = {
        'payment_instruction': (order.payment_instruction, TextID.HEADER_PAYIN.value),
        'internal_comment_to_logistic': (order.internal_comments_to_logistic, TextID.HEADER_ICTL.value),
        'external_comment_to_customer': (order.external_comments_to_customer, TextID.HEADER_ECTC.value),
        'production_information': (order.production_information, TextID.HEADER_PI.value),
        'internal_comment_to_warehouse': (order.internal_comment_to_warehouse, TextID.HEADER_ICTW.value),
        'remark': (order.remark, TextID.HEADER_REMARK.value),
        'etd': (date_to_sap_date(order.etd), TextID.HEADER_ETD.value),
        'eta': (date_to_sap_date(order.eta), TextID.HEADER_ETA.value),
        'port_of_discharge': (order.port_of_discharge, TextID.HEADER_PORT_OF_DISCHARGE.value),
        'no_of_containers': (order.no_of_containers, TextID.HEADER_NO_OF_CONTAINERS.value),
        'dlc_expiry_date': (
            order.dlc_expiry_date.strftime("%d%m%Y") if order.dlc_expiry_date else "",
            TextID.HEADER_DLC_EXPIRY_DATE.value),
        'dlc_latest_delivery_date': (
            order.dlc_latest_delivery_date.strftime("%d%m%Y") if order.dlc_latest_delivery_date else "",
            TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value),
        'dlc_no': (order.dlc_no, TextID.HEADER_DLC_NO.value),
        'uom': (order.uom, TextID.HEADER_UOM.value),
        'port_of_loading': (order.port_of_loading, TextID.HEADER_PORT_OF_LOADING.value),
        'gw_uom': (order.gw_uom, TextID.HEADER_GW_UOM.value),
        'shipping_mark': (order.shipping_mark, TextID.ITEM_SHIPPING_MARK.value),
    }

    for header_key, (header_variable, text_id) in header_mapping.items():
        # From UI
        # Send data to sap only if the value is updated
        if not order.eo_upload_log:
            if order_header_updated_data:
                if header_key in order_header_updated_data:
                    export_order_text_lists.append((header_variable, item_no, text_id, ignore_blank,
                                                    get_order_text_language(contract_details, order, text_id,
                                                                            is_header=True)))
        # From EO Upload
        # Didn't check updated data, so send all data to sap
        else:
            if header_key == 'port_of_loading':
                continue
            if header_key in ['production_information', 'eta', 'etd']:
                export_order_text_lists.append((header_variable, item_no, text_id, True,
                                                get_order_text_language(contract_details, order, text_id,
                                                                        is_header=True)))
                continue
            export_order_text_lists.append((header_variable, item_no, text_id, ignore_blank,
                                            get_order_text_language(contract_details, order, text_id, is_header=True)))

    return export_order_text_lists


def request_create_order_sap(need_invoke_iplan, order, manager, order_header_updated_data=None, po_upload_mode="",
                             ui_order_lines_info=None):
    """
    Call SAP create order
    :params order: e-ordering order
    :params manager: plugin manager
    :params order_header_updated_data:to identify the updated fields
    :params po_upload_mode: A for Customer Role, B for CS Role, '' for normal case
    :return: SAP response
    """
    order_lines = sap_migration_models.OrderLines.objects.filter(order=order)
    '''
    https://scgdigitaloffice.atlassian.net/browse/SEO-3817
    Customer Input for below UI fields should take precedence over contract comments
    ข้อมูลเพิ่มเติมสำหรับครังสินค้า (z001 i.e., input to  warehouse),
    ข้อมูลเพิ่มเติมสำหรับการจัดส่ง (z002 i.e., input to  logistic) 
    '''
    if order.type == OrderType.CUSTOMER.value:
        internal_comments_to_warehouse = order.internal_comment_to_warehouse or order.internal_comments_to_warehouse or ""
        internal_comments_to_logistic = order.internal_comments_to_logistic or " "
    else:
        internal_comments_to_warehouse = order.internal_comments_to_warehouse or order.internal_comment_to_warehouse or ""
        internal_comments_to_logistic = order.internal_comments_to_logistic or order.remark_for_logistic or ""
    external_comments_to_customer = order.external_comments_to_customer or ""
    product_information = order.product_information or order.production_information or ""
    remark = order.remark or ""
    payment_instruction = order.payment_instruction or ""
    contract = order.contract
    sales_organization = contract and contract.sales_organization or None
    shipping_mark = order.shipping_mark or ""
    sales_organization_code = sales_organization and sales_organization.code or None
    if order.sales_organization:
        sales_organization_code = order.sales_organization.code
    # ETD is char field
    # ETA is date field
    # TODO: handle this case
    etd = date_to_sap_date(order.etd)
    eta = date_to_sap_date(order.eta)
    # TODO: handle in case of eo upload
    if order.type == "export":
        # FIXME: handle this case, ETA is date field
        try:
            # UI got %Y-%m-%d, but eo upload not
            etd = datetime.strptime(order.etd, "%Y-%m-%d").strftime("%d%m%Y") if order.etd else ""
        except:
            pass
        try:
            eta = datetime.strptime(str(order.eta), "%Y-%m-%d").strftime("%d%m%Y") if order.eta else ""
        except:
            pass
    port_of_discharge = order.port_of_discharge or ""
    port_of_loading = order.port_of_loading or ""
    no_of_containers = order.no_of_containers or ""
    dlc_expiry_date = order.dlc_expiry_date.strftime(
        "%d%m%Y") if order.dlc_expiry_date else ""
    dlc_latest_delivery_date = order.dlc_latest_delivery_date.strftime(
        "%d%m%Y") if order.dlc_latest_delivery_date else ""
    dlc_no = order.dlc_no or ""
    uom = order.uom or ""
    gw_uom = order.gw_uom or ""

    order_partners = get_order_partner(order, order_lines)

    request_items = []
    request_schedules = []
    request_texts = []
    web_user_name = []
    item_no = "000000"

    if order.web_user_name:
        web_user_name = order.web_user_name.split("\n")

    if len(web_user_name) == 2:
        _, *_names = web_user_name[1].split(" ")
        uname = " ".join(_names)
        z095_string = get_valid_z095_name(web_user_name[0])
        request_texts.append(
            {
                "itemNo": item_no,
                "textId": TextID.SYSTEM_SOURCE.value,
                "textLines": [{"textLine": z095_string}],
            }
        )
        request_texts.append(
            {
                "itemNo": item_no,
                "textId": TextID.WEB_USERNAME.value,
                "textLines": [{"textLine": uname}],
            }
        )
    contract_code = order.contract.code if order.contract else ""
    _error, contract_details = mulesoft_api.get_contract_detail(contract_code)
    # role customer: ignore empty order texts
    order_type = order.type or ""
    ignore_blank = order_type in ["customer"] or False
    default_text_list = [
        (internal_comments_to_warehouse, item_no, TextID.HEADER_ICTW.value, False,
         get_order_text_language(contract_details, order, TextID.HEADER_ICTW.value, is_header=True)),
        # ignore if eo upload / required for customer, export, domestic
        (internal_comments_to_logistic, item_no, TextID.HEADER_ICTL.value, order.eo_upload_log and True or False,
         get_order_text_language(contract_details, order, TextID.HEADER_ICTL.value, is_header=True)),
        (external_comments_to_customer, item_no, TextID.HEADER_ECTC.value, ignore_blank, get_lang_by_order_text_lang_db(
            contract, TextID.HEADER_ECTC.value, item_no
        )),
        (product_information, item_no, TextID.HEADER_PI.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_PI.value, is_header=True)),
    ]
    # using this list for export

    export_order_text_lists = []
    if OrderType.EXPORT.value == order_type:
        export_order_text_lists = process_export_order_header_data(order_header_updated_data, contract_details, order,
                                                                   ignore_blank)

    extend_text_list = [
        (remark, item_no, TextID.HEADER_REMARK.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_REMARK.value, is_header=True)),
        (payment_instruction, item_no, TextID.HEADER_PAYIN.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_PAYIN.value, is_header=True)),
        (etd, item_no, TextID.HEADER_ETD.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_ETD.value, is_header=True)),
        (eta, item_no, TextID.HEADER_ETA.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_ETA.value, is_header=True)),
        (port_of_discharge, item_no, TextID.HEADER_PORT_OF_DISCHARGE.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_PORT_OF_DISCHARGE.value, is_header=True)),
        (no_of_containers, item_no, TextID.HEADER_NO_OF_CONTAINERS.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_NO_OF_CONTAINERS.value, is_header=True)),
        (dlc_expiry_date, item_no, TextID.HEADER_DLC_EXPIRY_DATE.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_DLC_EXPIRY_DATE.value, is_header=True)),
        (dlc_latest_delivery_date, item_no, TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_DLC_LATEST_DELIVERY_DATE.value,
                                 is_header=True)),
        (dlc_no, item_no, TextID.HEADER_DLC_NO.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_DLC_NO.value, is_header=True)),
        (uom, item_no, TextID.HEADER_UOM.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_UOM.value, is_header=True)),
        (gw_uom, item_no, TextID.HEADER_GW_UOM.value, ignore_blank,
         get_order_text_language(contract_details, order, TextID.HEADER_GW_UOM.value, is_header=True)),
    ]

    if OrderType.EXPORT.value != order_type:
        default_text_list.append((port_of_loading, item_no, TextID.HEADER_PORT_OF_LOADING.value, ignore_blank,
                                  get_lang_by_order_text_lang_db(contract, TextID.HEADER_PORT_OF_LOADING.value,
                                                                 item_no)))

    if order_type != OrderType.DOMESTIC.value and order_type != OrderType.EXPORT.value:
        default_text_list += extend_text_list

    # Using this for export order
    if order_type == OrderType.EXPORT.value:
        default_text_list = export_order_text_lists
    # init request_texts
    for text_args in default_text_list:
        text_lines = text_args[0]
        if (order_type == OrderType.EXPORT.value and text_lines) or (
                order_type in [OrderType.DOMESTIC.value, OrderType.CUSTOMER.value]):
            item_no = text_args[1]
            text_id = text_args[2]
            ignore_blank = text_args[3]
            language = text_args[4]
            if order.eo_upload_log:
                if text_id not in text_id_list_eo and not ignore_blank:
                    ignore_blank = True
            handle_request_text_to_es17(request_texts, text_lines, item_no, text_id, ignore_blank, language)

    request_items_container = []
    request_schedules_container = []
    request_texts_container = []
    for line in order_lines:

        if line.item_cat_eo == ItemCat.ZKC0.value:
            request_items_container, request_schedules_container, request_texts_container = handle_lines_to_request_es17(
                need_invoke_iplan,
                line, order, request_items_container, request_schedules_container, request_texts_container,
                contract_details, ui_order_lines_info=ui_order_lines_info)
        else:
            request_items, request_schedules, request_texts = handle_lines_to_request_es17(need_invoke_iplan, line,
                                                                                           order, request_items,
                                                                                           request_schedules,
                                                                                           request_texts,
                                                                                           contract_details,
                                                                                           ui_order_lines_info=ui_order_lines_info)

    request_items += request_items_container
    request_schedules += request_schedules_container
    request_texts += request_texts_container

    request_id = str(uuid.uuid1().int)
    req_date = order.request_date or order.request_delivery_date or None
    if isinstance(req_date, str):
        req_date = datetime.strptime(req_date, '%Y-%m-%d')

    payment_term = order.contract.payment_term_key or PaymentTerm.DEFAULT.value
    doc_type = order.order_type or DocType.ZOR.value

    # Case domestic or customer order, NT00 --> ZBV, NTxx --> ZOR
    if order.type != OrderType.EXPORT.value and payment_term == PaymentTerm.DEFAULT.value:
        doc_type = DocType.ZBV.value
    if order.eo_upload_log_id:
        payment_term = order.payment_term

    '''https://scgdigitaloffice.atlassian.net/browse/SEO-3708
    if order is placed by customer then sales group is optional and not to be SENT.
    Hence set default value of sales_group to None
    '''
    sales_group = None
    if order.type != OrderType.CUSTOMER.value:
        sales_group = getattr(order, "sales_group", getattr(contract, "sales_group"))
    sales_office = getattr(order, "sales_office", getattr(contract, "sales_office"))
    sales_org = getattr(order, "sales_organization", getattr(contract, "sales_organization"))
    if request_items is not None:
        order_items_in = sorted(request_items, key=lambda x: int(x["itemNo"]))
    else:
        order_items_in = []

    if request_schedules is not None:
        order_schedules_in = sorted(request_schedules, key=lambda x: int(x["itemNo"]))
    else:
        order_schedules_in = []

    if order_partners:
        order_partners = sorted(order_partners, key=lambda x: int(x.get("itemNo", "0")))

    if request_texts:
        request_texts = sorted(request_texts, key=lambda x: int(x.get("itemNo", "0")))

    params = {
        "piMessageId": request_id,
        "testrun": False,
        "poUploadMode": po_upload_mode,
        "savePartialItem": bool(po_upload_mode),
        "orderHeader": {
            "docType": doc_type,
            "salesOrg": getattr(sales_org, "code", ""),
            "distributionChannel": order.distribution_channel
                                   and order.distribution_channel.code
                                   or "",
            "division": order.division and order.division.code or None,
            "salesGroup": getattr(sales_group, "code", ""),
            "salesOffice": getattr(sales_office, "code", ""),
            "reqDate": req_date and req_date.strftime('%d/%m/%Y') or "",
            "incoterms1": order.incoterm or "",
            "incoterms2": order.place_of_delivery or "",
            "paymentTerm": payment_term,
            "poNo": get_po_number_from_order(order),
            "poDate": order.po_date.strftime('%d/%m/%Y') if order.po_date else "",
            # "priceGroup": order.price_group,
            # "priceDate": order.price_date.strftime('%d/%m/%Y') if order.price_date else "",
            # "currency": order.currency,
            # "customerGroup": order.customer_group.code if order.price_date else "",
            # "customerGroup1": order.customer_group_1.code if order.customer_group_1 else "",
            # "customerGroup2": order.customer_group_2.code if order.customer_group_2 else "",
            # "customerGroup3": order.customer_group_3.code if order.customer_group_3 else "",
            # "customerGroup4": order.customer_group_4.code if order.customer_group_4 else "",
            # "deliveryBlock": order.delivery_block,
            # contractNo required by SAP
            # "contactNo": order.contract.code if order.contract else "",
            "contactNo": contract_code,
            "description": order.description or "",
            "unloadingPoint": order.unloading_point or "",
            "usage": order.usage or "",
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderSchedulesIn": order_schedules_in,
        "orderTexts": request_texts,
    }

    if order.type == OrderType.CUSTOMER.value:
        del params["orderHeader"]["salesGroup"]
        del params["orderHeader"]["salesOffice"]
        del params["orderHeader"]["incoterms1"]
        del params["orderHeader"]["incoterms2"]
        del params["orderHeader"]["description"]
        del params["orderHeader"]["unloadingPoint"]
        del params["orderHeader"]["usage"]

    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
        "feature": MulesoftFeatureType.CREATE_ORDER.value,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_17.value,
        params
    )
    return response


def get_valid_z095_name(web_user_name):
    valid = False
    for key in dir(SourceOfAppData):
        value = ""
        try:
            value = SourceOfAppData[key].value
        except KeyError:
            logging.debug("key not found ")
        if web_user_name == value:
            valid = True
            return web_user_name
    if not valid:
        logging.error("Not valid web z095 attribute got . defaulting to %s",
                      SourceOfAppData.DOMESTIC_ORDER_SCREEN.value)
        return SourceOfAppData.DOMESTIC_ORDER_SCREEN.value


def request_change_order_sap(order, i_plan_order_lines, manager):
    """
    Call sap to request update orders
    :params orders: order
    :return: sap response
    """
    order_lines = sap_migration_models.OrderLines.objects.filter(order=order)

    request_items = []
    request_items_x = []
    request_schedules = []
    request_schedules_x = []
    request_conditions = []
    request_conditions_x = []
    confirm_quantity = 0
    for line in order_lines:
        request_items_base = {
            "itemNo": line.item_no,
            "materialNo": line.material_variant
                          and line.material_variant.code
                          or "",
            "targetQty": line.target_quantity,
            "salesUnit": "ROL",
            "plant": line.plant,
            "shippingPoint": "MY0067",
            "route": "7504",
            "orderNo": "MPS/PO/SKT023/21",
            "poItemNo": "000010",
            "itemCategory": "ZKS4",
            "priceGroup1": "",
            "priceGroup2": "",
            "poNo": "K00040064300100001WY0000000-1730896",
            "poitemNoS": "000010",
            "usage": "100",
            "overdlvtol": line.delivery_tol_over,
            "unlimitTol": "",
            "unddlvTol": line.delivery_tol_under,
            "reasonReject": "93",
            "paymentTerms": "TL60",
            "denominato": 1,
            "numconvert": 1000,
            "refDoc": line.ref_doc,
            "refDocIt": line.ref_doc_it or "",
        }

        if line.delivery_tol_unlimited:
            request_items_base["overdlvtol"] = 0
            request_items_base["unlimitTol"] = "X"
            request_items_base["unddlvTol"] = 0
            # order_items_base.pop("overdlvtol")
            # order_items_base.pop("unddlvTol")

        if not line.delivery_tol_over:
            request_items_base.pop("overdlvtol")

        if not line.delivery_tol_under:
            request_items_base.pop("unddlvTol")

        request_items.append(request_items_base)
        request_items_x.append(
            {
                "itemNo": line.item_no,
                "updateflag": "U",
                "targetQty": True,
                "salesUnit": True,
                "plant": True,
                "shippingPoint": True,
                "route": True,
                "purchaseOrderNo": True,
                "poItemNo": True,
                "itemCategory?:description": True,
                "priceGroup1": True,
                "priceGroup2": True,
                "poNo": True,
                "poDate": True,
                "poitemNoS": True,
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
            confirm_quantity = line.iplan.iplant_confirm_quantity or 0
        # if line.item_cat_eo == ItemCat.ZKSO.value:
        #     confirm_quantity = line.target_quantity
        if line.item_cat_eo == ItemCat.ZKC0.value:
            confirm_quantity = line.quantity or 0
        dispatch_date_str = i_plan_order_lines.get(line.item_no, {}).get("dispatchDate", None) or mock_confirm_date(
            line.request_date, i_plan_order_lines[line.item_no]["status"])
        dispatch_date = dispatch_date_str.split("-")[::-1]
        request_schedules.append(
            {
                "itemNo": line.item_no,
                "scheduleLine": "0001",
                "scheduleLinecate": "ZC",
                "reqDate": dispatch_date.strftime(
                    "%d/%m/%Y") if dispatch_date and dispatch_date != line.request_date else line.request_date.strftime(
                    "%d/%m/%Y"),
                "reqQty": line.target_quantity,
                "confirmQty": confirm_quantity
            }
        )
        request_schedules_x.append(
            {
                "itemNo": line.item_no,
                "scheduleLine": "0001",
                "updateflag": True,
                "scheduleLineCate": True,
                "requestDate": True,
                "reqiestQuantity": True,
                "confirmQuantity": True,
                "deliveryBlock": True,
            }
        )
        request_conditions.append(
            {
                "itemNo": line.item_no,
                "conditionType": "ZPR2",
                "conditionValue": 4816,
                "currency": "THB",
                "conditionUnit": "ROL",
                "conditionPUnit": "1",
            }
        )
        request_conditions_x.append(
            {
                "itemNo": line.item_no,
                "conditionType": "ZPR2",
                "updateFlag": True,
                "conditionValue": True,
                "currency": True,
                "conditionUnit": True,
                "conditionPUnit": True,
            }
        )

    params = {
        "piMessageId": "5100000753",
        # Todo: this is order id save in SAP, need to store in our db
        # Todo: ask Ducdm1 for this
        "salesdocumentin": "0410273310",
        "testrun": False,
        "orderHeader": {
            "reqDateH": order.request_date.strftime("%d/%m/%Y")
            if order.request_date
            else "",
            "incoterms1": order.incoterms_1,
            "incoterms2": order.incoterms_2,
            "paymentTerms": order.payment_term,
            "poNo": order.po_no,
            # Todo: have no idea about this field
            # Todo: ask Ducdm1 for this
            "purchaseDate1": "",
            "priceGroup": order.price_group,
            "priceDate": order.price_date.strftime("%d/%m/%Y") if order.po_date else "",
            "currency": order.currency,
            "salesDistrict": order.sales_district,
            "shippingCondition": order.shipping_condition,
            "custtomerGroup": order.customer_group.code if order.price_date else "",
            "custtomerGroup1": order.customer_group_1.code
            if order.customer_group_1
            else "",
            "custtomerGroup2": order.customer_group_2.code
            if order.customer_group_2
            else "",
            "custtomerGroup3": order.customer_group_3.code
            if order.customer_group_3
            else "",
            "custtomerGroup4": order.customer_group_4.code
            if order.customer_group_4
            else "",
            "refDoc": order.contract.code if order.contract else "",
        },
        "orderHeaderInX": {
            "reqDate": True,
            "incoterms1": True,
            "incoterms2": True,
            "paymentTerms": True,
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
            "customerGroup5": True,
            "deliveryBlock": True,
        },
        # Todo: query in sap_master_data_soldtochannelpartnermaster table by sold_to_code
        # Todo: ask Ducdm1 for this
        "orderPartners": [
            {
                "partnerRole": "WE",
                "partnerNo": "0001002813",
                "itemNo": "000000",
                "addressLink": "12address",
            }
        ],
        # Todo: query in sap_master_data_soldtopartneraddressmaster table by sold_to_code
        # Todo: ask Ducdm1 for this
        "PartnerAddreses": [
            {
                "addressNo": "1",
                "name1": "นาย Customer Name1",
                "name2": "",
                "name3": "",
                "name4": "",
                "city": "",
                "zipCode": "10220",
                "district": "บางซื่อ",
                "street": "",
                "streetSuppl1": "",
                "streetSuppl2": "",
                "streetSuppl3": "",
                "location": "",
                "transportZone": "ZATH010029",
                "country": "TH",
                "telephoneNo": "",
            }
        ],
        "orderItemsIn": request_items,
        "orderItemsInx": request_items_x,
        "orderSchedulesIn": request_schedules,
        "orderSchedulesInx": request_schedules_x,
        "orderConditionsIn": request_conditions,
        "orderConditionsInX": request_conditions_x,
        "orderCfgsValues": [
            {"configId": "000010", "instId": "000010", "charc": "SDKUOM", "value": "MM"}
        ],
        "orderText": [
            {
                "itemNo": "000000",
                "textId": "Z016",
                "langu": "EN",
                "textLine": [{"textLine": "เพิ่มบอร์ดใหม่ส่วนลด 14%"}],
            }
        ],
    }
    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
        "feature": MulesoftFeatureType.CHANGE_ORDER.value
    }

    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_17.value,
        params
    )
    return response


def request_sap_es21(order, manager, sap_update_flag=None, order_lines_change_request_date=None,
                     origin_order_lines=None,
                     original_order=None, updated_data=None, pre_update_lines={}, export_delete_flag=True,
                     updated_items=[]):
    sap_update_flag = sap_update_flag or {}

    order_type = order.type
    if order_type == OrderType.EXPORT.value:
        return change_order_request_es21(order, manager, sap_update_flag, updated_data=original_order,
                                         pre_update_lines=pre_update_lines, export_delete_flag=export_delete_flag,
                                         updated_items=updated_items)

    order_lines = updated_items or sap_migration_models.OrderLines.objects.filter(order=order)
    fields_of_order = {
        "po_no": "poNo",
        "po_date": "purchaseDate",
        "customer_group_1_id": "customerGroup1",
        "customer_group_2_id": "customerGroup2",
        "customer_group_3_id": "customerGroup3",
        "customer_group_4_id": "customerGroup4",
        "incoterms_1_id": "incoterms1",
    }
    field_of_order_line = {
        "request_date": "reqDate",
        "quantity": "targetQty",
        "plant": "plant",
        "shipping_point": "shippingPoint",
        "route": "route",
        "po_no": "purchaseNoC",
        "delivery_tol_over": "overdlvtol",
        "delivery_tol_unlimited": "unlimitTol",
        "delivery_tol_under": "unddlvTol",
    }
    order_header_in = {
        "incoterms1": order.incoterms_1.code if order.incoterms_1 else "",
        "poNo": order.po_no if order.po_no else "",
        "purchaseDate": order.po_date.strftime("%d/%m/%Y") if order.po_date else "",
        "customerGroup1": deepgetattr(order, "customer_group_1.code", ""),
        "customerGroup2": deepgetattr(order, "customer_group_2.code", ""),
        "customerGroup3": deepgetattr(order, "customer_group_3.code", ""),
        "customerGroup4": deepgetattr(order, "customer_group_4.code", ""),
        "refDoc": deepgetattr(order, "contract.code", ""),
    }

    flag_update = {}
    for field, value in fields_of_order.items():
        flag_update[field] = True
        if getattr(order, field, None) == getattr(original_order, field, None):
            flag_update[field] = False
            order_header_in.pop(value, None)

    origin_order_lines_object = {}
    for origin_order_line in origin_order_lines:
        origin_order_lines_object[origin_order_line.item_no] = origin_order_line

    order_items_in = []
    order_items_inx = []
    order_schedules_in = []
    order_schedules_inx = []
    ship_to_partners = {}
    confirm_quantity = 0

    for order_line in order_lines:
        if order_line.ship_to:
            ship_to_partners[order_line.item_no] = order_line.ship_to.split(" - ")[0]

    order_partners = get_order_partner_for_es21(order)

    for line in order_lines:
        if ship_to_partners.get(line.item_no):
            order_partners.append(
                {
                    "partnerRole": "WE",
                    "partnerNumb": ship_to_partners[line.item_no],
                    "itemNo": line.item_no
                }
            )

    for line in order_lines:
        item_no = line.item_no.zfill(6)
        origin_order_line_object = origin_order_lines_object.get(line.item_no)
        flag_update_line = {}

        request_items_base = {
            "itemNo": item_no,
            "material": line.material_variant.code
            if line.material_variant.code
            else "",
            "targetQty": line.quantity if line.quantity else 0,
            "salesUnit": "EA" if line.contract_material.material.material_group == "PK00" else "ROL",
            "plant": line.plant or "",
            "shippingPoint": line.shipping_point or "",
            "route": line.route.split(" - ")[0] if line.route else "",
            "purchaseNoC": line.po_no if line.po_no else "",
            "overdlvtol": line.delivery_tol_over,
            "unlimitTol": "",
            "unddlvTol": line.delivery_tol_under,
            "refDoc": line.ref_doc if line.ref_doc else "",
            "refDocIt": line.contract_material and line.contract_material.item_no or "",
        }
        if line.delivery_tol_unlimited:
            request_items_base["overdlvtol"] = 0
            request_items_base["unlimitTol"] = "X"
            request_items_base["unddlvTol"] = 0

        if not line.delivery_tol_over:
            request_items_base.pop("overdlvtol")

        if not line.delivery_tol_under:
            request_items_base.pop("unddlvTol")

        for field, value in field_of_order_line.items():
            flag_update_line[field] = True
            if getattr(origin_order_line_object, field, None) == getattr(line, field, None):
                flag_update_line[field] = False
                request_items_base.pop(value, None)

        order_items_in.append(request_items_base)

        order_items_inx.append(
            {
                "itemNo": item_no,
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                "targetQty": flag_update_line["quantity"],
                "salesUnit": False,
                "plant": flag_update_line["plant"],
                "shippingPoint": flag_update_line["shipping_point"],
                "route": flag_update_line["route"],
                "custPoNo": flag_update_line["po_no"],
                "overdlvtol": flag_update_line["delivery_tol_over"],
                "unlimitTol": flag_update_line["delivery_tol_unlimited"],
                "unddlvTol": flag_update_line["delivery_tol_under"],
            }
        )
        if line.iplan:
            confirm_quantity = line.iplan.iplant_confirm_quantity if line.i_plan_on_hand_stock else 0
        if line.item_cat_eo == ItemCat.ZKC0.value:
            confirm_quantity = line.quantity or 0

            # Todo: improve late
        order_schedule_in = {
            "itemNo": item_no,
            "scheduleLine": "0001",
            "reqDate": line.request_date.strftime("%d/%m/%Y") if line.request_date else "",
            "reqQty": line.quantity,
            "confirmQty": confirm_quantity or 0
        }

        for field in ["request_date", "quantity"]:
            flag_update_line[field] = True
            if getattr(origin_order_line_object, field, None) == getattr(line, field, None):
                flag_update_line[field] = False
                if field == "request_date":
                    order_schedule_in.pop("reqDate", None)
                if field == "quantity":
                    order_schedule_in.pop("reqQty", None)
        order_schedules_in.append(order_schedule_in)
        order_schedules_inx.append(
            {
                "itemNo": item_no,
                "scheduleLine": "0001",
                "updateflag": sap_update_flag.get(str(line.item_no), "U"),
                "requestDate": flag_update_line["request_date"],
                "requestQuantity": flag_update_line["quantity"],
                "confirmQuantity": True,
                "deliveryBlock": True,
            }
        )
    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": order_header_in,
        "orderHeaderInX": {
            "incoterms1": flag_update["incoterms_1_id"],
            "poNo": flag_update["po_no"],
            "purchaseDate": flag_update["po_date"],
            "customerGroup1": flag_update["customer_group_1_id"],
            "customerGroup2": flag_update["customer_group_2_id"],
            "customerGroup3": flag_update["customer_group_3_id"],
            "customerGroup4": flag_update["customer_group_4_id"],
        },
        "orderPartners": order_partners,
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
    }
    order_text = prepare_param_es21_order_text_for_change_order_domestic(order, order_lines,
                                                                         order_lines_change_request_date,
                                                                         dtr_dtp_update=False)
    if order_text:
        params["orderText"] = order_text

    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
        "feature": MulesoftFeatureType.CHANGE_ORDER.value
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params,
        encode=True
    )
    return response


def sap_update_order(order, manager, sap_update_flag, order_lines_change_request_date=None, origin_order_lines=None,
                     original_order=None, updated_data=None, pre_update_lines={}, export_delete_flag=True,
                     updated_items=[]):
    """
    Call SAP ES21 to update order
    @param order:
    @param manager:
    @param sap_update_flag:
    @param order_lines_change_request_date:
    @param origin_order_lines:
    @param original_order:
    @return:
    """
    # Call SAP to update order
    sap_response = request_sap_es21(order, manager, sap_update_flag, order_lines_change_request_date,
                                    origin_order_lines, original_order, updated_data=updated_data,
                                    pre_update_lines=pre_update_lines, export_delete_flag=export_delete_flag,
                                    updated_items=updated_items)
    sap_response_success = True
    sap_order_messages = []
    sap_item_messages = []
    if sap_response.get("return"):
        for data in sap_response.get("return"):
            if data.get("type") == SAP21.FAILED.value:
                sap_response_success = False
                sap_order_messages.append(
                    {
                        "id": data.get("id"),
                        "number": data.get("number"),
                        "so_no": sap_response.get("salesdocument") or order.so_no,
                        "message": data.get("message")
                    }
                )
        for item in sap_response.get("orderItemsOut", ""):
            if item.get("itemStatus"):
                sap_item_messages.append(
                    {
                        "item_no": item.get("itemNo"),
                        "item_status": item.get("itemStatus"),
                    }
                )
    sap_warning_messages = get_sap_warning_messages(sap_response)
    return sap_response_success, sap_order_messages, sap_item_messages, sap_warning_messages


def request_sap_es27(order, manager, order_lines=None, sap_update_flag=None):
    sap_update_flag = sap_update_flag or {}
    if not order_lines:
        order_lines = sap_migration_models.OrderLines.objects.filter(order=order)

    order_schedules_in = []
    order_schedules_inx = []

    index = 1
    for line in order_lines:
        order_schedules_in.append(
            {
                "itemNumber": int(line.item_no) if line.item_no else int(line.eo_item_no),
                "scheduleLine": index,
                "ScheduleLineCatalog": "ZC",
                "requestDate": line.request_date.strftime("%d/%m/%Y"),
                "requestQuantity": line.quantity,
                "confirmQuantity": float(line.target_quantity)
                if line.target_quantity
                else 0
            }
        )
        order_schedules_inx.append(
            {
                "itemNumber": int(line.item_no) if line.item_no else int(line.eo_item_no),
                "scheduleLine": index,
                "updateFlag": sap_update_flag.get(str(line.item_no), "U"),
                "scheduleLineCatalog": "",
                # "requestDate": line.request_date.strftime('%d/%m/%Y') if line.request_date.strftime('%d/%m/%Y') else "",
                "requestDate": "X",
                # "requestQuantity": str(line.quantity) if str(line.quantity) else "",
                "requestQuantity": "X",
                "confirmQuantity": float(line.target_quantity)
                if line.target_quantity
                else 0,
                "deliveryBlock": "X",
            }
        )
        index += 1

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesDocumentIn": order.so_no,
        "orderSchedulesIn": order_schedules_in,
        "orderSchedulesInx": order_schedules_inx,
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
        SapEnpoint.ES_27.value,
        params
    )

    return response


def es27_update_order(order, manager, call_type=None, sap_update_flag=None):
    """
    Call SAP ES27 to update order
    @param order:
    @param manager:
    @param sap_update_flag:
    @param call_type: use for send mail eo upload feature
    @return:
    """
    # Call SAP to update order
    order_lines = None
    if sap_update_flag:
        order_lines = sap_migration_models.OrderLines.objects.filter(order=order, item_no__in=sap_update_flag.keys())

    sap_response = request_sap_es27(order, manager, order_lines=order_lines, sap_update_flag=sap_update_flag)
    sap_response_success = True
    sap_order_messages = []
    sap_item_messages = []
    if sap_response.get("return"):
        for data in sap_response.get("return"):
            if data.get("type").lower() == SAP27.FAILED.value.lower():
                sap_response_success = False
                sap_order_messages.append(
                    {
                        "id": data.get("id"),
                        "number": data.get("number"),
                        "so_no": sap_response.get("salesDocumentIn") or order.so_no,
                        "message": data.get("message")
                    }
                )

        for item in sap_response.get("orderItemsOut", ""):
            if item.get("itemStatus"):
                sap_item_messages.append(
                    {
                        "item_no": item.get("itemNumber"),
                        "item_status": item.get("itemStatus"),
                    }
                )
    # else:
    #     sap_response_success = False
    if (not sap_response_success) and call_type == "eo_upload":
        eo_upload_send_email_when_call_api_fail(
            manager, order, "Update", "SAP", sap_response, "sap_update"
        )
    return sap_response_success, sap_order_messages, sap_item_messages


def es_21_delete_cancel_order(success_item_from_i_plan_request, status, manager):
    """
    Call SAP to delete or cancel order items
    @param: success items after call i-plan
    @return: fail items after call SAP to handle fail case
    """
    try:
        # if one of items return fail, can not cancel/delete that order items
        success, failed, item_no_for_special_plant = [], [], []
        for item in success_item_from_i_plan_request:
            for k, v in item.items():
                if v:
                    so_no = k.zfill(10)
                    line_send_to_es_21 = OrderLines.objects.filter(item_no__in=[line for line in v], order__so_no=so_no)
                    response = call_es_21_to_delete_cancel_order(line_send_to_es_21, status, manager)
                    if response.get("return")[0].get("type") == "success":
                        origin_lines_success = copy.deepcopy(line_send_to_es_21)
                        success_item_from_es_21 = [line for line in origin_lines_success]
                        success = get_message_response(success_item_from_es_21, success)
                        if status == "Delete":
                            OrderLines.objects.filter(
                                id__in=[line.id for line in line_send_to_es_21]
                            ).delete()
                        if status == "Cancel" or status == "Cancel 93":
                            _update_cancelled_status_for_order_line(line_send_to_es_21)
                            order = Order.objects.filter(so_no=so_no).first()
                            status_en, status_thai = update_order_status(order.id)
                            order.status = status_en
                            order.status_thai = status_thai
                            order.save()
                    else:
                        message = response.get("return")[0].get("message", "")
                        fail_item_from_es_21 = [line for line in line_send_to_es_21]
                        update_attention_type_r5(fail_item_from_es_21)
                        failed = get_message_response(fail_item_from_es_21, failed, message)

        return success, failed
    except Exception as e:
        raise e


def get_message_response(list_order_lines, list_response, message=None):
    for order_line in list_order_lines:
        list_response.append(
            {
                "order_no": order_line.order.so_no,
                "item_no": order_line.item_no,
                "material_code": order_line.material_variant.code,
                "material_description": order_line.material_variant.description_th,
                "request_date": order_line.request_date,
                "confirm_date": order_line.confirmed_date,
                "confirm_quantity": order_line.iplan.iplant_confirm_quantity or "0",
                "message": message
            }
        )
    return list_response


def call_es_21_to_delete_cancel_order(line, status, manager):
    params = prepare_es_21_delete_cancel_order(line, status)
    log_val = {
        "orderid": line[0].order.id,
        "order_number": line[0].order.so_no,
        "feature": MulesoftFeatureType.DELETE_ITEM.value
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params
    )
    return response


def _update_cancelled_status_for_order_line(order_lines):
    update_lines = []
    for order_line in order_lines:
        cancelled_status = IPlanOrderItemStatus.CANCEL.value
        order_line.reject_reason = "93"
        order_line.item_status_en = cancelled_status
        order_line.item_status_th = IPlanOrderItemStatus.IPLAN_ORDER_LINES_STATUS_TH.value.get(
            cancelled_status
        )
        order_line.attention_type = None
        update_lines.append(order_line)

    OrderLines.objects.bulk_update(
        update_lines, fields=["item_status_en", "item_status_th", "reject_reason", "attention_type"]
    )


def prepare_es_21_delete_cancel_order(success_item_from_i_plan_request, status):
    sales_document_in = None
    ref_doc = None
    order_items_in = []
    order_items_inx = []

    for line in success_item_from_i_plan_request:
        order_items_in_dict = {
            "itemNo": "",
            "material": "",
            "targetQty": 0,
            "salesUnit": "ROL",
            "reasonReject": "93",
            "refDoc": "",
            "refDocIt": ""
        }
        order_items_inx_dict = {
            "itemNo": "",
            "updateflag": "U",
            "reasonReject": True
        }
        if status == "Delete":
            order_items_in_dict.pop("reasonReject")
            order_items_inx_dict["updateflag"] = "D"

        sales_document_in = line.order.so_no
        ref_doc = line.contract_material.contract_no

        order_items_in_dict["itemNo"] = line.item_no.zfill(6)
        order_items_in_dict["material"] = line.material_variant.code if line.material_variant.code else ""
        order_items_in_dict["targetQty"] = line.quantity if line.quantity else 0
        order_items_in_dict["refDoc"] = line.contract_material.contract_no
        order_items_in_dict["refDocIt"] = line.contract_material.item_no.zfill(6)

        order_items_inx_dict["itemNo"] = line.item_no.zfill(6)

        order_items_in.append(order_items_in_dict)
        order_items_inx.append(order_items_inx_dict)

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": sales_document_in,
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": ref_doc
        },
        "orderHeaderInX": {},
        "orderItemsIn": order_items_in,
        "orderItemsInx": order_items_inx
    }

    return params


def sap_change_request_date(order_lines, manager):
    order = order_lines[0].order
    sap_response = call_sap_change_request_date(order_lines, manager)
    sap_response_success = True
    sap_order_messages = []
    sap_item_messages = []
    if sap_response.get("return"):
        for data in sap_response.get("return"):
            if data.get("type") == SAP21.FAILED.value:
                sap_response_success = False
                sap_order_messages.append(
                    {
                        "id": data.get("id"),
                        "number": data.get("number"),
                        "so_no": sap_response.get("salesdocument") or order.so_no,
                        "message": data.get("message")
                    }
                )
        for item in sap_response.get("orderItemsOut", ""):
            if item.get("itemStatus"):
                sap_item_messages.append(
                    {
                        "item_no": item.get("itemNo"),
                        "item_status": item.get("itemStatus"),
                    }
                )
    return sap_response_success, sap_order_messages, sap_item_messages


def call_sap_change_request_date(order_lines, manager):
    ''' Update Request date from Confirmed date in SAP '''
    order = order_lines[0].order

    params = {
        "piMessageId": str(uuid.uuid1().int),
        "salesdocumentin": order.so_no,
        "testrun": False,
        "orderHeaderIn": {
            "refDoc": order.so_no
        },
        "orderHeaderInX": {
            "reqDate": False
        },
        "orderSchedulesIn": [
            {
                "itemNo": line.item_no.zfill(6),
                "scheduleLine": "0001",
                "reqDate": line.confirmed_date.strftime("%d/%m/%Y") if line.request_date else "",
                "reqQty": line.quantity or 0,
                "confirmQty": line.confirm_quantity or 0
            } for line in order_lines
        ],
        "orderSchedulesInx": [
            {
                "itemNo": line.item_no.zfill(6),
                "scheduleLine": "0001",
                "updateflag": "U",
                "requestDate": True,
                "requestQuantity": True,
                "confirmQuantity": True,
                "deliveryBlock": True
            } for line in order_lines
        ]
    }
    log_val = {
        "orderid": order.id,
        "order_number": order.so_no,
        "feature": MulesoftFeatureType.CHANGE_ORDER.value
    }
    response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value, **log_val).request_mulesoft_post(
        SapEnpoint.ES_21.value,
        params,
        encode=True
    )
    return response


def resolve_plant(need_invoke_iplan, line, order, ui_order_lines_info=None):
    if not need_invoke_iplan and ui_order_lines_info:
        logging.debug(f"resolving plant  group for{order.order_no}  from UI as ")
        if line and line.id:
            data = ui_order_lines_info.get(str(line.id))
            if data and data.get("plant"):
                return data.get("plant")
            else:
                logging.error(f" Plant information came as Null for {order.order_no}")
                return data.get("plant")
        else:
            logging.error(f"Line information has come as Null/ Id not valid for {order.order_no}")
    else:
        return line.plant or None


def resolve_qty_from_ui_or_iplan(need_invoke_iplan, line, order, ui_order_lines_info):
    if not need_invoke_iplan and ui_order_lines_info:
        logging.debug(f"resolving confirming Quantity for{order.order_no}  from UI as ")
        if line and line.id:
            data = ui_order_lines_info.get(str(line.id))
            if data and data.get("quantity"):
                qty = data.get("quantity")
            else:
                logging.error(f" quantity information came as Null for {order.order_no} from UI. Returning null")
                qty = data.get("quantity")
            return round_qty_decimal(qty)
        else:
            logging.error(
                f" Missing Quantity information came as Null for {order.order_no} from UI. for line {line.id}")
    else:
        return round_qty_decimal(line.quantity)


def resolve_confirm_qty(need_invoke_iplan, line, order, ui_order_lines_info=None):
    # https://scgdigitaloffice.atlassian.net/wiki/spaces/SN/pages/657424387/ES17+request+payload+related
    if OrderType.DOMESTIC.value == order.type:
        confirm_quantity = resolve_qty_from_ui_or_iplan(need_invoke_iplan, line, order, ui_order_lines_info)
        if need_invoke_iplan and not line.i_plan_on_hand_stock:
            confirm_quantity = 0
        return round_qty_decimal(confirm_quantity)
    if line.i_plan_on_hand_stock:
        confirm_quantity = line.quantity
    else:
        confirm_quantity = 0
    if OrderType.EXPORT.value == order.type:
        material_plant = line.contract_material and line.contract_material.plant or ""
        if line.item_cat_eo == ItemCat.ZKC0.value or material_plant in MaterialType.MATERIAL_OS_PLANT.value:
            confirm_quantity = line.quantity
    return round_qty_decimal(confirm_quantity)


def resolve_material_no(need_invoke_iplan, line, order, ui_order_lines_info=None):
    if not need_invoke_iplan and ui_order_lines_info:
        logging.debug(f"resolving sale unit  for{order.order_no}  from UI as ")
        if line and line.id:
            data = ui_order_lines_info.get(str(line.id))
            if data and data.get("material_no"):
                return data.get("material_no")
            else:
                logging.error(f" material_no information came as Null for {order.order_no} from UI")
                return data.get("material_no")

        else:
            logging.eror(f"missing material_no for{order.order_no}  from UI for line id {line.id}")
    else:
        return line.material_variant and line.material_variant.code or line.material_code or ""


def resolve_sales_unit(need_invoke_iplan, line, order, ui_order_lines_info=None):
    # https://scgdigitaloffice.atlassian.net/wiki/spaces/SN/pages/657424387/ES17+request+payload+related
    if OrderType.DOMESTIC.value == order.type:
        if not need_invoke_iplan:
            logging.debug(f"resolving sale unit  for{order.order_no}  from UI as ")
            if line and line.id:
                data = ui_order_lines_info.get(str(line.id))
                if data and data.get("unit"):
                    return data.get("unit")
                else:
                    logging.error(
                        f" sale unit information came as Null for {order.order_no} from UI. Returning ROL as default")
                    return 'ROL'
            else:
                logging.eror(f"missing sale unit  for{order.order_no}  from UI for line id {line.id}")
        else:
            sale_unit = line.sales_unit
    elif OrderType.CUSTOMER.value == order.type:
        sale_unit = 'ROL'
    else:
        sale_unit = line.contract_material.weight_unit if line.contract_material else ""
        if OrderType.EXPORT.value == order.type:
            if order.eo_upload_log:
                sale_unit = line.quantity_unit
            else:
                if line.item_cat_eo != ItemCat.ZKC0.value:
                    sale_unit = 'ROL'
    return sale_unit


def handle_lines_to_request_es17(need_invoke_iplan, line, order, request_items, request_schedules, request_texts,
                                 contract_details, ui_order_lines_info=None):
    # make it work with eo upload
    sale_unit = resolve_sales_unit(need_invoke_iplan, line, order, ui_order_lines_info=ui_order_lines_info)
    roll_diameter = line.roll_diameter or ""
    roll_core_diameter = line.roll_core_diameter or ""
    no_of_rolls = line.roll_quantity or ""
    ream_roll_per_pallet = line.roll_per_pallet or ""
    pallet_size = line.pallet_size or ""
    pallet_no = line.pallet_no or ""
    no_of_package = line.package_quantity or ""
    packing_list = line.packing_list or ""
    remark = line.remark or ""
    shipping_mark = line.shipping_mark or ""
    item_category = line.item_cat_eo if line.order.type == "export" else line.item_category

    # TODO: make it faster / optimize it
    def _search_ref_doc_it(mat_code, mat_type, ref_doc_it=None):
        if not mat_code:
            return ""
        for contract_detail in contract_details or []:
            items = contract_detail and contract_detail.get("contractItem") or []
            if not items:
                continue
            for item in items:
                if item.get("matNo", "") == mat_code and item.get("matType", "") == mat_type:
                    if ref_doc_it:
                        if ref_doc_it.zfill(6) == item.get("itemNo", ""):
                            return ref_doc_it.zfill(6)
                    else:
                        return item.get("itemNo", "")
        return ""

    internal_comments_to_warehouse = line.internal_comments_to_warehouse or order.internal_comment_to_warehouse
    external_comments_to_customer = line.external_comments_to_customer
    item_no = str(line.item_no or line.eo_item_no)
    if order.eo_upload_log or order.po_number:
        item_no = item_no.zfill(6)
    mat_code = resolve_material_no(need_invoke_iplan, line, order, ui_order_lines_info)
    mat_type = line.material_variant and line.material_variant.type or ""

    if order.type == OrderType.CUSTOMER.value:
        ref_doc_it = line.contract_material and line.contract_material.item_no or ""
    else:
        '''
            Check ES 14 response for  
            1. Use Mat Variant, Mat type to check and compare with refDocIt if not null else return the first item found
            2. If not found, then Use Contract Mat Code, Mat type to check and compare item no with refDocIt if not null 
                else return the first item found
            3. If not found then use Line.Contract.ItemNo
        '''
        line_ref_doc_it = line.ref_doc_it
        ref_doc_it = _search_ref_doc_it(mat_code, mat_type, line_ref_doc_it)
        if not ref_doc_it:
            _line_contract_mat_code = line.contract_material and line.contract_material.material_code or ""
            ref_doc_it = _search_ref_doc_it(_line_contract_mat_code, mat_type, line_ref_doc_it)
            if not ref_doc_it:
                ref_doc_it = line.contract_material and line.contract_material.item_no or ""

    request_items_base = {
        "itemNo": item_no,
        "materialNo": mat_code,
        "targetQty": resolve_qty_from_ui_or_iplan(need_invoke_iplan, line, order, ui_order_lines_info),
        "salesUnit": sale_unit or "ROL",
        "plant": resolve_plant(need_invoke_iplan, line, order, ui_order_lines_info),
        "shippingPoint": line.shipping_point or "",
        "route": line.route.split("-")[0].strip() if line.route else "",
        "itemCategory": item_category or "",
        "poDate": line.original_request_date.strftime('%d/%m/%Y') if line.original_request_date else "",
        "refDoc": order.contract.code if order.contract else "",
        # eoupload: refDocIt == item_no == eo_item_no
        "refDocIt": item_no if order.eo_upload_log else ref_doc_it
    }
    if line.order.type == "domestic":
        request_items_base.pop("shippingPoint")
    if line.condition_group1 and len(line.condition_group1) > 1:
        # XXX: only 2 chars
        request_items_base["conditionGroup1"] = line.condition_group1[:2].strip()

    confirm_quantity = resolve_confirm_qty(need_invoke_iplan, line, order, ui_order_lines_info=ui_order_lines_info)

    request_items.append(request_items_base)
    order_line_i_plan = line.iplan
    '''
    For Special Plants/Containers order_line_i_plan is empty hence didn't segregate the logic of dispatch date
    '''
    request_date = line.request_date
    dispatch_date = order_line_i_plan.iplant_confirm_date if order_line_i_plan and order_line_i_plan.iplant_confirm_date else None
    if not dispatch_date:
        dispatch_date_str = mock_confirm_date(request_date, order_line_i_plan.item_status)
        dispatch_date = DateHelper.iso_str_to_obj(dispatch_date_str) if dispatch_date_str else ""
    request_schedules.append(
        {
            "itemNo": item_no,
            "reqDate": dispatch_date.strftime(
                "%d/%m/%Y") if dispatch_date and dispatch_date != request_date else request_date.strftime("%d/%m/%Y"),
            "reqQty": resolve_qty_from_ui_or_iplan(need_invoke_iplan, line, order, ui_order_lines_info),
            "confirmQty": confirm_quantity
        }
    )
    ignore_blank = False
    if order.type == OrderType.CUSTOMER.value:
        ignore_blank = True
        del request_items_base["route"]
        del request_items_base["itemCategory"]
        del request_items_base["shippingPoint"]
    if order.eo_upload_log_id:
        ignore_blank = True

    if OrderType.EXPORT.value != order.type or order.eo_upload_log:
        refDocIt = get_ref_doc_it_from_item_no(item_no, request_items)

        handle_request_text_to_es17(request_texts, internal_comments_to_warehouse, item_no, TextID.ITEM_ICTW.value,
                                    ignore_blank,
                                    get_lang_by_order_text_lang_db(order.contract, TextID.ITEM_ICTW.value, refDocIt))
        if not order.eo_upload_log:
            handle_request_text_to_es17(request_texts, external_comments_to_customer, item_no, TextID.ITEM_ECTC.value,
                                        ignore_blank,
                                        get_lang_by_order_text_lang_db(order.contract, TextID.ITEM_ECTC.value, item_no))

        if OrderType.DOMESTIC.value != order.type:
            handle_request_text_to_es17(request_texts, roll_diameter, item_no, TextID.MATERIAL_ITEM_ROLL_DIAMETER.value,
                                        ignore_blank,
                                        get_order_text_language(contract_details, order
                                                                , TextID.MATERIAL_ITEM_ROLL_DIAMETER.value))

            handle_request_text_to_es17(request_texts, roll_core_diameter, item_no,
                                        TextID.MATERIAL_ITEM_ROLL_CORE_DIAMETER.value,
                                        ignore_blank,
                                        get_order_text_language(contract_details, order,
                                                                TextID.MATERIAL_ITEM_ROLL_CORE_DIAMETER.value))

            handle_request_text_to_es17(request_texts, no_of_rolls, item_no, TextID.MATERIAL_ITEM_NO_OF_ROLLS.value,
                                        ignore_blank,
                                        get_order_text_language(contract_details, order,
                                                                TextID.MATERIAL_ITEM_NO_OF_ROLLS.value))

            handle_request_text_to_es17(request_texts, ream_roll_per_pallet, item_no,
                                        TextID.MATERIAL_ITEM_REAM_ROLL_PER_PALLET.value,
                                        ignore_blank,
                                        get_order_text_language(contract_details, order,
                                                                TextID.MATERIAL_ITEM_REAM_ROLL_PER_PALLET.value))

            handle_request_text_to_es17(request_texts, pallet_size, item_no, TextID.MATERIAL_ITEM_PALLET_SIZE.value,
                                        ignore_blank, get_order_text_language(contract_details, order,
                                                                              TextID.MATERIAL_ITEM_PALLET_SIZE.value))

            handle_request_text_to_es17(request_texts, pallet_no, item_no, TextID.MATERIAL_ITEM_PALLET_NO.value,
                                        ignore_blank,
                                        get_order_text_language(contract_details, order,
                                                                TextID.MATERIAL_ITEM_PALLET_NO.value))

            handle_request_text_to_es17(request_texts, no_of_package, item_no, TextID.MATERIAL_ITEM_NO_OF_PACKAGE.value,
                                        ignore_blank, get_order_text_language(contract_details, order,
                                                                              TextID.MATERIAL_ITEM_NO_OF_PACKAGE.value))

            handle_request_text_to_es17(request_texts, packing_list, item_no, TextID.MATERIAL_ITEM_PACKING_LIST.value,
                                        ignore_blank, get_order_text_language(contract_details, order,
                                                                              TextID.MATERIAL_ITEM_PACKING_LIST.value))

    if OrderType.EXPORT.value == order.type and order.eo_upload_log is None:
        handle_request_text_to_es17(request_texts, remark, item_no, TextID.ITEM_REMARK.value,
                                    ignore_blank,
                                    get_order_text_language(contract_details, order,
                                                            TextID.ITEM_REMARK.value))
    handle_request_text_to_es17(request_texts, shipping_mark, item_no, TextID.ITEM_SHIPPING_MARK.value,
                                ignore_blank,
                                get_order_text_language(contract_details, order,
                                                        TextID.ITEM_SHIPPING_MARK.value))
    return request_items, request_schedules, request_texts


def get_ref_doc_it_from_item_no(item_no, request_items):
    refDocIt = None
    for request_item in request_items:
        if request_item.get("itemNo") == item_no:
            refDocIt = request_item.get('refDocIt')
            continue
    return refDocIt


def handle_request_text_to_es17(request_texts, text_lines, item_no, text_id, ignore_blank=False,
                                language=LanguageCode.EN.value):
    text_line = None
    if isinstance(text_lines, str) and len(text_lines) > 0:
        text_line = text_lines.split("\n")
    elif isinstance(text_lines, datetime):
        text_line = [date_to_sap_date(text_lines, "%d%m%Y")]
    elif isinstance(text_lines, (int, float)):
        text_line = [str(text_lines)]
    if not text_line:
        if ignore_blank:
            return
        text_line = [" "]

    request_text = {
        "itemNo": item_no,
        "textId": text_id,
        "textLines": [
            {"textLine": item}
            for item in text_line
        ],
    }
    if language is not None:
        request_text = add_item_to_dict_with_index(request_text, "textLines", "language", language)

    request_texts.append(request_text)


def date_to_sap_date(value, target_fmt="%d%m%Y"):
    if not value:
        return None
    date = value
    if isinstance(value, str):
        format_dates = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d%m%Y"]
        for fmt in format_dates:
            try:
                date = datetime.strptime(value, fmt)
                # str_date = date.strftime("%Y-%m-%d")
                break
            except Exception:
                continue
    if isinstance(date, datetime):
        return date.strftime(target_fmt)
    return value


def get_order_partner_for_es21(order):
    order_partners = []
    mapping_addresses = {
        "WE": str(order.ship_to).split(" - ")[0] or "",
        "RE": str(order.bill_to or "").split(" - ")[0] or "",
    }
    for partner_role, partner_no in mapping_addresses.items():
        if not partner_no:
            continue
        order_partners.append(
            {
                "partnerRole": partner_role,
                "partnerNumb": partner_no,
                "itemNo": "000000"
            }
        )
    return order_partners


def get_sap_warning_messages(sap_response):
    warning_messages = []
    # es17
    if sap_response.get("creditStatusCode") == "B":
        order_no = sap_response.get("salesdocument")
        warning_message = sap_response.get("creditStatusText")
        warning_messages.append({
            "source": "sap",
            "order": order_no,
            "message": warning_message
        })
    # es21
    elif sap_response.get("creditStatus") == "B":
        order_no = sap_response.get("salesdocument")
        warning_message = sap_response.get("creditStatustxt")
        warning_messages.append({
            "source": "sap",
            "order": order_no,
            "message": warning_message
        })
    return warning_messages


def get_excel_upload_order_level_error_message(order_item_message, sap_order_messages, order_lines):
    sap_item_msg = {}
    for item in order_lines:
        item_msg = order_item_message.get(item.item_no)
        error_message = "\n".join(sap_order_messages) if len(sap_order_messages) > 0 else ""
        sap_item_msg[item.item_no] = error_message + f"\n{item_msg}" if item_msg else error_message
    return sap_item_msg


def get_error_messages_from_sap_response_for_create_order(sap_response, dict_order_lines=None, file_upload=False,
                                                          is_excel_upload=False):
    error_msg_order_header = load_error_message()
    sap_errors_code = []
    is_items_error = False
    sap_order_messages = []
    sap_item_messages = []
    sap_success = True
    order_header_msgs = []
    order_item_msgs = {}
    is_being_process = False
    if sap_response.get("data"):
        for data in sap_response.get("data"):
            if data.get("type").lower() == SapType.ERROR.value:
                sap_success = False
                error_code = data.get("number", "")
                item_no = data.get("itemNo").lstrip("0") if data.get("itemNo") else None
                if not file_upload:
                    (is_being_process) = handle_sap_response_create_order_normal(item_no, error_code,
                                                                                 data.get("message", ""),
                                                                                 data, sap_response, sap_item_messages,
                                                                                 sap_order_messages)
                else:
                    (is_being_process,
                     is_items_error) = handle_sap_response_create_order_upload(item_no, error_code,
                                                                               sap_response, data,
                                                                               error_msg_order_header,
                                                                               dict_order_lines, sap_item_messages,
                                                                               order_header_msgs, sap_order_messages,
                                                                               sap_errors_code, order_item_msgs,
                                                                               is_excel_upload)
    order_header_msg = list(set(order_header_msgs))
    return (
        sap_success,
        sap_order_messages,
        sap_item_messages,
        sap_errors_code,
        order_header_msg,
        is_being_process,
        is_items_error,
        order_item_msgs
    )


def handle_sap_response_create_order_normal(item_no, error_code, error_message, data, sap_response, sap_item_messages,
                                            sap_order_messages):
    is_being_process = False
    if item_no and error_code != BeingProcessConstants.BEING_PROCESS_CODE:
        (error_code, error_message) = check_thai_message_in_message_error_item(
            sap_response.get("orderItemsOut", []), item_no, error_code, error_message)
        if not error_message:
            error_message = data.get("message", "")
        sap_item_messages.append(
            {
                "item_no": item_no,
                "error_code": error_code,
                "error_message": error_message
            }
        )
    else:
        message = data.get("message", "")
        if error_code == BeingProcessConstants.BEING_PROCESS_CODE:
            is_being_process = True
        sap_order_messages.append(
            {
                "error_code": data.get("number", ""),
                "so_no": sap_response.get("salesdocument"),
                "error_message": message
            }
        )
    return is_being_process


def handle_sap_response_create_order_upload(item_no, error_code, sap_response, data, error_msg_order_header,
                                            dict_order_lines,
                                            sap_item_messages, order_header_msgs, sap_order_messages,
                                            sap_errors_code, order_item_msgs, is_excel_upload):
    is_items_error = False
    is_being_process = False
    if item_no and error_code != BeingProcessConstants.BEING_PROCESS_CODE:
        is_items_error = True
        error_message = item_level_error_formatting(
            sap_response.get("orderItemsOut", []),
            data,
            item_no,
            error_msg_order_header,
            is_excel_upload
        )
        if not order_item_msgs.get(item_no):
            order_item_msgs[item_no] = error_message
        if not is_excel_upload:
            order_line = dict_order_lines.get(item_no)
            mat_description = (
                get_material_description_from_order_line(order_line)
            )
            if mat_description:
                error_message = f"{mat_description} {error_message}"
        if error_message not in sap_item_messages:
            sap_item_messages.append(error_message)
    else:
        message = data.get("message", "")
        validate_order_msg(data, error_msg_order_header, order_header_msgs)
        if error_code == BeingProcessConstants.BEING_PROCESS_CODE:
            is_being_process = True
            message = (check_thai_message_in_error_messages_order_header(data, error_msg_order_header)
                       or data.get("message"))
        error_message = f"{data.get('id')} {data.get('number')} {message}"
        if error_message not in sap_order_messages:
            sap_order_messages.append(error_message)
    sap_errors_code.append(error_code)
    return is_being_process, is_items_error


def format_error_massage(order_header_response, order_header_msg):
    message_v1 = order_header_response.get("messageV1", "")
    message_v2 = order_header_response.get("messageV2", "")
    message_v3 = order_header_response.get("messageV3", "")
    message_v4 = order_header_response.get("messageV4", "")
    order_header_msg = order_header_msg.replace(DYNAMIC_VALUE1, message_v1)
    order_header_msg = order_header_msg.replace(DYNAMIC_VALUE2, message_v2)
    order_header_msg = order_header_msg.replace(DYNAMIC_VALUE3, message_v3)
    order_header_msg = order_header_msg.replace(DYNAMIC_VALUE4, message_v4)
    if DYNAMIC_VALUE in order_header_msg:
        message_list = [message_v1, message_v2, message_v3, message_v4]
        for message in message_list:
            order_header_msg = order_header_msg.replace("&", message, 1)
    return order_header_msg


def item_level_error_formatting(sap_order_items_out, sap_data, item_no, error_msg_order_header, is_excel_upload):
    message = ""
    error_code = sap_data.get("number", "")
    (error_code, message) = check_thai_message_in_message_error_item(
        sap_order_items_out, item_no, error_code, message)
    if not message:
        message = (check_thai_message_in_error_messages_order_header(sap_data, error_msg_order_header)
                   or sap_data.get("message"))
    error_message = (
        message
        if re.match("E\\d", message)
        else (
            f"{error_code} {message}"
            if not is_excel_upload
            else f"{error_code}:{message}"
        )
    )
    return error_message


def check_thai_message_in_message_error_item(sap_order_items_out, item_no, error_code, error_message):
    for order_items_out in sap_order_items_out:
        if order_items_out.get("itemStatus") and item_no == order_items_out.get("itemNo").lstrip("0"):
            error_code = order_items_out.get("itemStatus")
            error_message = MessageErrorItem.ITEM_LEVEL_ERROR_MESSAGE.get(error_code)
            break
    return error_code, error_message


def check_thai_message_in_error_messages_order_header(sap_data, error_msg_order_header):
    msg_id, msg_number = sap_data.get("id"), sap_data.get("number")
    message_format = error_msg_order_header.get(msg_id, {}).get(msg_number, None)
    if message_format:
        message = format_error_massage(sap_data, message_format)
        return message


def get_material_description_from_order_line(order_line):
    try:
        material = sap_master_data_models.MaterialMaster.objects.filter(
            material_code=order_line.material_variant.code
        ).first()
        return material.description_en
    except Exception:
        return ""


def get_error_messages_from_sap_response_for_change_order(sap_response):
    sap_order_messages = []
    sap_item_messages = []
    is_being_process = False
    sap_success = True
    if not sap_response.get("return"):
        return sap_order_messages, sap_item_messages, is_being_process, sap_success

    for data in sap_response.get("return", []):
        if data.get("type").lower() == SapType.ERROR.value:
            sap_success = False
            error_message = data.get("message", "")
            error_code = data.get("number", "")
            item_no = data.get("itemNo").lstrip("0") if data.get("itemNo") else None
            if item_no and error_code != BeingProcessConstants.BEING_PROCESS_CODE:
                sap_item_messages.append(
                    {
                        "item_no": item_no,
                        "error_code": error_code,
                        "error_message": error_message
                    }
                )
            else:
                if error_code == BeingProcessConstants.BEING_PROCESS_CODE:
                    is_being_process = True
                sap_order_messages.append(
                    {
                        "error_code": error_code,
                        "so_no": sap_response.get("salesdocument", ""),
                        "error_message": error_message
                    }
                )
    return sap_order_messages, sap_item_messages, is_being_process, sap_success
