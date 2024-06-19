import random
from datetime import datetime

import sap_master_data.models
from sap_migration import models as sap_migration_models
from sap_migration.graphql.enums import CreatedFlow
from scg_checkout.graphql.enums import (
    RealtimePartnerType,
    ScgOrderStatus,
    WeightUnitEnum,
)
from scgp_cip.common.constants import (
    EXCEL_HEADER_DOMESTIC,
    FORCE_FLAG_VALUES,
    HEADER_DOMESTIC,
    HEADER_ORDER_KEY,
    ITEM_NOTE_WHEN_NOT_PRODUCED,
    MAPPING_HEADER_ADDITIONAL_FIELDS,
    MAPPING_HEADER_ADDITIONAL_FIELDS_EXCEL_UPLOAD,
    MAPPING_ITEM_ADDITIONAL_FIELDS,
    MAPPING_ITEM_ADDITIONAL_FIELDS_EXCEL_UPLOAD,
    SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX,
    WARNING_CREDIT_STATUSES,
)
from scgp_cip.common.enum import (
    CIPOrderPaymentType,
    ItemCat,
    MaterialTypes,
    OrderType,
    ProductionFlag,
    ScheduleLineCategory,
)
from scgp_cip.common.helper.helper import (
    add_key_and_data_into_params,
    get_random_number,
)
from scgp_cip.dao.order.distribution_channel_master_repo import (
    DistributionChannelMasterRepo,
)
from scgp_cip.dao.order.division_master_repo import DivisionMasterRepo
from scgp_cip.dao.order.sale_organization_master_repo import SalesOrganizationMasterRepo
from scgp_cip.dao.order.sold_to_master_repo import SoldToMasterRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line.material_sale_master_repo import MaterialSaleMasterRepo
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo
from scgp_cip.graphql.order.types import (
    CipTempOrder,
    CPItemMessage,
    SapItemMessages,
    SapOrderMessages,
    WarningMessages,
)
from scgp_po_upload.implementations.excel_upload_validation import is_valid_date

cip_order_line_update_fields = [
    "item_no",
    "material_id",
    "po_no_external",
    "po_no",
    "plant",
    "quantity",
    "net_price",
    "request_date",
    "internal_comments_to_warehouse",
    "product_information",
    "type",
    "weight",
    "weight_unit",
    "total_weight",
    "price_per_unit",
    "price_currency",
    "sales_unit",
    "delivery_tol_over",
    "delivery_tol_under",
    "payment_term_item",
    "additional_remark",
]


def prepare_order_for_cip_create(info, order_information, order_organization_data):
    sold_to_code = order_information.get("sold_to_code")
    sold_to_master = sap_master_data.models.SoldToMaster.objects.filter(
        sold_to_code=sold_to_code
    ).first()
    if sold_to_master:
        sold_to_id = sold_to_master.id
    else:
        raise ValueError(f"Invalid Customer Id: {sold_to_code}")

    order = sap_migration_models.Order(
        status="",
        sold_to_id=sold_to_id,
        sold_to_code=sold_to_code,
        created_by=info.context.user,
        payment_term=order_information.get("payment_term"),
        currency=order_information.get("currency"),
        dp_no=f"01{int(datetime.now().timestamp() * 2 / 100)}",
        invoice_no=f"01{int(datetime.now().timestamp())}",
        # company=company,
        po_date=order_information.get("po_date"),
        po_number=order_information.get("po_number"),
        po_no=order_information.get("po_number"),
        ship_to=order_information.get("ship_to"),
        bill_to=order_information.get("bill_to"),
        order_type=order_information.get("order_type"),
        request_date=order_information.get("request_date"),
        external_comments_to_customer=order_information.get(
            "external_comments_to_customer"
        ),
        internal_comments_to_warehouse=order_information.get(
            "internal_comments_to_warehouse"
        ),
        internal_comments_to_logistic=order_information.get(
            "internal_comments_to_logistic"
        ),
        product_information=order_information.get("product_information"),
        shipping_point=order_information.get("shipping_point"),
        route=order_information.get("route"),
        delivery_block=order_information.get("delivery_block"),
        sales_organization_id=order_organization_data.get("sale_organization_id"),
        distribution_channel_id=order_organization_data.get("distribution_channel_id"),
        division_id=order_organization_data.get("division_id"),
        sales_group_id=order_organization_data.get("sale_group_id"),
        sales_office_id=order_organization_data.get("sale_office_id"),
        sales_employee=order_organization_data.get("sales_employee"),
        unloading_point=order_information.get("unloading_point"),
    )

    orderExtn = sap_migration_models.OrderExtension(
        order=order,
        bu=order_organization_data.get("bu"),
        # otc_sold_to = OrderOtcPartner
        # otc_bill_to = OrderOtcPartner
        # otc_ship_to = OrderOtcPartner
        tax_class=order_information.get("tax_class"),
        additional_txt_from_header=order_information.get("from_header"),
        additional_txt_header_note1=order_information.get("header_note1"),
        additional_txt_cash=order_information.get("cash"),
    )
    return order, orderExtn


def prepare_orderline_for_cip_create(order, order_line, channel_master):
    material = MaterialMasterRepo.get_material_by_material_code(
        order_line.get("material_no")
    )
    sales = MaterialSaleMasterRepo.get_material_sale_master_by_material_code(
        material.material_code,
        channel_master.sales_organization_code,
        channel_master.distribution_channel_code,
    )
    weight = order_line.get("weight") or None  # TODO
    quantity = order_line.get("quantity")

    line = sap_migration_models.OrderLines(
        order_id=order.pk,
        prc_group_1=sales.material_group1,
        item_no=order_line.get("item_no"),
        po_no_external=random.randint(10000, 99999),
        po_no=order.po_no,
        material_id=material.id,
        material_code=material.material_code,
        plant=order_line.get("plant"),
        quantity=order_line.get("quantity"),
        original_quantity=order_line.get("quantity"),
        net_price=order_line.get("net_price"),
        request_date=order_line.get("request_date", None),
        internal_comments_to_warehouse=order_line.get(
            "internal_comments_to_warehouse", ""
        ),
        product_information=order_line.get("product_information", ""),
        type=order.type,
        weight=weight,
        weight_unit=WeightUnitEnum.TON.value,
        total_weight=weight * quantity if weight else None,
        price_per_unit=order_line.get("price_per_unit"),  # TODO
        price_currency=order_line.get("price_currency"),  # TODO
        sales_unit=order_line.get("unit") or sales.sales_unit,
        sap_confirm_status=None,
        delivery_tol_over=order_line.get("delivery_tol_over")
        or channel_master.over_delivery_tol
        if channel_master
        else None,
        delivery_tol_under=order_line.get("delivery_tol_under")
        or channel_master.under_delivery_tol
        if channel_master
        else None,
        payment_term_item=order_line.get("payment_term_item") or order.payment_term,
        additional_remark=order_line.get("additional_remark"),
        production_flag=order_line.get("production_flag", "ผลิต"),
    )
    return line


def prepare_order_for_cip_update(
    info, order, order_extn, order_information, order_organization_data
):
    order.po_date = order_information.get("po_date", order.po_date)
    order.po_number = order_information.get("po_number", order.po_number)
    order.po_no = order_information.get("po_number", order.po_number)
    order.order_type = order_information.get("order_type", order.order_type)
    order.payment_term = order_information.get("payment_term", order.payment_term)
    order.request_date = order_information.get("request_date", order.request_date)
    order.ship_to = order_information.get("ship_to", order.ship_to)
    order.bill_to = order_information.get("bill_to", order.bill_to)
    order.sold_to_code = order_information.get("sold_to_code", order.sold_to_code)
    order.unloading_point = order_information.get(
        "unloading_point", order.unloading_point
    )

    order.external_comments_to_customer = order_information.get(
        "external_comments_to_customer", order.external_comments_to_customer
    )
    order.internal_comments_to_warehouse = order_information.get(
        "internal_comments_to_warehouse", order.internal_comments_to_warehouse
    )
    order.internal_comments_to_logistic = order_information.get(
        "internal_comments_to_logistic", order.internal_comments_to_logistic
    )
    order.product_information = order_information.get(
        "product_information", order.product_information
    )
    order.shipping_point = order_information.get("shipping_point", order.shipping_point)
    order.route = order_information.get("route", order.route)
    order.delivery_block = order_information.get("delivery_block", order.delivery_block)

    order.sales_organization_id = order_organization_data.get(
        "sale_organization_id", order.sales_organization_id
    )
    order.distribution_channel_id = order_organization_data.get(
        "distribution_channel_id", order.distribution_channel_id
    )
    order.division_id = order_organization_data.get("division_id", order.division_id)
    order.sales_group_id = order_organization_data.get(
        "sale_group_id", order.sales_group_id
    )
    order.sales_office_id = order_organization_data.get(
        "sale_office_id", order.sales_office_id
    )
    order.sales_employee = order_organization_data.get(
        "sales_employee", order.sales_employee
    )
    order_extn.tax_class = order_information.get("tax_class", order_extn.tax_class)
    order_extn.additional_txt_from_header = order_information.get(
        "from_header", order_extn.additional_txt_from_header
    )
    order_extn.additional_txt_header_note1 = order_information.get(
        "header_note1", order_extn.additional_txt_header_note1
    )
    order_extn.additional_txt_cash = order_information.get(
        "cash", order_extn.additional_txt_cash
    )

    return order, order_extn


def prepare_orderline_for_cip_update(
    order, order_line, order_line_input, order_item_map
):
    # Check if order_line_input represents a child order line
    if order_line_input.get("bom_material_id"):
        # Get the parent order line from the order_item_map
        parent_order_line = order_item_map.get(order_line_input["bom_material_id"])
        if parent_order_line:
            # Update the fields of the child order line with the values from the parent
            for key, value in parent_order_line.items():
                if key != "price_per_unit" and (
                    order_line_input.get(key) is None or order_line_input.get(key) == ""
                ):
                    order_line_input[key] = value

    # Update fields of the order line with the corresponding values from order_line_input
    order_line.item_no = order_line_input.get("item_no")
    order_line.po_no_external = order_line_input.get(
        "po_no_external", order_line.po_no_external
    )
    order_line.po_no = order_line_input.get("po_no", order.po_no)
    order_line.plant = order_line_input.get("plant")
    quantity = order_line_input.get("quantity")
    order_line.quantity = quantity
    order_line.original_quantity = quantity
    order_line.net_price = order_line_input.get("net_price")
    request_date = order_line_input.get("request_date", None)
    order_line.request_date = request_date
    order_line.original_request_date = request_date
    order_line.internal_comments_to_warehouse = order_line_input.get(
        "internal_comments_to_warehouse", order_line.internal_comments_to_warehouse
    )
    order_line.product_information = order_line_input.get(
        "product_information", order_line.product_information
    )
    weight = order_line_input.get("weight")
    order_line.weight = weight or order_line.weight
    order_line.weight_unit = (
        order_line_input.get("weight_unit", order_line.weight_unit)
        or WeightUnitEnum.TON.value
    )
    order_line.total_weight = weight * quantity if weight else None
    order_line.price_per_unit = order_line_input.get(
        "price_per_unit", order_line.price_per_unit
    )
    order_line.price_currency = order_line_input.get(
        "price_currency", order_line.price_currency
    )
    order_line.sales_unit = order_line_input.get("unit", order_line.sales_unit)
    order_line.delivery_tol_over = order_line_input.get(
        "delivery_tol_over", order_line.delivery_tol_over
    )
    order_line.delivery_tol_under = order_line_input.get(
        "delivery_tol_under", order_line.delivery_tol_under
    )
    order_line.payment_term_item = order_line_input.get(
        "payment_term_item", order_line.payment_term_item
    )
    order_line.additional_remark = order_line_input.get(
        "additional_remark", order_line.additional_remark
    )
    order_line.remark = order_line_input.get("remark", order_line.remark)
    order_line.batch_choice_flag = order_line_input.get(
        "batch_choice_flag", order_line.batch_choice_flag
    )

    order_line.price_date = order_line_input.get("price_date", order_line.price_date)
    order_line.po_item_no = order_line_input.get("po_item_no", order_line.po_item_no)
    order_line.production_flag = order_line_input.get(
        "production_flag", order_line.production_flag
    )
    order_line.external_comments_to_customer = order_line_input.get(
        "external_comments_to_customer", order_line.external_comments_to_customer
    )
    order_line.sale_text1 = order_line_input.get("sale_text1", order_line.sale_text1)
    order_line.sale_text2 = order_line_input.get("sale_text2", order_line.sale_text2)
    order_line.sale_text3 = order_line_input.get("sale_text3", order_line.sale_text3)
    order_line.sale_text4 = order_line_input.get("sale_text4", order_line.sale_text4)
    order_line.item_note = order_line_input.get("item_note", order_line.item_note)
    order_line.pr_item_text = order_line_input.get(
        "pr_item_text", order_line.pr_item_text
    )
    order_line.lot_no = order_line_input.get("lot_no", order_line.lot_no)
    order_line.production_memo = order_line_input.get(
        "production_memo", order_line.production_memo
    )
    order_line.batch_no = order_line_input.get("batch_no", order_line.batch_no)
    order_line.ship_to = order_line_input.get("ship_to", order_line.ship_to)

    return order_line


def derive_order_partners(
    sold_to_code,
    sales_employee,
    bill_to,
    ship_to,
    item_ship_to_dict,
    item_otc_dict=None,
    order_otc_partners=None,
    payer=None,
):
    order_partners = []
    partner_role_address_code_dict = {}
    if order_otc_partners:
        for order_otc_partner in order_otc_partners:
            partner_role = order_otc_partner.partner_role
            address_code = order_otc_partner.address.address_code
            partner_role_address_code_dict[partner_role] = address_code
    header_full_ship_to = str(ship_to)
    header_ship_to = (str(ship_to or "").strip().split("-")[0] or "").strip()
    mapping_addresses = {
        RealtimePartnerType.SHIP_TO.value: header_ship_to,
        RealtimePartnerType.SOLD_TO.value: (str(sold_to_code)).strip(),
        RealtimePartnerType.BILL_TO.value: (
            str(bill_to or "").strip().split("-")[0] or ""
        ).strip(),
        RealtimePartnerType.SALE_EMPLOYEE.value: (
            str(sales_employee or "").strip().split("-")[0] or ""
        ).strip(),
        RealtimePartnerType.PAYER.value: (
            str(payer or "").strip().split("-")[0] or ""
        ).strip(),
    }
    for partner_role, partner_no in mapping_addresses.items():
        address_code = partner_role_address_code_dict.get(partner_role)

        if not partner_no:
            continue

        partner_data = {"partnerRole": partner_role, "partnerNo": partner_no}
        if partner_role != RealtimePartnerType.SALE_EMPLOYEE:
            partner_data["itemNo"] = HEADER_ORDER_KEY
        if address_code:
            partner_data["addrLink"] = address_code

        order_partners.append(partner_data)

    if item_ship_to_dict:
        for item_no, ship_to in item_ship_to_dict.items():
            if ship_to:
                item_ship_to = (str(ship_to or "").strip().split("-")[0] or "").strip()
                if str(ship_to) != header_full_ship_to:
                    order_partner = {
                        "partnerRole": RealtimePartnerType.SHIP_TO.value,
                        "partnerNo": item_ship_to,
                        "itemNo": item_no.zfill(6),
                    }
                    if item_otc_dict and item_otc_dict.get(item_no):
                        order_partner["addrLink"] = item_otc_dict[item_no]
                    order_partners.append(order_partner)

    if order_partners:
        order_partners = sorted(order_partners, key=lambda x: int(x.get("itemNo", "0")))
    return order_partners


def prepare_otc_partner_create(otc_info, partner_role):
    otc_partner = sap_migration_models.OrderOtcPartner(
        sold_to_code=otc_info.get("sold_to_code"), partner_role=partner_role
    )
    return otc_partner


def prepare_otc_partneraddress_create(otc_info):
    partneraddress = sap_migration_models.OrderOtcPartnerAddress(
        name1=otc_info.get("name1"),
        name2=otc_info.get("name2"),
        name3=otc_info.get("name3"),
        name4=otc_info.get("name4"),
        city=otc_info.get("city"),
        postal_code=otc_info.get("postal_code"),
        district=otc_info.get("district"),
        street_1=otc_info.get("street_1"),
        street_2=otc_info.get("street_2"),
        street_3=otc_info.get("street_3"),
        street_4=otc_info.get("street_4"),
        location=otc_info.get("location"),
        transport_zone_code=otc_info.get("transport_zone_code"),
        transport_zone_name=otc_info.get("transport_zone_name"),
        country_code=otc_info.get("country_code"),
        country_name=otc_info.get("country_name"),
        telephone_no=otc_info.get("telephone_no"),
        telephone_extension=otc_info.get("telephone_extension"),
        mobile_no=otc_info.get("mobile_no"),
        fax_no=otc_info.get("fax_no"),
        fax_no_ext=otc_info.get("fax_no_ext"),
        email=otc_info.get("email"),
        language=otc_info.get("language"),
        tax_number1=otc_info.get("tax_number1"),
        tax_number2=otc_info.get("tax_number2"),
        tax_id=otc_info.get("tax_id"),
        branch_id=otc_info.get("branch_id"),
    )
    return partneraddress


def prepare_otc_partneraddress_update(otc_info, partneraddress):
    partneraddress.name1 = otc_info.get("name1")
    partneraddress.name2 = otc_info.get("name2")
    partneraddress.name3 = otc_info.get("name3")
    partneraddress.name4 = otc_info.get("name4")
    partneraddress.city = otc_info.get("city")
    partneraddress.postal_code = otc_info.get("postal_code")
    partneraddress.district = otc_info.get("district")
    partneraddress.street_1 = otc_info.get("street_1")
    partneraddress.street_2 = otc_info.get("street_2")
    partneraddress.street_3 = otc_info.get("street_3")
    partneraddress.street_4 = otc_info.get("street_4")
    partneraddress.location = otc_info.get("location")
    partneraddress.transport_zone_code = otc_info.get("transport_zone_code")
    partneraddress.transport_zone_name = otc_info.get("transport_zone_name")
    partneraddress.country_code = otc_info.get("country_code")
    partneraddress.country_name = otc_info.get("country_name")
    partneraddress.telephone_no = otc_info.get("telephone_no")
    partneraddress.telephone_extension = otc_info.get("telephone_extension")
    partneraddress.mobile_no = otc_info.get("mobile_no")
    partneraddress.fax_no = otc_info.get("fax_no")
    partneraddress.fax_no_ext = otc_info.get("fax_no_ext")
    partneraddress.email = otc_info.get("email")
    partneraddress.language = otc_info.get("language")
    partneraddress.tax_number1 = otc_info.get("tax_number1")
    partneraddress.tax_number2 = otc_info.get("tax_number2")
    partneraddress.tax_id = otc_info.get("tax_id")
    partneraddress.branch_id = otc_info.get("branch_id")
    return partneraddress


def cp_params(order, order_lines):
    order_items_in = []
    order_header_params = {
        "salesOrg": order.sales_organization.code,
        "soldTo": order.ship_to,
        "shipTo": order.ship_to,
        "orderId": order.id,
    }

    for line in order_lines:
        item_no = line.item_no.zfill(6)
        item = {
            "itemNo": item_no,
            "materialCode": line.material_variant.code,
            "quantity": line.quantity if line.quantity else 0,
            "unit": line.sales_unit,
            "requestDate": line.request_date or "",
        }

        # Check if plant is present in the order line
        if line.plant:
            item["plant"] = line.plant

        # Check if bom_flag is present and True in the order line
        if hasattr(line, "bom_flag") and line.bom_flag:
            item["bom_flag"] = True

        order_items_in.append(item)

    return {
        "saleOrg": order_header_params["salesOrg"],
        "soldTo": order_header_params["soldTo"],
        "shipTo": order_header_params["shipTo"],
        "orderId": order_header_params["orderId"],
        "orderLines": order_items_in,
    }


def fetch_item_category(material, order_type, production_flag, batch_no):
    if material:
        if (
            material.material_type == MaterialTypes.OWN_MATERIAL.value
            and CIPOrderPaymentType.CASH.value == order_type
            and material.batch_flag
            and not batch_no
        ):
            return ItemCat.ZPSI.value
        elif (
            material.material_type == MaterialTypes.OWN_MATERIAL.value
            and CIPOrderPaymentType.CREDIT.value == order_type
            and material.batch_flag
            and not batch_no
        ):
            return ItemCat.ZPSH.value
        elif (
            MaterialTypes.OUTSOURCE_MATERIAL.value == material.material_type
            and CIPOrderPaymentType.CASH.value == order_type
            and production_flag
            and ProductionFlag.NOT_PRODUCED.value == production_flag
        ):
            return ItemCat.ZPS2.value
        elif (
            MaterialTypes.OUTSOURCE_MATERIAL.value == material.material_type
            and CIPOrderPaymentType.CREDIT.value == order_type
            and production_flag
            and ProductionFlag.NOT_PRODUCED.value == production_flag
        ):
            return ItemCat.ZPS0.value
    return ""


def fetch_item_category_excel_upload(material, order_type, item_note):
    if material:
        if (
            MaterialTypes.OUTSOURCE_MATERIAL.value == material.material_type
            and CIPOrderPaymentType.CASH.value == order_type
            and item_note
            and item_note.startswith(ITEM_NOTE_WHEN_NOT_PRODUCED)
        ):
            return ItemCat.ZPS2.value
        elif (
            MaterialTypes.OUTSOURCE_MATERIAL.value == material.material_type
            and CIPOrderPaymentType.CREDIT.value == order_type
            and item_note
            and item_note.lower().startswith(ITEM_NOTE_WHEN_NOT_PRODUCED.lower())
        ):
            return ItemCat.ZPS0.value
    return ""


def es_16_params(
    order,
    order_ext,
    order_lines,
    order_partners,
    payment_term,
    order_otc_partner_addresses,
    user,
    order_item_map,
    parent_child_item_no_dict,
):
    order_items_in = []
    order_schedules_in = []
    order_conditions_in = []
    partner_addresses = []
    order_header_in = header_params(order, order_ext, payment_term)
    order_text_in = prepare_param_es16_order_text(order, order_lines, user)

    partner_address_params(order_otc_partner_addresses, partner_addresses)

    item_details_params(
        order,
        order_conditions_in,
        order_items_in,
        order_lines,
        order_schedules_in,
        order_item_map,
        parent_child_item_no_dict,
    )

    return {
        "piMessageId": get_random_number(),
        "testrunFlag": False,
        "orderHeaderIn": order_header_in,
        "orderItemsIn": order_items_in,
        "orderPartners": order_partners,
        **({"partneraddresses": partner_addresses} if partner_addresses else {}),
        **({"orderSchedulesIn": order_schedules_in} if order_schedules_in else {}),
        **({"orderConditionsIn": order_conditions_in} if order_conditions_in else {}),
        "orderText": order_text_in,
    }


def es_16_params_for_excell_upload(
    order,
    order_lines,
    order_partners,
    parent_child_item_no_dict,
):
    order_items_in = []
    order_schedules_in = []
    order_header_in = header_params_excell_upload(order)
    order_text_in = prepare_param_es16_order_text_excel_upload(
        order, order_lines, order.web_user_name
    )

    item_details_params_excel_upload(
        order,
        order_lines,
        order_items_in,
        order_schedules_in,
        parent_child_item_no_dict,
    )

    return {
        "piMessageId": get_random_number(),
        "poUploadMode": "B",
        "savePartialItem": True,
        "orderHeaderIn": order_header_in,
        "orderItemsIn": order_items_in,
        "orderPartners": order_partners,
        **({"orderSchedulesIn": order_schedules_in} if order_schedules_in else {}),
        "orderText": order_text_in,
    }


def item_details_params(
    order,
    order_conditions_in,
    order_items_in,
    order_lines,
    order_schedules_in,
    order_item_in_map,
    parent_child_item_no_dict,
):
    for line in order_lines:
        item_no = line.item_no.zfill(6)
        order_line_cp = OrderLineCpRepo.get_order_line_cp_by_order_line_id(line.id)
        item = {
            "itemNo": item_no,
            "material": line.material.material_code,
            "targetQuantity": line.quantity if line.quantity else 0,
            "salesUnit": line.sales_unit or "",
            "plant": order_line_cp and order_line_cp.plant or line.plant or "",
            "poNo": line.po_no or "",
            "poitemNo": line.po_item_no or "",
            "poDate": line.request_date.strftime("%d/%m/%Y")
            if line.request_date
            else "",
            "itemCategory": fetch_item_category(
                line.material, order.order_type, line.production_flag, line.batch_no
            ),
            "priceDate": line.price_date.strftime("%d/%m/%Y")
            if line.price_date
            else "",
            "overDeliveryTol": line.delivery_tol_over or 0,
            "underDeliveryTol": line.delivery_tol_under or 0,
            "unlimitTol": line.delivery_tol_unlimited or "",
            "paymentTermItem": order.payment_term[:4],
            "batchNumber": line.batch_no or "",
        }
        if line.bom_flag and line.parent:
            item["parentItemNo"] = line.parent.item_no.zfill(6)
        elif line.bom_flag:
            item["parentItemNo"] = HEADER_ORDER_KEY
            child_item_nos = parent_child_item_no_dict.get(line.item_no)
            if child_item_nos:
                child_order_line_cp = (
                    OrderLineCpRepo.get_order_line_cp_by_order_id_and_item_no(
                        order, child_item_nos
                    )
                )
                add_key_and_data_into_params(
                    "plant",
                    child_order_line_cp
                    and child_order_line_cp.plant
                    or line.plant
                    or "",
                    item,
                )
        order_items_in.append(item)
        order_item_in = order_item_in_map.get(line.item_no)
        add_order_condition_in(item_no, line, order_conditions_in, order_item_in)

        order_schedule_in = {
            "itemNo": item_no,
            "requestDate": line.request_date.strftime("%d/%m/%Y")
            if line.request_date
            else "",
            "requestQuantity": line.quantity,
            "confirmQty": 0,
        }
        if item["itemCategory"] == ItemCat.ZPS0.value:
            order_schedule_in["scheduleLineCate"] = ScheduleLineCategory.CN.value
        order_schedules_in.append(order_schedule_in)


def item_details_params_excel_upload(
    order,
    order_lines,
    order_items_in,
    order_schedules_in,
    parent_child_item_no_dict,
):
    for line in order_lines:
        item_no = line.item_no.zfill(6)
        order_line_cp = OrderLineCpRepo.get_order_line_cp_by_order_line_id(line.id)
        item = {
            "itemNo": item_no,
            "material": line.material.material_code,
            "targetQuantity": line.quantity if line.quantity else 0,
            "salesUnit": line.sales_unit or "",
            "plant": order_line_cp and order_line_cp.plant or line.plant or "",
            "poNo": line.po_no or "",
            "itemCategory": fetch_item_category_excel_upload(
                line.material, order.order_type, line.item_note
            ),
            "batchNumber": line.batch_no or "",
        }
        if line.bom_flag and line.parent:
            item["parentItemNo"] = line.parent.item_no.zfill(6)
        elif line.bom_flag:
            item["parentItemNo"] = HEADER_ORDER_KEY
            child_item_nos = parent_child_item_no_dict.get(line.item_no)
            if child_item_nos:
                child_order_line_cp = (
                    OrderLineCpRepo.get_order_line_cp_by_order_id_and_item_no(
                        order, child_item_nos
                    )
                )
                add_key_and_data_into_params(
                    "plant",
                    child_order_line_cp
                    and child_order_line_cp.plant
                    or line.plant
                    or "",
                    item,
                )
        order_items_in.append(item)
        order_schedule_in = {
            "itemNo": item_no,
            "requestDate": line.request_date.strftime("%d/%m/%Y")
            if line.request_date
            else "",
            "requestQuantity": line.quantity,
        }
        if item["itemCategory"] == ItemCat.ZPS0.value:
            order_schedule_in["scheduleLineCate"] = ScheduleLineCategory.CN.value
        order_schedules_in.append(order_schedule_in)


def partner_address_params(order_otc_partner_addresses, partner_addresses):
    for address in order_otc_partner_addresses:
        partneraddress = {
            "addrNo": address.address_code or "",
            "name": address.name1 or "",
            "name2": address.name2 or "",
            "name3": address.name3 or "",
            "name4": address.name4 or "",
            "city": address.city or "",
            "postleCode": address.postal_code or "",
            "district": address.district or "",
            "street": address.street_1 or "",
            "street1": address.street_2 or "",
            "street2": address.street_3 or "",
            "street3": address.street_4 or "",
            "location": address.location or "",
            "transpzone": address.transport_zone_code or "",
            "country": address.country_code or "",
            "telephoneNo": address.telephone_no or "",
            "telephoneNoExt": address.telephone_extension or "",
            "mobileNo": address.mobile_no or "",
            "faxNo": address.fax_no or "",
            "faxNoExt": address.fax_no_ext or "",
            "language": "2" if address.language == "th" else "E",
            "orderTaxNumber": {
                "taxId": address.tax_id or "",
                "branchId": address.branch_id or "",
                "taxNumber1": address.tax_number1 or "",
                "taxNumber2": address.tax_number2 or "",
            },
        }
        partner_addresses.append(partneraddress)


def partner_address_params_es18(order_otc_partner_addresses, partner_addresses):
    for address in order_otc_partner_addresses:
        partneraddress = {
            "addressNo": address.address_code or "",
            "name1": address.name1 or "",
            "name2": address.name2 or "",
            "name3": address.name3 or "",
            "name4": address.name4 or "",
            "city": address.city or "",
            "zipCode": address.postal_code or "",
            "district": address.district or "",
            "street": address.street_1 or "",
            "streetSuppl1": address.street_2 or "",
            "streetSuppl2": address.street_3 or "",
            "streetSuppl3": address.street_4 or "",
            "location": address.location or "",
            "transportZone": address.transport_zone_code or "",
            "country": address.country_code or "",
            "telephoneNo": address.telephone_no or "",
            "telephoneNoExt": address.telephone_extension or "",
            "mobileNo": address.mobile_no or "",
            "faxNo": address.fax_no or "",
            "faxNoExt": address.fax_no_ext or "",
            "language": "2" if address.language == "th" else "E",
            "orderTaxNumber": {
                "taxId": address.tax_id or "",
                "branchId": address.branch_id or "",
                "taxNumber1": address.tax_number1 or "",
                "taxNumber2": address.tax_number2 or "",
            },
        }
        partner_addresses.append(partneraddress)


def header_params(order, order_ext, payment_term):
    order_header_in = {
        "docType": order.order_type,
        "salesOrg": order.sales_organization.code,
        "distributionChannel": order.distribution_channel
        and order.distribution_channel.code
        or "",
        "division": order.division and order.division.code or "",
        "salesGroup": order.sales_group and order.sales_group.code or "",
        "salesOffice": order.sales_office and order.sales_office.code or "",
        "requestDate": order.request_date.strftime("%d/%m/%Y"),
        "paymentTerm": payment_term[:4],
        "poNo": order.po_number or "",
        "poDate": order.po_date.strftime("%d/%m/%Y")
        if order.po_date
        else datetime.now().strftime("%d/%m/%Y"),
        "taxClass": order_ext and order_ext.tax_class or "",
        "unloadingPoint": order.unloading_point or "",
    }
    return order_header_in


def header_params_excell_upload(order):
    order_header_in = {
        "docType": order.order_type,
        "salesOrg": order.sales_organization.code,
        "distributionChannel": order.distribution_channel
        and order.distribution_channel.code
        or "",
        "division": order.division and order.division.code or "",
        "requestDate": order.request_date.strftime("%d/%m/%Y"),
        "poNo": order.po_number or "",
        "poDate": order.po_date.strftime("%d/%m/%Y")
        if order.po_date
        else datetime.now().strftime("%d/%m/%Y"),
    }
    return order_header_in


def add_order_condition_in(item_no, line, order_conditions_in, order_item_in):
    if (
        MaterialTypes.SERVICE_MATERIAL.value == line.material.material_type
        and line.price_per_unit
        and order_item_in
        and order_item_in.get("manual_price_flag", False)
    ):
        order_conditions_in.append(
            {
                "itemNo": item_no,
                "conditionType": ItemCat.ZPS2.value,
                "conditionValue": line.price_per_unit,
            }
        )


def prepare_param_es16_order_text(order, order_lines, user):
    order_text = []
    parent_additional_details_dict = {}

    for line in order_lines:
        parent_additional_details = {
            field: getattr(line, field, "")
            for field, _ in MAPPING_ITEM_ADDITIONAL_FIELDS.items()
        }
        for field, text_id in MAPPING_ITEM_ADDITIONAL_FIELDS.items():
            value = getattr(line, field, "")

            if not value and line.bom_flag and line.parent_id:
                parent_value = parent_additional_details_dict.get(
                    line.parent_id, {}
                ).get(field, "")
                if parent_value:
                    value = parent_value
            if (
                field == "item_note"
                and line.production_flag == ProductionFlag.NOT_PRODUCED.value
            ):
                value = f"{ITEM_NOTE_WHEN_NOT_PRODUCED} {value}"
            elif (
                field == "item_note"
                and line.production_flag == ProductionFlag.PRODUCED.value
                and value is not None
                and value.startswith(ITEM_NOTE_WHEN_NOT_PRODUCED)
            ):
                value = value[4:]
            if value:
                order_text.append(
                    {
                        "itemNo": line.item_no,
                        "textId": text_id,
                        "textLineList": [
                            {"textLine": text} for text in value.split("\n")
                        ],
                    }
                )
        if line.bom_flag:
            parent_additional_details_dict[line.id] = parent_additional_details

    # Additional fields not related to order lines
    order_text.append(
        {
            "itemNo": HEADER_ORDER_KEY,
            "textId": MAPPING_HEADER_ADDITIONAL_FIELDS.get("web_username"),
            "textLineList": [{"textLine": user.first_name + " " + user.last_name}],
        }
    )
    order_text.append(
        {
            "itemNo": HEADER_ORDER_KEY,
            "textId": MAPPING_HEADER_ADDITIONAL_FIELDS.get("source_of_app"),
            "textLineList": [{"textLine": HEADER_DOMESTIC}],
        }
    )
    for field, text_id in MAPPING_HEADER_ADDITIONAL_FIELDS.items():
        if hasattr(order, field):
            text_line = getattr(order, field)
            if text_line is None:
                text_line = ""
            order_text.append(
                {
                    "itemNo": HEADER_ORDER_KEY,
                    "textId": text_id,
                    "textLineList": [{"textLine": text_line}],
                }
            )
        if hasattr(order.orderextension, field):
            text_line = getattr(order.orderextension, field)
            if text_line is None:
                text_line = ""
            order_text.append(
                {
                    "itemNo": HEADER_ORDER_KEY,
                    "textId": text_id,
                    "textLineList": [{"textLine": text_line}],
                }
            )
    return order_text


def prepare_param_es16_order_text_excel_upload(order, order_lines, web_user_name):
    order_text = []
    parent_additional_details_dict = {}

    for line in order_lines:
        parent_additional_details = {
            field: getattr(line, field, "")
            for field, _ in MAPPING_ITEM_ADDITIONAL_FIELDS_EXCEL_UPLOAD.items()
        }
        for field, text_id in MAPPING_ITEM_ADDITIONAL_FIELDS_EXCEL_UPLOAD.items():
            value = getattr(line, field, "")

            if not value and line.bom_flag and line.parent_id:
                parent_value = parent_additional_details_dict.get(
                    line.parent_id, {}
                ).get(field, "")
                if parent_value:
                    value = parent_value
            if value:
                order_text.append(
                    {
                        "itemNo": line.item_no,
                        "textId": text_id,
                        "textLineList": [
                            {"textLine": text} for text in value.split("\n")
                        ],
                    }
                )
        if line.bom_flag:
            parent_additional_details_dict[line.id] = parent_additional_details
    order_text.append(
        {
            "itemNo": HEADER_ORDER_KEY,
            "textId": MAPPING_HEADER_ADDITIONAL_FIELDS.get("web_username"),
            "textLineList": [
                {
                    "textLine": order.created_by.first_name
                    + " "
                    + order.created_by.last_name
                }
            ],
        }
    )
    order_text.append(
        {
            "itemNo": HEADER_ORDER_KEY,
            "textId": MAPPING_HEADER_ADDITIONAL_FIELDS.get("source_of_app"),
            "textLineList": [{"textLine": EXCEL_HEADER_DOMESTIC}],
        }
    )
    for field, text_id in MAPPING_HEADER_ADDITIONAL_FIELDS_EXCEL_UPLOAD.items():
        if hasattr(order, field):
            text_line = getattr(order, field)
            if text_line is None:
                text_line = ""
            order_text.append(
                {
                    "itemNo": HEADER_ORDER_KEY,
                    "textId": text_id,
                    "textLineList": [{"textLine": text_line}],
                }
            )
        if hasattr(order.orderextension, field):
            text_line = getattr(order.orderextension, field)
            if text_line is None:
                text_line = ""
            order_text.append(
                {
                    "itemNo": HEADER_ORDER_KEY,
                    "textId": text_id,
                    "textLineList": [{"textLine": text_line}],
                }
            )
    return order_text


def process_cp_response(cp_response):
    cp_error_messages = []
    cp_item_message = []
    return cp_item_message, cp_error_messages


def get_response_message(
    response,
    order,
    success,
    cp_item_messages,
    cp_error_messages,
    sap_order_messages,
    sap_item_messages,
    warning_messages,
):
    response.success = success

    if order:
        response.order = []
        response.order = CipTempOrder(order.id)
    if sap_order_messages is not None and len(sap_order_messages):
        response.sap_order_messages = []
        for sap_order_message in sap_order_messages:
            response.sap_order_messages.append(
                SapOrderMessages(
                    id=sap_order_message.get("id"),
                    error_code=sap_order_message.get("error_code"),
                    so_no=sap_order_message.get("so_no"),
                    error_message=sap_order_message.get("error_message"),
                )
            )
    if sap_item_messages is not None and len(sap_item_messages):
        response.sap_item_messages = []
        for sap_item_message in sap_item_messages:
            response.sap_item_messages.append(
                SapItemMessages(
                    error_code=sap_item_message.get("error_code"),
                    item_no=sap_item_message.get("item_no"),
                    error_message=sap_item_message.get("error_message"),
                )
            )
    if cp_item_messages is not None and len(cp_item_messages):
        response.cp_item_messages = []
        for cp_item_message in cp_item_messages:
            response.cp_item_messages.append(
                CPItemMessage(
                    material_code=cp_item_message.get("material_code"),
                    item_no=cp_item_message.get("item_no"),
                    show_in_popup=cp_item_message.get("show_in_popup"),
                    material_description=cp_item_message.get("material_description"),
                    quantity=cp_item_message.get("quantity"),
                    request_date=cp_item_message.get("request_date"),
                    confirm_date=cp_item_message.get("confirm_date"),
                    bom_flag=cp_item_message.get("bom_flag"),
                    parent_item_no=cp_item_message.get("parent_item_no"),
                    plant=cp_item_message.get("plant"),
                    original_date=cp_item_message.get("original_date"),
                )
            )
    if warning_messages is not None and len(warning_messages):
        response.warning_messages = []
        for sap_item_message in warning_messages:
            response.warning_messages.append(
                WarningMessages(
                    source=sap_item_message.get("source"),
                    order=sap_item_message.get("order"),
                    message=sap_item_message.get("message"),
                )
            )
    return response


def validate_order_msg(data, error_msg_order_header, order_header_msg):
    if data.get("id").startswith("V"):
        message = format_order_header_msg(data, error_msg_order_header)
        order_header_msg.append(message)
    return order_header_msg


def format_order_header_msg(order_header_response, error_msg_order_header):
    msg_id = order_header_response.get("id")
    msg_number = order_header_response.get("number")
    message_format = error_msg_order_header.get(msg_id, {}).get(msg_number, None)
    if message_format:
        order_header_msg = f"{msg_id} {msg_number} {message_format}"
        message_v1 = order_header_response.get("messageV1", "")
        message_v2 = order_header_response.get("messageV2", "")
        message_v3 = order_header_response.get("messageV3", "")
        message_v4 = order_header_response.get("messageV4", "")
        order_header_msg = order_header_msg.replace("&1", message_v1)
        order_header_msg = order_header_msg.replace("&2", message_v2)
        order_header_msg = order_header_msg.replace("&3", message_v3)
        order_header_msg = order_header_msg.replace("&4", message_v4)
        if "&" in order_header_msg:
            message_list = [message_v1, message_v2, message_v3, message_v4]
            for message in message_list:
                order_header_msg = order_header_msg.replace("&", message, 1)
    else:
        order_header_msg = (
            f"{msg_id} {msg_number} {order_header_response.get('message')}"
        )
    return order_header_msg


def get_sap_warning_messages(sap_response):
    warning_messages = []
    # es17
    if sap_response.get("creditStatus") in WARNING_CREDIT_STATUSES:
        order_no = sap_response.get("salesdocument")
        warning_message = sap_response.get("creditStatusText")
        warning_messages.append(
            {"source": "sap", "order": order_no, "message": warning_message}
        )
    return warning_messages


def get_partner_emails_from_es16_response(sap_response):
    order_partners_list = sap_response.get("orderPartners", [])
    partner_no_list = [
        partner_data["partnerNo"]
        for partner_data in order_partners_list
        if partner_data.get("partnerRole") == "VE"
    ]
    partner_emails = SoldToMasterRepo.get_sold_to_partner_address_by_partner(
        partner_no_list
    ).values_list("email", flat=True)
    return list(partner_emails)


def update_remark_order_line(order_line_remark, remark):
    if not order_line_remark:
        return remark
    if remark not in order_line_remark:
        return ", ".join(
            map(lambda x: x.strip(), f"{order_line_remark}, {remark}".split(","))
        )
    return order_line_remark


def get_text_master_data_by_sold_to_code(
    sold_to_code, sales_org, distribution_channel, division
):
    """
    This function returns an object with text_id as the key and the rest of the data as its value,
    filtered by the sold_to_code.

    :param sold_to_code: sold to code used to filter the data
    :return: an object with text_id as the key
    """
    data = SoldToMasterRepo.fetch_text_data_for_sold_to(
        sold_to_code, sales_org, distribution_channel, division
    )

    # Create the object with text_id as the key and the rest of the data as its value
    text_id_obj = {d["text_id"] + "_" + d["language"]: d for d in data}

    return text_id_obj


def generate_temp_so_no():
    return f"{int(datetime.now().timestamp() * 2 / 100)}"


def prepare_excel_order_cip(header_data, params, user):
    sale_org = SalesOrganizationMasterRepo.get_sale_organization_by_code(
        header_data.get("sale_org")
    )
    dist_channel = DistributionChannelMasterRepo.get_distribution_channel_by_code(
        header_data.get("distribution_channel")
    )
    division = DivisionMasterRepo.get_division_by_code(header_data.get("division"))
    sold_to_code = params.get("sold_to", "").zfill(10)
    sold_to_master = SoldToMasterRepo.get_sold_to_data(sold_to_code)
    order = sap_migration_models.Order(
        status=ScgOrderStatus.DRAFT.value,
        so_no=generate_temp_so_no(),
        type=OrderType.DOMESTIC.value,
        created_by_flow=CreatedFlow.EXCEL_UPLOAD.value,
        sold_to=sold_to_master,
        sold_to_code=sold_to_code,
        created_by=user,
        dp_no=f"01{int(datetime.now().timestamp() * 2 / 100)}",
        invoice_no=f"01{int(datetime.now().timestamp())}",
        po_number=params.get("po_number"),
        po_no=params.get("po_number"),
        ship_to=params.get("ship_to", "").zfill(10),
        bill_to=params.get("bill_to").zfill(10) if params.get("bill_to") else "",
        payer=params.get("payer").zfill(10) if params.get("payer") else "",
        order_type=header_data.get("order_type"),
        request_date=is_valid_date(params.get("request_date_header")),
        internal_comments_to_warehouse=params.get("internal_comment_to_warehouse"),
        internal_comments_to_logistic=params.get("internal_comment_to_logistic"),
        sales_organization=sale_org,
        distribution_channel=dist_channel,
        division=division,
        item_no_latest=0,
    )
    order_extension = sap_migration_models.OrderExtension(
        order=order,
        bu=sale_org.business_unit.code,
        additional_txt_header_note1=params.get("header_note1"),
        temp_order_no=order.so_no,
        created_by=user,
        last_updated_by=user,
    )
    return order, order_extension


def prepare_excel_order_line_cip(line, material, sales, order):
    order_line = sap_migration_models.OrderLines(
        order=order,
        po_no=order.po_no,
        type=order.type,
        prc_group_1=sales.material_group1,
        po_no_external=random.randint(10000, 99999),
        material_id=material.id,
        material_code=material.material_code,
        plant=line.get("plant"),
        quantity=float(line.get("request_quantity")),
        original_quantity=float(line.get("request_quantity")),
        request_date=is_valid_date(line.get("request_date")),
        sales_unit=sales.sales_unit or material.base_unit,
        item_note=line.get("item_note"),
        force_flag=line.get("force_request_date") in FORCE_FLAG_VALUES,
        production_flag=ProductionFlag.NOT_PRODUCED.value
        if line.get("item_note", "")
        .upper()
        .startswith(SAP_ITEM_NOTE_CIP_NOT_PRODUCED_PREFIX)
        else ProductionFlag.PRODUCED.value,
        ship_to=line.get("item_ship_to"),
    )
    if line.get("batch") and material.batch_flag:
        order_line.batch_no = line.get("batch")
        order_line.batch_choice_flag = True
    return order_line
