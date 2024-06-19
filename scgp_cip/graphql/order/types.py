import graphene
import logging

from common.helpers import DateHelper
from common.product_group import ProductGroupDescription
from saleor.graphql.account.types import User
from sap_migration.graphql.types import CustomerGroupMaster, CustomerGroup1Master, CustomerGroup2Master, \
    CustomerGroup3Master, CustomerGroup4Master, Incoterms1Master, Currency
from scg_checkout.graphql.enums import ScgOrderStatus, POStatusEnum
from scg_checkout.graphql.helper import get_order_type_desc, deepgetattr
from scg_checkout.graphql.resolves.orders import get_address_from_code
from scg_checkout.graphql.types import SalesOffice, SalesGroup, ScgpSalesEmployee, SapMigrationCompany, DPNo, InvoiceNo, \
    OrderPartners, \
    OrderCondition, OrderText
from sap_migration import models as migration_models

from sap_master_data.graphql.types import SoldToPartnerAddressMaster, SoldToTextMaster
from sap_master_data.models import TransportZone, CountryMaster
from scg_checkout.graphql.helper import PAYMENT_TERM_MAPPING
from scg_checkout.graphql.types import (SalesOrganization, DistributionChannel, ScgDivision)
from sap_migration.graphql.types import (
    SalesOrganizationMaster,
    DistributionChannelMaster,
    DivisionMaster,
    SalesOfficeMaster,
    SalesGroupMaster,
    SoldToMaster,
)
from saleor.graphql.core.types import ModelObjectType
from sap_master_data import models as sap_data_models
from scgp_cip.common.constants import BOM_FLAG_TRUE_VALUE, YMD_FORMAT, DMY_FORMAT, MANUAL_PRICE_FLAG_TRUE_VALUE
from scgp_cip.common.enum import CipCancelItemStatus
from scgp_cip.common.helper.date_time_helper import convert_date_format
from scgp_cip.dao.master_repo.sales_office_master_repo import SalesOfficeMasterRepo
from scgp_cip.dao.order.distribution_channel_master_repo import DistributionChannelMasterRepo
from scgp_cip.dao.order.division_master_repo import DivisionMasterRepo
from scgp_cip.dao.order.order_otc_partner_address_repo import OrderOtcPartnerAddressRepo
from scgp_cip.dao.order.sales_group_master_repo import SalesGroupMasterRepo
from scgp_cip.dao.order_line.bom_material_repo import BomMaterialRepo
from scgp_cip.dao.order_line.conversion2master_repo import Conversion2MasterRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo
from scgp_cip.dao.order_line_cp.order_line_cp_repo import OrderLineCpRepo

from scgp_customer.graphql.types import CustomerUnloadingPoint
from graphene import ObjectType, InputObjectType

from saleor.graphql.core.types import NonNullList
from scgp_cip.dao.order.order_repo import OrderRepo
from scgp_cip.dao.order_line.order_line_repo import OrderLineRepo
from scgp_cip.graphql.order_line.types import CipOrderLineInput, CipTempOrderLine, CpOrderLineInput, OrderOtcPartner, \
    CipConversion2Master, CipAddOrderLineInput
from datetime import datetime
import re


class CipOrderOtcPartnerInput(InputObjectType):
    sold_to_code = graphene.String(required=False)
    name1 = graphene.String(required=False)
    name2 = graphene.String(required=False)
    name3 = graphene.String(required=False)
    name4 = graphene.String(required=False)
    city = graphene.String(required=False)
    postal_code = graphene.String(required=False)
    district = graphene.String(required=False)
    street_1 = graphene.String(required=False)
    street_2 = graphene.String(required=False)
    street_3 = graphene.String(required=False)
    street_4 = graphene.String(required=False)
    location = graphene.String(required=False)
    transport_zone_code = graphene.String(required=False)
    transport_zone_name = graphene.String(required=False)
    country_code = graphene.String(required=False)
    country_name = graphene.String(required=False)
    telephone_no = graphene.String(required=False)
    telephone_extension = graphene.String(required=False)
    mobile_no = graphene.String(required=False)
    fax_no = graphene.String(required=False)
    fax_no_ext = graphene.String(required=False)
    email = graphene.String(required=False)
    language = graphene.String(required=False)
    tax_number1 = graphene.String(required=False)
    tax_number2 = graphene.String(required=False)
    tax_id = graphene.String(required=False)
    branch_id = graphene.String(required=False)


class CipOrderInformationInput(InputObjectType):
    customer_id = graphene.ID(required=False)
    po_date = graphene.Date(required=False, description="date must be type yyyy-mm-dd")
    po_number = graphene.String(required=False)
    request_date = graphene.Date(
        required=False, description="date must be type yyyy-mm-dd"
    )
    order_type = graphene.String(required=False)
    sold_to_code = graphene.String(required=False)
    ship_to = graphene.String(required=False)
    bill_to = graphene.String(required=False)
    customer_group_1_id = graphene.ID(require=False)
    customer_group_2_id = graphene.ID(require=False)
    customer_group_3_id = graphene.ID(require=False)
    customer_group_4_id = graphene.ID(require=False)
    from_header = graphene.String(required=False)
    header_note1 = graphene.String(required=False)
    cash = graphene.String(required=False)
    internal_comments_to_warehouse = graphene.String(required=False)
    internal_comments_to_logistic = graphene.String(required=False)
    external_comments_to_customer = graphene.String(required=False)
    product_information = graphene.String(required=False)
    shipping_point = graphene.String(required=False)
    route = graphene.String(required=False)
    delivery_block = graphene.String(require=False)
    incoterms_id = graphene.ID(required=False)
    tax_class = graphene.String(require=False)
    unloading_point = graphene.String(require=False)
    sales_employee = graphene.String(require=False)
    payment_term = graphene.String()

    otc_sold_to = graphene.Field(
        CipOrderOtcPartnerInput,
        description="information about One Time Customer Sold TO",
        required=False,
    )

    otc_bill_to = graphene.Field(
        CipOrderOtcPartnerInput,
        description="information about One Time Customer Bill TO",
        required=False,
    )

    otc_ship_to = graphene.Field(
        CipOrderOtcPartnerInput,
        description="information about One Time Customer Ship TO",
        required=False,
    )


class CipOrderOrganizationalDataInput(InputObjectType):
    sale_organization_code = graphene.String()
    distribution_channel_code = graphene.String()
    division_code = graphene.String()
    sale_office_code = graphene.String()
    sale_group_code = graphene.String()
    sales_employee = graphene.String()


class CipOrderUpdateInput(InputObjectType):
    order_information = graphene.Field(CipOrderInformationInput)
    order_organization_data = graphene.Field(
        CipOrderOrganizationalDataInput,
        description="information about order organization data",
        required=False,
    )
    lines = NonNullList(
        CipOrderLineInput,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ),
        required=False,
    )
    status = graphene.Field(ScgOrderStatus, description="", required=False)


class CpOrderUpdateInput(InputObjectType):
    order_id = graphene.String()
    lines = NonNullList(
        CpOrderLineInput,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ),
        required=False,
    )


class OrderExtension(ModelObjectType):
    additional_txt_from_header = graphene.String()
    additional_txt_header_note1 = graphene.String()
    additional_txt_cash = graphene.String()
    tax_class = graphene.String()
    otc_sold_to = graphene.Field(OrderOtcPartner)
    otc_bill_to = graphene.Field(OrderOtcPartner)
    otc_ship_to = graphene.Field(OrderOtcPartner)
    temp_order_no = graphene.String()

    class Meta:
        model = migration_models.OrderExtension


class CipTempOrder(ModelObjectType):
    id = graphene.ID()
    sold_to = graphene.Field(SoldToMaster)
    customer = graphene.Field(SoldToMaster)
    po_date = graphene.Date()
    po_number = graphene.String()
    ship_to = graphene.String()
    bill_to = graphene.String()
    unloading_point = graphene.String()
    order_type = graphene.String()
    request_date = graphene.Date()
    sale_organization = graphene.Field(SalesOrganization)
    distribution_channel = graphene.Field(DistributionChannel)
    division = graphene.Field(ScgDivision)
    sale_office = graphene.Field(SalesOffice)
    sales_group = graphene.Field(SalesGroup)
    total_price = graphene.Float()
    order_lines = graphene.List(lambda: CipTempOrderLine)
    status = graphene.String()
    order_no = graphene.String()
    scgp_sales_employee = graphene.Field(lambda: ScgpSalesEmployee)
    created_by = graphene.Field(User)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    update_by = graphene.Field(User)
    so_no = graphene.String()
    type = graphene.String()
    company = graphene.Field(SapMigrationCompany)
    payment_term = graphene.String()
    credit_status = graphene.String()
    order_date = graphene.Date()
    status_sap = graphene.String()
    customer_group = graphene.Field(CustomerGroupMaster)
    customer_group_1 = graphene.Field(CustomerGroup1Master)
    customer_group_2 = graphene.Field(CustomerGroup2Master)
    customer_group_3 = graphene.Field(CustomerGroup3Master)
    customer_group_4 = graphene.Field(CustomerGroup4Master)
    dp_no = graphene.String()
    invoice_no = graphene.String()
    delivery_block = graphene.String()
    incoterm = graphene.String()
    incoterms_1 = graphene.Field(Incoterms1Master)
    shipping_point = graphene.String()
    route = graphene.String()
    po_no = graphene.String()
    total_price_inc_tax = graphene.Float()
    tax_amount = graphene.Float()
    currency = graphene.Field(Currency)
    ship_to_address = graphene.String()
    sold_to_address = graphene.String()
    bill_to_address = graphene.String()
    tax_percent = graphene.Float()
    order_amt_before_vat = graphene.String()
    order_amt_vat = graphene.String()
    order_amt_after_vat = graphene.String()
    item_category = graphene.String()
    route_id = graphene.String()
    route_name = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    internal_comments_to_logistic = graphene.String()
    external_comments_to_customer = graphene.String()
    product_information = graphene.String()
    payment_term_key = graphene.String()
    payment_term_desc_th = graphene.String()
    po_upload_file_name = graphene.String()
    order_type_desc = graphene.String()
    order_extension = graphene.Field(OrderExtension)
    sales_employee = graphene.String()

    class Meta:
        model = migration_models.Order

    @staticmethod
    def resolve_customer(root, info):
        return root.sold_to

    @staticmethod
    def resolve_sale_organization(root, info):
        return root.sales_organization

    @staticmethod
    def resolve_sale_office(root, info):
        return root.sales_office

    @staticmethod
    def resolve_order_lines(root, info):
        return OrderLineRepo.get_order_lines_by_order_id_without_split(root.id)

    @staticmethod
    def resolve_payment_term_key(root, info):
        return root.get("payment_term", "")

    @staticmethod
    def resolve_payment_term_desc_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.payment_term, "")

    @staticmethod
    def resolve_order_extension(root, info):
        return OrderRepo.get_order_extension_by_id(root.id)

    @staticmethod
    def resolve_order_type_desc(root, info):
        order_type = getattr(root, "order_type", None)
        return get_order_type_desc(order_type)

    @staticmethod
    def resolve_sold_to_address(root, info):
        try:
            sold_to_code = root.sold_to.sold_to_code if root.sold_to else ""
            sold_to_address = get_address_from_code(sold_to_code)
            if sold_to_address:
                return sold_to_address
            return sold_to_code
        except Exception:
            return sold_to_code

    @staticmethod
    def resolve_sales_employee(root, info):
        sales_employee = root.sales_employee or ""
        return sales_employee.split("-")[0].strip() if sales_employee.split("-") else sales_employee

    @staticmethod
    def resolve_ship_to(root, info):
        return "" if OrderOtcPartnerAddressRepo.get_order_otc_ship_to_by_id(root.id) else root.ship_to


class SalesDataResponse(graphene.ObjectType):
    sales_organization = graphene.List(SalesOrganization)
    default_sales_organization = graphene.Field(SalesOrganization)
    distribution_channel = graphene.List(DistributionChannel)
    division = graphene.List(ScgDivision)
    default_otc_sold_to = graphene.Field(SoldToMaster)

    class Meta:
        description = "Sales data based on user login"


class PaymentTermData(graphene.ObjectType):
    code = graphene.String()
    name = graphene.String()
    displayText = graphene.String()

    class Meta:
        description = "Payment Term Object"


class SoldToHeaderInfoType(graphene.ObjectType):
    sold_to = graphene.Field(SoldToMaster)
    order_type = graphene.String()
    tax_classification = graphene.String()
    ship_to = graphene.List(SoldToPartnerAddressMaster)
    bill_to = graphene.List(SoldToPartnerAddressMaster)
    payment_term = graphene.List(PaymentTermData)
    unloading_points = graphene.List(CustomerUnloadingPoint)
    sale_employee = graphene.String()
    sale_organization = graphene.Field(SalesOrganizationMaster)
    sale_group = graphene.List(SalesGroupMaster)
    sale_office = graphene.Field(SalesOfficeMaster)
    division = graphene.Field(DivisionMaster)
    distribution_channel = graphene.Field(DistributionChannelMaster)
    default_sale_group = graphene.Field(SalesGroupMaster)
    default_unloading_point = graphene.Field(CustomerUnloadingPoint)
    default_ship_to = graphene.Field(SoldToPartnerAddressMaster)
    default_bill_to = graphene.Field(SoldToPartnerAddressMaster)
    default_payment_term = graphene.Field(PaymentTermData)
    headerNote1_en = graphene.Field(SoldToTextMaster)
    commentsToWarehouse_en = graphene.Field(SoldToTextMaster)
    headerNote1_th = graphene.Field(SoldToTextMaster)
    commentsToWarehouse_th = graphene.Field(SoldToTextMaster)

    class Meta:
        description = "Response Object SoldToHeaderInfoType"


class UnloadingPointForShipTo(ModelObjectType):
    ship_to = graphene.String()
    unloading_points = graphene.List(CustomerUnloadingPoint)
    default_unloading_point = graphene.Field(CustomerUnloadingPoint)

    class Meta:
        model = sap_data_models.SoldToUnloadingPointMaster

    @staticmethod
    def resolve_default_unloading_point(root, info):
        if root.first():
            return root.first()
        return None

    @staticmethod
    def resolve_ship_to(root, info):
        if root.first():
            return root.first().sold_to_code
        return None

    @staticmethod
    def resolve_unloading_points(root, info):
        return root.all()


class TempTransportation(graphene.ObjectType):
    id = graphene.ID(description="ID of scg_contract")
    country_code = graphene.String()
    transport_zone_code = graphene.String()
    transport_zone_name = graphene.String()

    class Meta:
        model = TransportZone


class TempCountryMaster(graphene.ObjectType):
    country_code = graphene.String()
    country_name = graphene.String()

    class Meta:
        model = CountryMaster


class OrderHeaderPriceInfo(InputObjectType):
    request_date = graphene.String(required=False)
    bill_to = graphene.String(required=False)
    ship_to = graphene.String(required=False)
    order_type = graphene.String(required=False)
    payment_term = graphene.String(required=False)
    distribution_channel = graphene.String(required=False)
    division = graphene.String(required=False)
    sales_organization = graphene.String(required=False)
    currency = graphene.String(required=False)
    tax_class_id = graphene.Int(required=False)
    so_no = graphene.String(required=False)
    sales_employee = graphene.String()


class OrderLinePriceInfo(InputObjectType):
    item_no = graphene.String()
    quantity = graphene.Float(required=False)
    plant = graphene.String()
    material_no = graphene.String(required=False)
    cust_mat_code = graphene.String(required=False)
    sale_unit = graphene.String(required=False)
    weight_unit = graphene.String()
    item_category = graphene.String()
    request_date = graphene.String(required=False)
    price_date = graphene.String(required=False)
    parent_item_no = graphene.String()
    production_flag = graphene.String()
    batch_no = graphene.String()
    ship_to = graphene.String()
    reject_reason = graphene.String(required=False)


class PriceCalculationInput(InputObjectType):
    order_information = graphene.Field(OrderHeaderPriceInfo)
    lines = NonNullList(
        OrderLinePriceInfo,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ),
        required=True,
    )


class PriceCalcOrderItemsOut(ObjectType):
    item_no = graphene.String()
    material_code = graphene.String()
    price_per_unit = graphene.Float()
    net_value = graphene.Float()
    currency = graphene.String()
    price_status = graphene.String()
    price_status_desc = graphene.String()
    material_description = graphene.String()
    material_type = graphene.String()
    manual_price_flag = graphene.Boolean()

    @staticmethod
    def resolve_item_no(root, info):
        return root.get("itemNo", "").lstrip("0")

    @staticmethod
    def resolve_material_code(root, info):
        return root.get("material", "")

    @staticmethod
    def resolve_price_per_unit(root, info):
        return root.get("netPricePerUnit", 0)

    @staticmethod
    def resolve_net_value(root, info):
        return root.get("netValue", 0)

    @staticmethod
    def resolve_currency(root, info):
        return root.get("currency", "")

    @staticmethod
    def resolve_price_status(root, info):
        return root.get("priceStatus", "")

    @staticmethod
    def resolve_price_status_desc(root, info):
        return root.get("priceStatusDesc", "")

    @staticmethod
    def resolve_material_description(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.get("material"))
        return material.description_en

    @staticmethod
    def resolve_material_type(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.get("material"))
        return material.material_type

    @staticmethod
    def resolve_manual_price_flag(root, info):
        return MANUAL_PRICE_FLAG_TRUE_VALUE == root.get("manualPriceFlag")


class PriceCalcOrderHeaderOut(ObjectType):
    order_amount_before_vat = graphene.Float()
    order_amount_vat = graphene.Float()
    order_amount_after_vat = graphene.Float()
    currency = graphene.String()

    @staticmethod
    def resolve_order_amount_before_vat(root, info):
        return root.get("orderAmtBeforeVat", 0)

    @staticmethod
    def resolve_order_amount_vat(root, info):
        return root.get("orderAmtVat", 0)

    @staticmethod
    def resolve_order_amount_after_vat(root, info):
        return root.get("orderAmtAfterVat", 0)

    @staticmethod
    def resolve_currency(root, info):
        return root.get("currency", "")


class PriceSummaryResponse(ObjectType):
    order_items_out = graphene.List(PriceCalcOrderItemsOut)
    order_header_out = graphene.Field(PriceCalcOrderHeaderOut)

    @staticmethod
    def resolve_order_items_out(root, info):
        return root.get("orderItemsOut", None)

    @staticmethod
    def resolve_order_header_out(root, info):
        return root.get("orderHeaderOut", None)


class PreviewHeaderResponse(ObjectType):
    so_no = graphene.String()
    po_number = graphene.String()
    order_date = graphene.String()
    payment_term = graphene.String()
    sale_organization = graphene.String()
    sale_employee = graphene.String()
    customer_name = graphene.String()
    ship_to = graphene.String()
    bill_to = graphene.String()

    @staticmethod
    def resolve_sale_organization(root, info):
        sales_org = root.get("sale_organization")
        if sales_org:
            return f'{sales_org.code} - {sales_org.short_name}'

    @staticmethod
    def resolve_payment_term(root, info):
        return PAYMENT_TERM_MAPPING.get(root.get("payment_term"), "")


class PreviewItemResponse(ObjectType):
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    quantity = graphene.Float()
    sales_unit = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.String()
    price_per_unit = graphene.Float()
    net_price = graphene.Float()
    request_date = graphene.String()
    confirmed_date = graphene.String()
    plant = graphene.String()
    confirmed_plant = graphene.String()
    bom_flag = graphene.Boolean()
    parent_item_no = graphene.String()
    item_status_en = graphene.String()
    item_status_th = graphene.String()

    @staticmethod
    def resolve_bom_flag(root, info):
        return BOM_FLAG_TRUE_VALUE == root.get("bom_flag")

    @staticmethod
    def resolve_net_price(root, info):
        return round(root.get("net_price"), 3) if root.get("net_price") else 0

    @staticmethod
    def resolve_confirmed_date(root, info):
        confirmed_date = root.get("confirmed_date")
        return convert_date_format(
            confirmed_date, YMD_FORMAT, DMY_FORMAT
        )


class PreviewItemFooterResponse(ObjectType):
    net_total_price = graphene.Float()
    total_vat = graphene.Float()
    order_amount_after_vat = graphene.Float()
    currency = graphene.String()


class CipPreviewOrderResponse(graphene.ObjectType):
    preview_header_data = graphene.Field(PreviewHeaderResponse)
    preview_item_data = graphene.List(PreviewItemResponse)
    preview_footer_data = graphene.Field(PreviewItemFooterResponse)


class CipGetChangeOrderItemData(graphene.ObjectType):
    id = graphene.ID()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    quantity = graphene.String()
    bom_flag = graphene.Boolean()
    manual_price_flag = graphene.Boolean(default_value=False)
    material_type = graphene.String()
    customer_mat_code = graphene.String()
    sales_unit = graphene.String()
    plant = graphene.String()
    payment_term = graphene.String()
    payment_term_desc_th = graphene.String()
    po_no = graphene.String()
    po_item_number = graphene.String()
    pr_no_os = graphene.String()
    pr_item_os = graphene.String()
    po_no_os = graphene.String()
    po_item_no_os = graphene.String()
    gr_status_os = graphene.String()
    item_status_en = graphene.String()
    item_status_th = graphene.String()
    production_flag = graphene.String()
    price_date = graphene.String()
    sale_qty_factor = graphene.Int()
    sale_qty_division = graphene.String()
    weight_unit = graphene.String()
    base_unit = graphene.String()
    delivery_block = graphene.Boolean()
    shipping_point = graphene.String()
    over_delivery_tol = graphene.Float()
    under_delivery_tol = graphene.Float()
    delivery_tol_unlimited = graphene.String()
    ship_to = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    sale_text_1 = graphene.String()
    sale_text_2 = graphene.String()
    sale_text_3 = graphene.String()
    sale_text_4 = graphene.String()
    remark = graphene.String()
    item_note = graphene.String()
    pr_item_text = graphene.String()
    lot_no = graphene.String()
    production_memo = graphene.String()
    item_category = graphene.String()
    material_group_1 = graphene.String()
    route_id = graphene.String()
    route_name = graphene.String()
    request_date = graphene.String()
    original_request_date = graphene.String()
    weight_per_unit = graphene.String()
    order_qty = graphene.String()
    confirm_qty = graphene.String()
    delivery_qty = graphene.String()
    assign_quantity = graphene.Float()
    delivery_status = graphene.String()
    prd_hierachy = graphene.String()
    po_date = graphene.String()
    reason_reject = graphene.String()
    confirmed_date = graphene.String()
    weight = graphene.Float()
    ref_pi_stock = graphene.String()
    net_value = graphene.Float()
    request_date_change_reason = graphene.String()
    weight_display = graphene.String()
    po_status = graphene.String()
    material_group1_desc = graphene.String()
    parent_item_no = graphene.String()
    price_per_unit = graphene.String()
    net_weight = graphene.String()
    price_currency = graphene.String()
    gross_weight = graphene.String()
    is_split_enabled = graphene.Boolean(default_value=False)
    batch_no = graphene.String()
    batch_flag = graphene.Boolean()
    batch_choice_flag = graphene.Boolean()
    sales_unit_list = graphene.List(CipConversion2Master)
    bom_unit_quantity = graphene.Float()

    @staticmethod
    def resolve_id(root, info):
        order_line = root.get("order_line_instance")
        return order_line.id if order_line else None

    @staticmethod
    def resolve_material_code(root, info):
        return root.get('material')

    @staticmethod
    def resolve_material_description(root, info):
        return root.get('materialDesc')

    @staticmethod
    def resolve_quantity(root, info):
        return root.get('orderQty')

    @staticmethod
    def resolve_material_type(root, info):
        return root.get('materialType')

    @staticmethod
    def resolve_customer_mat_code(root, info):
        order_line = root.get("order_line_instance")
        return order_line.customer_mat_35 if order_line else ""

    @staticmethod
    def resolve_sales_unit(root, info):
        return root.get('salesUnit')

    @staticmethod
    def resolve_payment_term(root, info):
        return root.get('paymentTerm')

    @staticmethod
    def resolve_payment_term_desc_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.get("paymentTerm"))

    @staticmethod
    def resolve_po_no(root, info):
        return root.get('poNumber')

    @staticmethod
    def resolve_po_item_number(root, info):
        return root.get('shipToItemNumber')

    @staticmethod
    def resolve_pr_no_os(root, info):
        return root.get('purchaseNo', "")

    @staticmethod
    def resolve_pr_item_os(root, info):
        return root.get('prItem', "")

    @staticmethod
    def resolve_po_no_os(root, info):
        return root.get('poSubcontract', "")

    @staticmethod
    def resolve_po_item_no_os(root, info):
        return root.get('poSubcontractItem', "")

    @staticmethod
    def resolve_gr_status_os(root, info):
        return root.get('grStatus')

    @staticmethod
    def resolve_production_flag(root, info):
        order_line = root.get("order_line_instance")
        return order_line.production_flag if order_line else ""

    @staticmethod
    def resolve_price_date(root, info):
        return DateHelper.sap_str_to_iso_str(root.get('priceDate'))

    @staticmethod
    def resolve_sale_qty_factor(root, info):
        return root.get('saleQtyFactor')

    @staticmethod
    def resolve_sale_qty_division(root, info):
        return root.get('saleQtyDivision')

    @staticmethod
    def resolve_weight_unit(root, info):
        return root.get('weightUnit', "")

    @staticmethod
    def resolve_base_unit(root, info):
        return root.get('baseUnit', "")

    @staticmethod
    def resolve_delivery_block(root, info):
        return True if root.get('deliveryBlock', "") else False

    @staticmethod
    def resolve_shipping_point(root, info):
        return root.get('shippingPoint')

    @staticmethod
    def resolve_over_delivery_tol(root, info):
        return root.get('deliveryTolOver')

    @staticmethod
    def resolve_under_delivery_tol(root, info):
        return root.get('deliveryTolOverUnder')

    @staticmethod
    def resolve_delivery_tol_unlimited(root, info):
        return root.get('untimatedTol')

    @staticmethod
    def resolve_sale_text_1(root, info):
        return root.get('saleText1_th')

    @staticmethod
    def resolve_sale_text_2(root, info):
        return root.get('saleText2_th')

    @staticmethod
    def resolve_sale_text_3(root, info):
        return root.get('saleText3_th')

    @staticmethod
    def resolve_sale_text_4(root, info):
        return root.get('saleText4_th')

    @staticmethod
    def resolve_item_category(root, info):
        return root.get('itemCategory')

    @staticmethod
    def resolve_material_group_1(root, info):
        return root.get('materialGroup1')

    @staticmethod
    def resolve_route_id(root, info):
        return root.get('routeId')

    @staticmethod
    def resolve_route_name(root, info):
        return root.get('routeName')

    @staticmethod
    def resolve_request_date(root, info):
        return DateHelper.sap_str_to_iso_str(root.get('requestedDate'))

    @staticmethod
    def resolve_original_request_date(root, info):
        order_line = root.get("order_line_instance")
        return order_line and (order_line.original_request_date or order_line.request_date)

    @staticmethod
    def resolve_weight_per_unit(root, info):
        return root.get('weightPerUnit')

    @staticmethod
    def resolve_order_qty(root, info):
        return root.get('orderQty')

    @staticmethod
    def resolve_confirm_qty(root, info):
        return root.get('comfirmQty')

    @staticmethod
    def resolve_delivery_qty(root, info):
        return root.get('deliveryQty')

    @staticmethod
    def resolve_assign_quantity(root, info):
        return root.get('comfirmQty')

    @staticmethod
    def resolve_delivery_status(root, info):
        return root.get('deliveryStatus')

    @staticmethod
    def resolve_prd_hierachy(root, info):
        return root.get('prdHierachy')

    @staticmethod
    def resolve_po_date(root, info):
        return datetime.strptime(root.get('poDates'), '%d/%m/%Y') if root.get("poDates") else None

    @staticmethod
    def resolve_reason_reject(root, info):
        return root.get('reasonReject')

    @staticmethod
    def resolve_confirmed_date(root, info):
        order_line = root.get("order_line_instance")
        order_line_cp = OrderLineCpRepo.get_order_line_cp_by_order_line_id(order_line.id) if order_line else False
        if not order_line_cp:
            return ""
        return order_line_cp.confirm_date

    @staticmethod
    def resolve_weight(root, info):
        return root.get('netWeight')

    @staticmethod
    def resolve_ref_pi_stock(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.ref_pi_no:
            return ""
        return order_line.ref_pi_no or ""

    @staticmethod
    def resolve_net_value(root, info):
        return root.get("totalNetPrice", 0)

    @staticmethod
    def resolve_request_date_change_reason(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.request_date_change_reason or ""

    @staticmethod
    def resolve_weight_display(root, info):
        return deepgetattr(root.get('order_line_instance', {}), 'weight_display', "TON")

    @staticmethod
    def resolve_po_status(root, info):
        po_status = root.get('poStatus', "")
        if po_status == "N":
            return POStatusEnum.N.value
        if po_status == "P":
            return POStatusEnum.P.value
        return ""

    @staticmethod
    def resolve_material_group1_desc(root, info):
        try:
            material_group = ProductGroupDescription[root.get('materialGroup1')].value
        except Exception as e:
            material_group = ""
            logging.info(
                f" Material group code : {root.get('materialGroup1')} exception: {e}"
            )
        return material_group

    @staticmethod
    def resolve_parent_item_no(root, info):
        return root.get('parentItemNo', "").lstrip("0")

    @staticmethod
    def resolve_price_per_unit(root, info):
        return root.get('netPricePerUnit')

    @staticmethod
    def resolve_net_weight(root, info):
        return root.get('netWeight')

    @staticmethod
    def resolve_price_currency(root, info):
        return root.get('priceCurrency')

    @staticmethod
    def resolve_gross_weight(root, info):
        return root.get('grossWeight')

    @staticmethod
    def resolve_sales_unit_list(root, info):
        is_bom_parent = root.get('bomFlag') and not root.get('parentItemNo')
        sales_unit_list = list(
            Conversion2MasterRepo.get_conversion_by_material_code(root.get('material'))) if not is_bom_parent else []
        if not any(unit.to_unit == root.get('salesUnit') for unit in sales_unit_list):
            sales_unit_list.append({
                "from_unit": root.get('weightUnit'),
                "calculation": root.get('netWeight', 0) / root.get('orderQty', 1),
                "to_unit": root.get('salesUnit'),
            })
        return sales_unit_list

    @staticmethod
    def resolve_batch_no(root, info):
        return root.get('batchNo')

    @staticmethod
    def resolve_batch_choice_flag(root, info):
        order_line = root.get("order_line_instance")
        return order_line.batch_choice_flag if order_line else False

    @staticmethod
    def resolve_batch_flag(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.get('material'))
        return material.batch_flag if material else False

    @staticmethod
    def resolve_bom_unit_quantity(root, info):
        return BomMaterialRepo.get_bom_unit_quantity(
            root.get('parentMaterial'), root.get('material')
        ) if root.get('parentItemNo') else None


class CipOrderViewData(graphene.ObjectType):
    id = graphene.ID()
    so_no = graphene.String()
    po_no = graphene.String()
    distribution_channel_code = graphene.String()
    distribution_channel_name = graphene.String()
    sales_org_code = graphene.String()
    sales_org_name = graphene.String()
    sales_org_short_name = graphene.String()
    sales_org_display_text = graphene.String()
    sales_off = graphene.String()
    sales_off_name = graphene.String()
    division_code = graphene.String()
    division_name = graphene.String()
    price_date = graphene.String()
    status = graphene.String()
    order_amt_before_vat = graphene.String()
    order_amt_vat = graphene.String()
    order_amt_after_vat = graphene.String()
    currency = graphene.String()
    request_date = graphene.String()
    payment_terms = graphene.String()
    payment_terms_display_text = graphene.String()
    sales_employee_display_text = graphene.String()
    order_date = graphene.String()
    sales_group_code = graphene.String()
    sales_group_name = graphene.String()
    sales_employee = graphene.String()
    sold_to_code = graphene.String()
    sold_to_display_text = graphene.String()
    bill_to_display_text = graphene.String()
    ship_to_display_text = graphene.String()

    internal_comments_to_logistic = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    production_information = graphene.String()
    form_header = graphene.String()
    header_note_1 = graphene.String()
    cash = graphene.String()

    unloading_point = graphene.String()
    dp = graphene.List(DPNo)
    invoice = graphene.List(InvoiceNo)
    order_partners = graphene.List(OrderPartners)
    otc_order_partners = graphene.List(OrderPartners)
    order_items = graphene.List(CipGetChangeOrderItemData)
    order_condition = graphene.List(OrderCondition)
    order_text = graphene.List(OrderText)
    item_no_latest = graphene.String()
    po_date = graphene.String()
    order_type = graphene.String()
    order_type_desc = graphene.String()
    tax_class = graphene.String()
    payment_term_list = graphene.List(graphene.String)
    one_time_flag = graphene.Boolean()

    @staticmethod
    def resolve_id(root, info):
        order_instance = info.variable_values.get("order_instance")
        return order_instance.id if order_instance else None

    @staticmethod
    def resolve_distribution_channel_name(root, info):
        if root.get('distribution_channel_code'):
            distribution_channel = DistributionChannelMasterRepo.get_distribution_channel_by_code(
                root.get('distribution_channel_code'))
            return distribution_channel.name if distribution_channel else ""
        return ""

    @staticmethod
    def resolve_sales_org_name(root, info):
        sales_org_instance = info.variable_values.get("sales_org_instance")
        return sales_org_instance.name if sales_org_instance else ""

    @staticmethod
    def resolve_sales_org_short_name(root, info):
        sales_org_instance = info.variable_values.get("sales_org_instance")
        return sales_org_instance.short_name if sales_org_instance else ""

    @staticmethod
    def resolve_sales_org_display_text(root, info):
        sales_org_instance = info.variable_values.get("sales_org_instance")
        return f"{root.get('sales_org_code')} - {sales_org_instance.short_name}" if sales_org_instance else ""

    @staticmethod
    def resolve_sales_off_name(root, info):
        if root.get('sales_off'):
            sales_off = SalesOfficeMasterRepo.get_sale_office_by_code(root.get('sales_off'))
            return sales_off.name if sales_off else ""
        return ""

    @staticmethod
    def resolve_division_name(root, info):
        if root.get('division_code'):
            division = DivisionMasterRepo.get_division_by_code(root.get('division_code'))
            return division.name if division else ""
        return ""

    @staticmethod
    def resolve_sales_group_name(root, info):
        if root.get('sales_group_code'):
            sales_group = SalesGroupMasterRepo.get_sales_group_by_sales_group_code(root.get('sales_group_code'))
            return sales_group.sales_group_description if sales_group else ""
        return ""

    @staticmethod
    def resolve_item_no_latest(root, info, **kwargs):
        order_instance = info.variable_values.get("order_instance")
        return getattr(order_instance, "item_no_latest", 0) if order_instance else 0

    @staticmethod
    def resolve_order_type_desc(root, info):
        if root.get('order_type'):
            return get_order_type_desc(root.get('order_type'))
        return ""

    @staticmethod
    def resolve_sold_to_display_text(root, info):
        split_list = re.split('-|\n', root.get("sold_to", ""))
        return f'{split_list[0]} - {split_list[1]}' if len(split_list) >= 2 else root.get("sold_to", "")

    @staticmethod
    def resolve_sales_employee_display_text(root, info):
        sales_employee = root.get("sales_employee", "")
        return sales_employee.split("-")[0].strip() if sales_employee.split("-") else sales_employee

    @staticmethod
    def resolve_payment_terms_display_text(root, info):
        return f'{root.get("payment_term")} - {PAYMENT_TERM_MAPPING.get(root.get("payment_term"))}' if root.get(
            "payment_term", "") else ""

    @staticmethod
    def resolve_bill_to_display_text(root, info):
        return root.get("bill_to", "")

    @staticmethod
    def resolve_ship_to_display_text(root, info):
        return root.get("ship_to", "")

    @staticmethod
    def resolve_payment_term_list(root, info):
        return PAYMENT_TERM_MAPPING.keys()

    @staticmethod
    def resolve_order_amt_before_vat(root, info):
        return root.get("total_price", "")

    @staticmethod
    def resolve_order_amt_vat(root, info):
        return root.get("tax_amount", "")

    @staticmethod
    def resolve_order_amt_after_vat(root, info):
        return root.get("total_price_inc_tax", "")

    @staticmethod
    def resolve_payment_terms(root, info):
        return root.get("payment_term", "")


class SapOrderMessages(graphene.ObjectType):
    id = graphene.String()
    item_no = graphene.String()
    error_code = graphene.String()
    so_no = graphene.String()
    error_message = graphene.String()


class SapItemMessages(graphene.ObjectType):
    item_no = graphene.String()
    error_message = graphene.String()
    error_code = graphene.String()
    id = graphene.String()


class CPMessage(graphene.ObjectType):
    id = graphene.String()
    item_no = graphene.String()
    error_message = graphene.String()
    error_code = graphene.String()


class CPItemMessage(graphene.ObjectType):
    parent_item_no = graphene.String()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    quantity = graphene.String()
    request_date = graphene.String()
    confirm_date = graphene.String()
    original_date = graphene.String()
    bom_flag = graphene.String()
    plant = graphene.String()
    parent_bom = graphene.String()
    show_in_popup = graphene.Boolean()


class WarningMessages(graphene.ObjectType):
    source = graphene.String()
    order = graphene.String()
    message = graphene.String()


class CancelDeleteCipOrderLinesInput(InputObjectType):
    item_no = graphene.String(required=True)
    status = CipCancelItemStatus(required=True)


class CipChangeOrderHeaderInput(InputObjectType):
    cp_need = graphene.Boolean(required=False)
    so_no = graphene.String()
    request_date = graphene.Date(
        required=False, description="date must be type yyyy-mm-dd"
    )
    payment_terms = graphene.String(required=False)
    po_no = graphene.String(required=False)
    sale_group_code = graphene.String(required=False)
    sales_employee = graphene.String(require=False)
    price_date = graphene.String(required=False)
    un_loading_point = graphene.String(required=False)
    tax_class = graphene.String(required=False)
    ship_to = graphene.String(required=False)
    bill_to = graphene.String(required=False)
    from_header = graphene.String(required=False)
    header_note1 = graphene.String(required=False)
    cash = graphene.String(required=False)
    internal_comments_to_warehouse = graphene.String(required=False)
    internal_comments_to_logistic = graphene.String(required=False)
    external_comments_to_customer = graphene.String(required=False)
    product_information = graphene.String(required=False)


class CipChangeOrderItemDetailsInput(InputObjectType):
    id = graphene.String()
    item_no = graphene.String()
    material_no = graphene.String()
    quantity = graphene.Float(required=False)
    unit = graphene.String(required=False)
    sale_qty_factor = graphene.Int(required=False)
    batch_no = graphene.String(required=False)
    batch_choice_flag = graphene.Boolean(required=False)
    plant = graphene.String(required=False)
    request_date = graphene.Date(
        required=False, description="date must be type yyyy-mm-dd"
    )
    price_per_unit = graphene.Float(required=False)
    payment_term = graphene.String(required=False)
    item_category = graphene.String(required=False)
    confirm_quantity = graphene.String(required=False)
    sap_confirm_qty = graphene.String(required=False)
    assigned_quantity = graphene.String(required=False)
    po_item_no = graphene.String(required=False)
    delivery_tol_over = graphene.Float(required=False)
    delivery_tol_under = graphene.Float(required=False)
    shipping_point = graphene.String(required=False)
    po_detail = graphene.String(required=False)
    ship_to = graphene.String(required=False)
    internal_comments_to_warehouse = graphene.String(required=False)
    external_comments_to_customer = graphene.String(required=False)
    internal_comments_to_logistic = graphene.String(required=False)
    remark = graphene.String(required=False)
    sale_text1 = graphene.String(required=False)
    sale_text2 = graphene.String(required=False)
    sale_text3 = graphene.String(required=False)
    sale_text4 = graphene.String(required=False)
    item_note = graphene.String(required=False)
    pr_item_text = graphene.String(required=False)
    lot_no = graphene.String(required=False)
    production_memo = graphene.String(required=False)
    production_flag = graphene.String(required=False)
    price_date = graphene.Date(
        required=False, description="date must be type yyyy-mm-dd"
    )
    manual_price_flag = graphene.Boolean()
    otc_ship_to = graphene.Field(
        CipOrderOtcPartnerInput,
        description="information about One Time Customer Ship TO",
        required=False,
    )


class CipChangeOrderEditInput(InputObjectType):
    header_details = graphene.Field(CipChangeOrderHeaderInput)

    item_details = NonNullList(
        CipChangeOrderItemDetailsInput,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ))


class OrderTypeResponse(ObjectType):
    value = graphene.String()
    label = graphene.String()
    bu = graphene.String()
