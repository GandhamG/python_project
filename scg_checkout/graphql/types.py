from __future__ import division

from datetime import datetime

import graphene
from django.contrib.auth import get_user_model
from graphene import relay, ObjectType, InputObjectType

from common.iplan.item_level_helpers import get_item_production_status, EOrderingProductionStatus

import scg_checkout.contract_order_update as fn

import sap_migration.models
from common.product_group import ProductGroupDescription
from common.weight_calculation import resolve_weight_other_products, resolve_weight_for_rol
import logging
from saleor.graphql.account.types import User, UserCountableConnection
from saleor.graphql.core.connection import CountableConnection
from saleor.graphql.core.fields import ConnectionField
from saleor.graphql.core.types import ModelObjectType, NonNullList
from saleor.graphql.meta.types import ObjectWithMetadata
from saleor.account.models import User as userModel
from sap_master_data import models as master_models
from sap_master_data.models import SoldToChannelMaster, CompanyMaster, SalesOrganizationMaster
from sap_migration import models as migration_models
from sap_migration.graphql import types as master_types
from sap_migration.graphql.enums import InquiryMethodType
from sap_migration.graphql.types import SoldToMaster, ScgCountableConnection
from scg_checkout import models
from scg_checkout.models import AlternatedMaterial
from sap_migration.models import MaterialVariantMaster
from scgp_cip.common.constants import SAP_RESPONSE_TRUE_VALUE
from scgp_cip.dao.master_repo.country_master_repo import CountryMasterRepo
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scg_checkout.graphql.helper import (
    from_api_response_es26_to_change_order,
    PAYMENT_TERM_MAPPING,
    deepgetattr,
    get_order_type_desc, is_other_product_group, get_mat_desc_from_master_for_alt_mat_old, get_sold_to_partner
)
from scg_checkout.graphql.enums import (
    IPLanResponseStatus,
    DeliveryUnlimited,
    UnitEnum,
    IPlanOrderItemStatus,
    LMSStatusText,
    IPlanOrderStatus,
    InquiryOrderConfirmationStatus,
    LMSStatusIdMapping,
    POStatusEnum,
    AlternatedMaterialLogChangeError
)
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text
from .enums import (
    MaterialType,
    ReasonForChangeRequestDateEnum,
    WeightUnitEnum,
    ScgOrderStatus,
    ScgOrderlineAtpCtpStatus,
    CancelItem
)

from .resolves import contracts
from .resolves.alternative_material import (
    resolve_materials_os,
    resolve_last_update_date,
)
from .resolves.checkouts import (
    resolve_checkout_lines,
    resolve_contract_product_variant,
    resolve_contract_product,
    resolve_product,
    resolve_product_variant,
    resolve_quantity,
    resolve_total_customers,
    resolve_total_products,
    resolve_purchase_unit,
    resolve_order_unit,
)
from .resolves.contracts import resolve_variants, get_sap_contract_items
from .resolves.orders import (
    resolve_contract_by_contract_product_id,
    resolve_contract_order_lines,
    resolve_contract_order_lines_without_split,
    resolve_order_lines_iplan,
    resolve_order_quantity_ton,
    resolve_split_items,
    resolve_ship_to_address,
    resolve_sold_to_address,
    resolve_bill_to_address,
    resolve_weight,
    resolve_description_en_preview_order,
    get_formatted_address_option_text,
    resolve_allow_change_inquiry_method,
)
from .resolves.product_variant import resolve_limit_quantity, resolve_weight_contract
from .sorters import (
    CheckoutLineSortingInput,
    ProductSortingInput,
    DomesticOrderLinesSortingInput,
)

finish_work = "จบงาน"
format_date_1 = "%Y/%m/%d"
format_date_2 = "%d/%m/%Y"


class Customer(User):
    id = graphene.ID(required=True)
    customer_no = graphene.String()

    class Meta:
        description = "Represents user data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = get_user_model()

    @staticmethod
    def resolve_customer_no(root, info):
        customer_no = "{:010d}".format(root.id)
        return customer_no


class CustomerCountableConnection(UserCountableConnection):
    class Meta:
        node = Customer


class CheckoutCompany(ModelObjectType):
    id = graphene.ID(description="ID of company")
    code = graphene.String(description="Code of company")
    name = graphene.String(description="Name of company")
    business_unit = graphene.Field(lambda: BusinessUnit)
    users = graphene.List(User)
    short_name = graphene.String(description="Short name of company")
    full_name = graphene.String(description="Full name of company")

    class Meta:
        model = master_models.CompanyMaster

    @staticmethod
    def resolve_users(root, info):
        return userModel.objects.filter(id=root.user__id)


class BusinessUnit(ModelObjectType):
    id = graphene.ID(description="ID of business_unit")
    name = graphene.String(description="name of business_unit")
    code = graphene.String(description="code of business_unit")
    companies = graphene.List(CheckoutCompany)

    class Meta:
        model = migration_models.BusinessUnits

    @staticmethod
    def resolve_companies(root, info):
        return master_models.CompanyMaster.objects.filter(business_unit_id=root.id).all()


class SalesOrganization(ModelObjectType):
    id = graphene.ID(description="ID of sales_organization")
    name = graphene.String(description="name of sales_organization")
    code = graphene.String(description="code of sales_organization")
    business_unit = graphene.Field(BusinessUnit)
    short_name = graphene.String()
    full_name = graphene.String()
    display_text = graphene.String()

    class Meta:
        model = master_models.SalesOrganizationMaster

    @staticmethod
    def resolve_display_text(root, info):
        return f'{root.code} - {root.short_name}'


class DistributionChannel(ModelObjectType):
    id = graphene.ID(description="ID of distribution_channel")
    name = graphene.String(description="name of distribution_channel")
    code = graphene.String(description="code of distribution_channel")
    display_text = graphene.String()

    class Meta:
        model = master_models.DistributionChannelMaster

    @staticmethod
    def resolve_display_text(root, info):
        return f'{root.code} - {root.name}'


class ScgDivision(ModelObjectType):
    id = graphene.ID(description="ID of division")
    name = graphene.String(description="name of division")
    code = graphene.String(description="code of division")

    class Meta:
        model = master_models.DivisionMaster


class SalesOffice(ModelObjectType):
    id = graphene.ID(description="ID of sales_office")
    name = graphene.String(description="name of sales_office")
    code = graphene.String(description="code of sales_office")

    class Meta:
        model = migration_models.SalesOfficeMaster


class SapMigrationCompany(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()
    business_unit = graphene.Field(BusinessUnit)

    class Meta:
        model = migration_models.CompanyMaster


class SalesGroup(ModelObjectType):
    id = graphene.ID(description="ID of sales_group")
    name = graphene.String(description="name of sales_group")
    code = graphene.String(description="code of sales_group")
    sales_organization = graphene.Field(SalesOrganization)
    company = graphene.Field(SapMigrationCompany)

    class Meta:
        model = migration_models.SalesGroupMaster


class TempProductVariant(ModelObjectType):
    id = graphene.ID(description="ID of product variant")
    code = graphene.String(description="code of product variant")
    name = graphene.String(description="name of product variant")
    weight = graphene.String(description="weight per unit")
    description_th = graphene.String()
    description_en = graphene.String()
    type = graphene.String()
    sales_unit = graphene.String()
    status = graphene.String()
    determine_type = graphene.String()
    key_combination = graphene.String()
    valid_from = graphene.Date()
    valid_to = graphene.Date()
    propose_reason = graphene.String()
    grade = graphene.String()
    basis_weight = graphene.String()
    diameter = graphene.String()
    grade_gram = graphene.String()
    dia = graphene.String()  # Fix old field for FE can run
    gram = graphene.String()  # Fix old field for FE can run
    width_of_roll = graphene.String()
    length_of_roll = graphene.String()
    variant_type = graphene.String()

    limit_quantity = graphene.Float()

    class Meta:
        model = migration_models.MaterialVariantMaster

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = info.variable_values.get("contractId", info.variable_values.get("cart_contract_id"))
        material_id = info.variable_values.get("productId", root.material.id)
        return resolve_limit_quantity(contract_id, material_id, root.code, info=info)

    @staticmethod
    def resolve_grade_gram(root, info):
        try:
            return root.code
        except:
            return None

    @staticmethod
    def resolve_dia(root, info):
        try:
            return root.diameter
        except:
            return None

    @staticmethod
    def resolve_gram(root, info):
        try:
            return root.basis_weight
        except:
            return None

    @staticmethod
    def resolve_width_of_roll(root, info):
        rs = root.material.materialclassificationmaster_set.first()
        if rs:
            return rs.roll_width or 0
        return 0

    @staticmethod
    def resolve_length_of_roll(root, info):
        rs = root.material.materialclassificationmaster_set.first()
        if rs:
            return rs.roll_length or 0
        return 0

    @staticmethod
    def resolve_weight(root, info):
        calculation = getattr(root, "calculation", 0)
        if not calculation:
            mat_code = root.code
            conversion_objects = (
                master_models.Conversion2Master.objects.filter(
                    material_code=mat_code,
                    to_unit="ROL",
                )
                .order_by("material_code", "-id")
                .distinct("material_code")
                .in_bulk(field_name="material_code")
            )
            conversion_object = conversion_objects.get(str(mat_code), None)
            calculation = 0
            if conversion_object:
                calculation = conversion_object.calculation
        return round(calculation / 1000, 3)


class MaterialInfo(ModelObjectType):
    id = graphene.ID(description="ID of product")
    name = graphene.String(description="name of product")
    sales_unit = graphene.String(description="unit of product")
    variants = graphene.List(TempProductVariant)
    code = graphene.String(description="Full code of product")
    grade = graphene.String()
    gram = graphene.String()
    dia = graphene.String(description="Dia of product")
    base_unit = graphene.String(description="Base unit of product")
    purchase_unit = graphene.String()
    description = graphene.String()
    order_unit = graphene.String()
    description_en = graphene.String()
    material_type = graphene.String()
    limit_quantity = graphene.Float()
    weight = graphene.Float()

    class Meta:
        model = master_models.MaterialMaster

    @staticmethod
    def resolve_variants(root, info):
        return resolve_variants(root, info)

    @staticmethod
    def resolve_grade(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.grade if material_class else None

    @staticmethod
    def resolve_gram(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.basis_weight if material_class else None

    @staticmethod
    def resolve_dia(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.diameter[0:3] if material_class and material_class.diameter else None

    @staticmethod
    def resolve_code(root, info):
        return root.material_code

    @staticmethod
    def resolve_name(root, info):
        return root.name

    @staticmethod
    def resolve_purchase_unit(root, info, **kwargs):
        return resolve_purchase_unit(root, info)

    @staticmethod
    def resolve_sales_unit(root, info, **kwargs):
        return root.base_unit

    @staticmethod
    def resolve_description(root, info, **kwargs):
        # TODO confirm if the description will get from en or th field
        return root.description_th

    @staticmethod
    def resolve_order_unit(root, info, **kwargs):
        return resolve_order_unit(root, info)

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = info.variable_values.get("contract_id")
        variant_code = root.material_code
        material_id = root.id
        return resolve_limit_quantity(contract_id, material_id, variant_code)

    @staticmethod
    def resolve_weight(root, info):
        material_code = root.material_code
        return resolve_weight_contract(material_code)


class TempProductVariantCountableConnection(CountableConnection):
    class Meta:
        node = MaterialInfo


class TempProduct(ModelObjectType):
    id = graphene.ID(description="ID of product")
    name = graphene.String(description="name of product")
    sales_unit = graphene.String(description="unit of product")
    variants = graphene.List(TempProductVariant)
    code = graphene.String(description="Full code of product")
    grade = graphene.String()
    gram = graphene.String()
    grade_gram = graphene.String(description="Short code of product")
    dia = graphene.String(description="Dia of product")
    base_unit = graphene.String(description="Base unit of product")
    purchase_unit = graphene.String()
    description = graphene.String()
    order_unit = graphene.String()
    description_en = graphene.String()
    material_type = graphene.String()
    limit_quantity = graphene.Float()
    weight = graphene.Float()
    material_code = graphene.String(description="material code of product")

    class Meta:
        model = master_models.MaterialMaster

    @staticmethod
    def resolve_material_code(root, info):
        return root.material_code

    @staticmethod
    def resolve_variants(root, info):
        return resolve_variants(root, info)

    @staticmethod
    def resolve_grade(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.grade if material_class else None

    @staticmethod
    def resolve_gram(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.basis_weight if material_class else None

    @staticmethod
    def resolve_dia(root, info):
        material_code = root.material_code
        material_class = master_models.MaterialClassificationMaster.objects.filter(material_code=material_code).first()
        return material_class.diameter[0:3] if material_class else None

    @staticmethod
    def resolve_grade_gram(root, info):
        material_code = root.material_code
        return material_code[0:10]

    @staticmethod
    def resolve_code(root, info):
        return root.material_code

    @staticmethod
    def resolve_name(root, info):
        return root.name

    @staticmethod
    def resolve_purchase_unit(root, info, **kwargs):
        return resolve_purchase_unit(root, info)

    @staticmethod
    def resolve_sales_unit(root, info, **kwargs):
        return root.base_unit

    @staticmethod
    def resolve_description(root, info, **kwargs):
        # TODO confirm if the description will get from en or th field
        return root.description_th

    @staticmethod
    def resolve_order_unit(root, info, **kwargs):
        return resolve_order_unit(root, info)

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = info.variable_values.get("contract_id")
        variant_code = root.material_code
        material_id = root.id
        return resolve_limit_quantity(contract_id, material_id, variant_code)

    @staticmethod
    def resolve_weight(root, info):
        material_code = root.material_code
        return resolve_weight_contract(material_code)


class TempProductCountableConnection(CountableConnection):
    class Meta:
        node = MaterialInfo


class TempContractProduct(ModelObjectType):
    id = graphene.ID(description="ID of contract product")
    name = graphene.String(description="name of product")
    price = graphene.Float()
    total = graphene.Float()
    remain = graphene.Float()
    sales_unit = graphene.String()
    product_id = graphene.ID(description="ID of material")
    product = graphene.Field(TempProduct)
    contract_id = graphene.ID(description="ID of contract")
    contract = graphene.Field(lambda: TempContract)
    plant = graphene.String()
    delivery_under = graphene.Float()
    delivery_over = graphene.Float()
    currency = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.String()
    material_description = graphene.String()
    item_no = graphene.String()
    mat_group_1 = graphene.String()
    prc_group_1 = graphene.String()
    mat_group1_desc = graphene.String()
    material_code = graphene.String(description="material code of product")

    class Meta:
        model = migration_models.ContractMaterial

    @staticmethod
    def resolve_name(root, info):
        return root.material.name

    @staticmethod
    def resolve_sales_unit(root, info):
        return root.weight_unit

    @staticmethod
    def resolve_product_id(root, info):
        return root.material_id

    @staticmethod
    def resolve_price(root, info):
        return root.price_per_unit

    @staticmethod
    def resolve_total(root, info):
        return root.total_quantity

    @staticmethod
    def resolve_remain(root, info):
        return root.remaining_quantity

    @staticmethod
    def resolve_product(root, info):
        return root.material

    def resolve_mat_group1_desc(root, info):
        if root.mat_group_1:
            return ProductGroupDescription[root.mat_group_1].value or ""
        return ""

    @staticmethod
    def resolve_material_code(root, info):
        return root.material.material_code


class TempContract(ModelObjectType):
    id = graphene.ID(description="ID of scg_contract")
    so_no = graphene.String(description="SO number of the order")
    contract_no = graphene.String()
    company = graphene.Field(CheckoutCompany)
    project_name = graphene.String()
    start_date = graphene.Date()
    end_date = graphene.Date()
    payment_term = graphene.String()
    products = graphene.List(TempContractProduct, sort_by=ProductSortingInput())
    customer = graphene.Field(SoldToMaster)
    po_date = graphene.Date()
    prc_group1 = graphene.String()
    ship_to = graphene.String()
    bill_to = graphene.String()
    external_comments_to_customer = graphene.String()
    product_information = graphene.String()
    sales_organization = graphene.Field(SalesOrganization)
    distribution_channel = graphene.Field(DistributionChannel)
    division = graphene.Field(ScgDivision)
    sales_group = graphene.Field(SalesGroup)
    sales_office = graphene.Field(SalesOffice)
    internal_comments_to_warehouse = graphene.String()
    currency = graphene.String()
    payment_term_key = graphene.String()
    payment_term_desc_th = graphene.String()
    remark = graphene.String()

    class Meta:
        model = migration_models.Contract

    @staticmethod
    def resolve_products(root, info, sort_by=None):
        info.variable_values.update({"contract_id": root.id})
        return contracts.resolve_products(root.id, sort_by, info)

    @staticmethod
    def resolve_contract_no(root, info, sort_by=None):
        return root.code

    @staticmethod
    def resolve_customer(root, info, sort_by=None):
        return root.sold_to

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_key + " - " + root.payment_term

    @staticmethod
    def resolve_payment_term_desc_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.payment_term_key, root.payment_term)


class TempContractCountableConnection(ScgCountableConnection):
    class Meta:
        node = TempContract


class BusinessUnitCountableConnection(CountableConnection):
    class Meta:
        node = BusinessUnit


class ContractCheckoutLine(ModelObjectType):
    id = graphene.ID(description="ID of checkout line")
    quantity = graphene.Float()
    price = graphene.Float()
    product = graphene.Field(TempProduct)
    variant = graphene.Field(TempProductVariant)
    contract_product = graphene.Field(TempContractProduct)
    selected = graphene.Boolean()

    class Meta:
        model = migration_models.CartLines

    @staticmethod
    def resolve_variant(root, info):
        return resolve_product_variant(root.material_variant_id)

    @staticmethod
    def resolve_product(root, info):
        info.variable_values.update({"cart_contract_id": root.contract_material.contract.id})
        return resolve_product(root.material_id)

    @staticmethod
    def resolve_contract_product(root, info):
        return root.contract_material


class ContractCheckoutLineCountableConnection(CountableConnection):
    class Meta:
        node = ContractCheckoutLine


class ContractCheckout(ModelObjectType):
    id = graphene.ID(description="ID of checkout")
    customer = graphene.Field(SoldToMaster)
    created_by = graphene.Field(User)
    contract = graphene.Field(TempContract)
    quantity = graphene.Float()
    lines = NonNullList(ContractCheckoutLine, sort_by=CheckoutLineSortingInput())

    class Meta:
        model = migration_models.Cart
        only_fields = ["created_by"]

    @staticmethod
    def resolve_lines(root, info, sort_by=None):
        return resolve_checkout_lines(root.id, sort_by)

    @staticmethod
    def resolve_quantity(root, info):
        return resolve_quantity(root.id)

    @staticmethod
    def resolve_customer(root, info, sort_by=None):
        return root.sold_to


class ContractCheckoutProductVariant(ModelObjectType):
    id = graphene.ID(description="ID of checkout")
    product_variant = graphene.List(TempProduct)
    contract_product = graphene.List(TempContractProduct)

    class Meta:
        model = migration_models.Cart
        only_fields = ["created_by"]

    @staticmethod
    def resolve_product_variant(root, info):
        info.variable_values.update({"cart_contract_id": root.contract_id})
        return resolve_contract_product_variant(root.id)

    @staticmethod
    def resolve_contract_product(root, info):
        return resolve_contract_product(root.id)


class ContractCheckoutCountableConnection(CountableConnection):
    class Meta:
        node = ContractCheckout


class ContractCheckoutTotal(ModelObjectType):
    total_customers = graphene.Int()
    total_products = graphene.Int()

    class Meta:
        model = migration_models.Cart

    @staticmethod
    def resolve_total_customers(root, info):
        return resolve_total_customers(info.context.user)

    @staticmethod
    def resolve_total_products(root, info):
        return resolve_total_products(info.context.user)


class TempOrder(ModelObjectType):
    id = graphene.ID()
    sold_to = graphene.Field(SoldToMaster)
    customer = graphene.Field(SoldToMaster)
    contract = graphene.Field(TempContract)
    po_date = graphene.Date()
    po_number = graphene.String()
    ship_to = graphene.String()
    bill_to = graphene.String()
    order_type = graphene.String()
    request_date = graphene.Date()
    sale_organization = graphene.Field(SalesOrganization)
    distribution_channel = graphene.Field(DistributionChannel)
    division = graphene.Field(ScgDivision)
    sale_office = graphene.Field(SalesOffice)
    sale_group = graphene.Field(SalesGroup)
    total_price = graphene.Float()
    order_lines = graphene.List(lambda: TempOrderLine)
    status = graphene.String()
    order_no = graphene.String()
    scgp_sales_employee = graphene.Field(lambda: ScgpSalesEmployee)
    created_by = graphene.Field(User)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    update_by = graphene.Field(User)
    so_no = graphene.String()
    type = graphene.String()
    contract_pi_no = graphene.String()
    company = graphene.Field(SapMigrationCompany)
    payment_term = graphene.String()
    credit_status = graphene.String()
    order_date = graphene.Date()
    status_sap = graphene.String()
    customer_group = graphene.Field(master_types.CustomerGroupMaster)
    customer_group_1 = graphene.Field(master_types.CustomerGroup1Master)
    customer_group_2 = graphene.Field(master_types.CustomerGroup2Master)
    customer_group_3 = graphene.Field(master_types.CustomerGroup3Master)
    customer_group_4 = graphene.Field(master_types.CustomerGroup4Master)
    dp_no = graphene.String()
    invoice_no = graphene.String()
    delivery_block = graphene.String()
    incoterm = graphene.String()
    incoterms_1 = graphene.Field(master_types.Incoterms1Master)
    order_lines_iplan = graphene.List("scgp_require_attention_items.graphql.types.OrderLineIPlan")
    shipping_point = graphene.String()
    route = graphene.String()
    po_no = graphene.String()
    total_price_inc_tax = graphene.Float()
    tax_amount = graphene.Float()
    currency = graphene.String()
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
    untimated_tol = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    internal_comments_to_logistic = graphene.String()
    external_comments_to_customer = graphene.String()
    product_information = graphene.String()
    sales_group = graphene.String()
    payment_term_key = graphene.String()
    payment_term_desc_th = graphene.String()
    po_upload_file_name = graphene.String()
    order_type_desc = graphene.String()

    class Meta:
        model = migration_models.Order

    @staticmethod
    def resolve_order_type_desc(root, info):
        order_type = getattr(root, "order_type", None)
        return get_order_type_desc(order_type)

    @staticmethod
    def resolve_po_upload_file_name(root, info):
        po_upload_file_name = getattr(root, "po_upload_file_log", None)
        return getattr(po_upload_file_name, "file_name", "")

    @staticmethod
    def resolve_payment_term_key(root, info):
        contract = getattr(root, "contract", None)
        return getattr(contract, "payment_term_key", "")

    @staticmethod
    def resolve_payment_term_desc_th(root, info):
        try:
            return PAYMENT_TERM_MAPPING.get(root.contract.payment_term_key, root.contract.payment_term)
        except Exception:
            return ""

    @staticmethod
    def resolve_order_lines(root, info):
        return resolve_contract_order_lines_without_split(root.id)

    @staticmethod
    def resolve_customer(root, info):
        return root.sold_to

    @staticmethod
    def resolve_contract_pi_no(root, info):
        contract = getattr(root, "contract", None)
        return getattr(contract, "code", "")

    @staticmethod
    def resolve_sale_organization(root, info):
        return root.sales_organization

    @staticmethod
    def resolve_sale_office(root, info):
        return root.sales_office

    @staticmethod
    def resolve_sale_group(root, info):
        return root.sales_group

    @staticmethod
    def resolve_order_lines_iplan(root, info):
        return resolve_order_lines_iplan(root.id)

    @staticmethod
    def resolve_total_price(root, info):

        return round(root.total_price, 2) if root.total_price else 0

    @staticmethod
    def resolve_total_price_inc_tax(root, info):
        return round(root.total_price_inc_tax, 2) if root.total_price_inc_tax else 0

    @staticmethod
    def resolve_tax_amount(root, info):
        return round(root.tax_amount, 2) if root.tax_amount else 0

    @staticmethod
    def resolve_ship_to_address(root, info):
        return resolve_ship_to_address(root, info)

    @staticmethod
    def resolve_sold_to_address(root, info):
        return resolve_sold_to_address(root, info)

    @staticmethod
    def resolve_bill_to_address(root, info):
        return resolve_bill_to_address(root, info)

    @staticmethod
    def resolve_tax_percent(root, info):
        return fn.get_tax_percent(root.sold_to.sold_to_code)

    @staticmethod
    def resolve_dp_no(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            # don't know why the hell SAP guys have to put this in another object
            dp_object = data[0].get("dp", {"dpNo": ""})

            return dp_object.get("dpNo", "")
        except:
            return root.dp_no

    @staticmethod
    def resolve_invoice_no(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            sap_invoice_obj = data[0].get("billing", [])

            if not sap_invoice_obj:
                return ""

            return sap_invoice_obj[0].get("billingNo", "")
        except:
            return ""

    @staticmethod
    def resolve_order_amt_before_vat(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return 0

            order_header_in = data[0].get("orderHeaderIn", {})

            return order_header_in.get("orderAmtBeforeVat") or 0
        except:
            return root.total_price

    @staticmethod
    def resolve_order_amt_vat(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return 0
            order_header_in = data[0].get("orderHeaderIn", {})

            return order_header_in.get("orderAmtVat") or 0
        except:
            return root.tax_amount

    @staticmethod
    def resolve_order_amt_after_vat(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return 0

            order_header_in = data[0].get("orderHeaderIn", {})

            return order_header_in.get("orderAmtAfterVat") or 0
        except:
            return root.total_price_inc_tax

    @staticmethod
    def resolve_currency(root, info):
        """
        As ticket 2453, we get currency from contract
        Todo: need to confirm later
        """
        try:
            return root.contract.currency
        except:
            return None

    @staticmethod
    def resolve_internal_comments_to_warehouse(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        if not sap_order_response:
            return root.internal_comments_to_warehouse
        try:
            data = sap_order_response.get("data", [])
            result = []

            if not data:
                return ""

            order_text_list = data[0].get("orderText", [])
            for order_text in order_text_list:
                if order_text.get("ItemNo") == "000000" and order_text.get("textId") == "Z001":
                    text_line_list = order_text.get("textLine")
                    for text_line in text_line_list:
                        result.append(text_line["text"])

            return '\n'.join(result)

        except:
            return root.internal_comments_to_warehouse

    @staticmethod
    def resolve_item_category(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            order_items = data[0].get("orderItems", [])

            return order_items[0].get("itemCategory", "")
        except:
            return ""

    @staticmethod
    def resolve_shipping_point(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            order_items = data[0].get("orderItems", [])

            return order_items[0].get("shippingPoint", "")
        except:
            return root.shipping_point

    @staticmethod
    def resolve_route_id(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            order_items = data[0].get("orderItems", [])

            return order_items[0].get("routeId", "")

        except:
            return ""

    @staticmethod
    def resolve_route_name(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])
            order_items = data[0].get("orderItems", [])

            return order_items[0].get("routeName", "")
        except:
            return ""

    @staticmethod
    def resolve_internal_comments_to_logistic(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        if not sap_order_response:
            return root.internal_comments_to_logistic
        try:
            data = sap_order_response.get("data", [])
            result = []

            if not data:
                return ""

            order_text_list = data[0].get("orderText", [])
            for order_text in order_text_list:
                if order_text.get("ItemNo") == "000000" and order_text.get("textId") == "Z002":
                    text_line_list = order_text.get("textLine")
                    for text_line in text_line_list:
                        result.append(text_line["text"])
            return '\n'.join(result)

        except:
            return root.internal_comments_to_logistic

    @staticmethod
    def resolve_po_no(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            order_header_in = data[0].get("orderHeaderIn", {})

            return order_header_in.get("poNo", "")

        except:
            return root.po_no

    @staticmethod
    def resolve_external_comments_to_customer(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        if not sap_order_response:
            return root.external_comments_to_customer
        try:
            data = sap_order_response.get("data", [])
            result = []

            if not data:
                return ""

            order_text_list = data[0].get("orderText", [])
            for order_text in order_text_list:
                if order_text.get("ItemNo") == "000000" and order_text.get("textId") == "Z067":
                    text_line_list = order_text.get("textLine")
                    for text_line in text_line_list:
                        result.append(text_line["text"])
            return '\n'.join(result)

        except:
            return root.external_comments_to_customer

    @staticmethod
    def resolve_untimated_tol(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            order_items = data[0].get("orderItems", [])

            return order_items[0].get("untimatedTol", "")

        except:
            return ""

    @staticmethod
    def resolve_product_information(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        if not sap_order_response:
            return root.product_information
        try:
            data = sap_order_response.get("data", [])
            result = []

            if not data:
                return ""

            order_text_list = data[0].get("orderText", [])
            for order_text in order_text_list:
                if order_text.get("ItemNo") == "000000" and order_text.get("textId") == "ZK08":
                    text_line_list = order_text.get("textLine")
                    for text_line in text_line_list:
                        result.append(text_line["text"])
            return '\n'.join(result)
        except:
            return root.product_information

    @staticmethod
    def resolve_sales_group(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        try:
            data = sap_order_response.get("data", [])

            if not data:
                return ""

            sales_group_object = data[0].get("orderHeaderIn", {})

            return sales_group_object.get("salesGroup", "")
        except:
            return ""


class TempOrderLine(ModelObjectType):
    id = graphene.ID()
    order = graphene.Field(TempOrder)
    product = graphene.Field(TempProduct)
    variant = graphene.Field(TempProductVariant)
    quantity = graphene.Float()
    plant = graphene.String()
    net_price = graphene.Float()
    price = graphene.Float()
    request_date = graphene.Date()
    internal_comments_to_warehouse = graphene.String()
    ship_to = graphene.String()
    product_information = graphene.String()
    payment_term = graphene.String()
    checkout_line = graphene.Field(ContractCheckoutLine)
    contract_product = graphene.Field(TempContractProduct)
    contract = graphene.Field(TempContract)
    confirmed_date = graphene.Date()
    item_no = graphene.String()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    attention_type = graphene.String()
    remark = graphene.String()
    dtr = graphene.String()
    dtp = graphene.String()
    original_request_date = graphene.Date()
    delivery = graphene.String()
    actual_gi_date = graphene.Date()
    gi_status = graphene.String()
    bill_to = graphene.String()
    external_comments_to_customer = graphene.String()
    internal_comments_to_logistic = graphene.String()
    shipping_point = graphene.String()
    route = graphene.String()
    price_currency = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.String()
    item_category = graphene.String()
    over_delivery_tol = graphene.Float()
    under_delivery_tol = graphene.Float()
    delivery_tol_unlimited = graphene.Boolean()
    po_no = graphene.String()
    prc_group_1 = graphene.String()
    po_date = graphene.Date()
    iplan = graphene.Field("scgp_require_attention_items.graphql.types.OrderLineIPlan")
    request_date_change_reason = graphene.String()
    po_no_external = graphene.String()
    payment_condition = graphene.String()
    unit = graphene.String()
    status = graphene.String()
    order_quantity_ton = graphene.Float()
    split_items = graphene.List(lambda: TempOrderLine)
    sales_unit = graphene.String()
    weight_unit_ton = graphene.String()
    net_weight_ton = graphene.String()
    atp_ctp_status = graphene.String()
    item_status_en = graphene.String()
    item_status_th = graphene.String()
    assigned_quantity = graphene.Float()
    inquiry_method = graphene.String()
    non_confirm_quantity = graphene.Float()
    confirm_quantity = graphene.Float()
    sap_confirm_status = graphene.String()
    description_en = graphene.String()
    remaining = graphene.Float()
    shipping_mark = graphene.String()
    status_enum = IPlanOrderStatus()

    class Meta:
        model = migration_models.OrderLines

    @staticmethod
    def resolve_contract_product(root, info):
        return root.contract_material

    @staticmethod
    def resolve_contract(root, info):
        return resolve_contract_by_contract_product_id(root.contract_material_id)

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_item

    @staticmethod
    def resolve_payment_condition(root, info):
        if root.contract_material is None:
            return None

        return root.contract_material.contract.payment_term

    @staticmethod
    def resolve_product(root, info):
        return root.material

    @staticmethod
    def resolve_price(root, info):
        return root.contract_material.price_per_unit

    @staticmethod
    def resolve_checkout_line(root, info):
        return root.cart_item

    @staticmethod
    def resolve_variant(root, info):
        info.variable_values.update({"contractId": root.order.contract.id})
        return root.material_variant

    @staticmethod
    def resolve_unit(root, info):
        # TODO: Confirm on with unit to return on ticket SEO-904
        return root.sales_unit

    @staticmethod
    def resolve_order_quantity_ton(root, info):
        return root.net_weight_ton

    @staticmethod
    def resolve_split_items(root, info):
        return resolve_split_items(root.id)

    @staticmethod
    def resolve_sales_unit(root, info):
        return root.contract_material.weight_unit

    @staticmethod
    def resolve_under_delivery_tol(root, info):
        return root.delivery_tol_under

    @staticmethod
    def resolve_over_delivery_tol(root, info):
        return root.delivery_tol_over

    @staticmethod
    def resolve_remark(root, info):
        return root.shipping_mark

    @staticmethod
    def resolve_weight(root, info):
        try:
            if not root.weight and root.prc_group_1:
                if is_other_product_group(root.prc_group_1):
                    return resolve_weight_other_products(root, info)
                else:
                    return resolve_weight_for_rol(root, info)
            else:
                return root.weight
        except Exception as e:
            logging.info(f"[resolve weight] exception {e}")
            return resolve_weight_for_rol(root, info)

    @staticmethod
    def resolve_description_en(root, info):
        return resolve_description_en_preview_order(root.material_variant.code)

    @staticmethod
    def resolve_remaining(root, info):
        try:
            contract_material_id = root.contract_material.id
            contract_mat = sap_migration.models.ContractMaterial.objects.filter(
                id=contract_material_id
            ).first()
            contract_remaining = contract_mat.remaining_quantity if contract_mat else 0
            return contract_remaining
        except AttributeError:
            return 0


class PreviewTempOrderLine(TempOrderLine):
    log_errors = graphene.String()
    log_old_product = graphene.String()

    class Meta:
        model = migration_models.OrderLines

    @staticmethod
    def resolve_log_errors(root, info):
        try:
            alternated_material = AlternatedMaterial.objects.get(order_line_id=root.id,
                                                                 error_type=AlternatedMaterialLogChangeError
                                                                 .NO_STOCK_ALT_MAT.value)
            error_type = alternated_material.error_type
            return error_type
        except AlternatedMaterial.DoesNotExist:
            return None

    @staticmethod
    def resolve_log_old_product(root, info):
        try:
            alternated_material = AlternatedMaterial.objects.get(order_line_id=root.id, error_type__isnull=True)
            old_product = MaterialVariantMaster.objects.get(id=alternated_material.old_product_id)
        except (AlternatedMaterial.DoesNotExist, MaterialVariantMaster.DoesNotExist):
            return None
        return get_mat_desc_from_master_for_alt_mat_old(old_product)


class ScgSoldTo(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()
    address_text = graphene.String()
    representatives = NonNullList(User, description="List of all user.")
    display_text = graphene.String()

    class Meta:
        description = "SoldTo data."
        model = models.ScgSoldTo

    @staticmethod
    def resolve_display_text(root, info):
        return f"{root.code} - {root.name}"


class SoldToCountableConnection(CountableConnection):
    class Meta:
        node = ScgSoldTo


class AlternativeMaterial(ModelObjectType):
    id = graphene.ID()
    sales_organization = graphene.Field(SalesOrganization)
    sold_to = graphene.Field(SoldToMaster)
    material_own = graphene.Field(MaterialInfo)
    type = graphene.String(description="Type of Alternative material")
    materials_os = graphene.List(lambda: AlternativeMaterialOs)
    created_by = graphene.Field(
        "saleor.graphql.account.types.User",
    )
    updated_by = graphene.Field(
        "saleor.graphql.account.types.User",
    )
    created_at = graphene.DateTime(required=True)
    updated_at = graphene.DateTime(required=True)

    class Meta:
        description = "Alternative material data."
        model = migration_models.AlternateMaterial

    @staticmethod
    def resolve_materials_os(root, info):
        return resolve_materials_os(root.id)


class AlternativeMaterialOs(ModelObjectType):
    id = graphene.ID()
    alternative_material = graphene.Field(AlternativeMaterial)
    material_os = graphene.Field(MaterialInfo)
    priority = graphene.Int(description="Priority of Alternative material.", required=True)
    diameter = graphene.String()

    class Meta:
        description = "Alternative material os data."
        model = migration_models.AlternateMaterialOs

    @staticmethod
    def resolve_alternative_material(root, info):
        return root.alternate_material


class AlternativeMaterialCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")

    class Meta:
        node = AlternativeMaterial


class AlternativeMaterialOsCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")
    last_update_date = graphene.DateTime(description="last_update_event")

    class Meta:
        node = AlternativeMaterialOs

    @staticmethod
    def resolve_last_update_date(info, root):
        return resolve_last_update_date()


class ScgCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")

    class Meta:
        abstract = True


class TempOrderCountableConnection(ScgCountableConnection):
    class Meta:
        node = TempOrder


class ScgpMaterialGroup(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()

    class Meta:
        model = models.ScgpMaterialGroup


class ScgpSalesEmployee(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()

    class Meta:
        model = migration_models.Order

    @staticmethod
    def resolve_name(root, info):
        return root.sales_employee.split(' - ')[1] if root.sales_employee and len(
            root.sales_employee.split(' - ')) > 1 else ""

    @staticmethod
    def resolve_code(root, info):
        return root.sales_employee.split(' - ')[0] if root.sales_employee else ""


class ALternatedMaterial(ModelObjectType):
    id = graphene.ID()
    order_line = graphene.Field(TempOrderLine)
    old_product = graphene.Field(MaterialInfo)
    new_product = graphene.Field(MaterialInfo)
    error_type = graphene.String()
    quantity_change_of_roll = graphene.Float()
    quantity_change_of_ton = graphene.Float()

    class Meta:
        model = models.AlternatedMaterial


class AlternatedMaterialCountableConnection(ScgCountableConnection):
    class Meta:
        node = ALternatedMaterial


class OrderDraft(graphene.ObjectType):
    unique_id = graphene.String()
    id = graphene.Int()
    status = graphene.String()
    contract_pi_no = graphene.String()
    sold_to = graphene.String()
    created_by = graphene.Field(lambda: User)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    type = graphene.String()

    class Meta:
        model = models.ScgOrderView

    @staticmethod
    def resolve_contract_pi_no(root, info):
        contract_no = "{:010d}".format(int(root.contract_pi_no))
        return contract_no


class OrderDraftCountableConnection(ScgCountableConnection):
    class Meta:
        node = OrderDraft


class DomesticSoldToCountableConnection(CountableConnection):
    class Meta:
        node = SoldToMaster


class DomesticMaterialCodeNameCountableConnection(CountableConnection):
    class Meta:
        node = TempProductVariant


class SalesEmployee(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_migration.models.SalesEmployee


class DomesticSaleEmployeeCountableConnection(CountableConnection):
    class Meta:
        node = SalesEmployee


class DomesticCompanyCountTableConnection(CountableConnection):
    class Meta:
        node = SapMigrationCompany


class DomesticSalesGroupCountTableConnection(CountableConnection):
    class Meta:
        node = SalesGroup


class DomesticOrderTypeEnums(ObjectType):
    name = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_name(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class RealtimePartner(ObjectType):
    partner_function = graphene.String()
    partner_function_desc = graphene.String()
    partner_no = graphene.String()
    partner_name = graphene.String()
    display_text = graphene.String()
    address_text = graphene.String()

    @staticmethod
    def resolve_partner_function(root, info):
        return root["partnerFunction"]

    @staticmethod
    def resolve_partner_function_desc(root, info):
        return root["partnerFunctionDes"]

    @staticmethod
    def resolve_partner_no(root, info):
        return root["partnerNo"]

    @staticmethod
    def resolve_partner_name(root, info):
        return root["partnerName"]

    @staticmethod
    def resolve_display_text(root, info):
        return f"{root['partnerNo']} - {root['partnerName']}"

    @staticmethod
    def resolve_address_text(root, info):
        return get_formatted_address_option_text(root["partnerNo"])


class DomesticOrderLinesCountableConnection(ScgCountableConnection):
    class Meta:
        node = PreviewTempOrderLine


class PreviewDomesticOrderLines(TempOrder):
    class Meta:
        model = migration_models.Order

    preview_order_lines = ConnectionField(lambda: DomesticOrderLinesCountableConnection,
                                          sort_by=DomesticOrderLinesSortingInput())

    @staticmethod
    def resolve_preview_order_lines(root, info, **kwargs):
        qs = resolve_contract_order_lines(root.id)
        return resolve_connection_slice(qs, info, kwargs, DomesticOrderLinesCountableConnection)


class ShowATPCTPPopup(ObjectType):
    status = graphene.Boolean()
    item_errors = graphene.List(graphene.String)
    flag = graphene.String()


class OrderEnums(ObjectType):
    name = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_name(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class OrderEmailRecipient(ObjectType):
    to = graphene.String()
    cc = graphene.String()


class MaterialCodeDescriptionCountableConnection(CountableConnection):
    class Meta:
        node = TempProductVariant


class EmailPendingOrder(ObjectType):
    sold_to_name = graphene.String()
    to = graphene.String()
    cc = graphene.String()


class salesOrgSoldTo(ObjectType):
    code = graphene.String()
    name = graphene.String()
    short_name = graphene.String()
    full_name = graphene.String()

    class Meta:
        Model = SalesOrganizationMaster


class DeliveryDateInput(graphene.InputObjectType):
    gte = graphene.Date()
    lte = graphene.Date()


class LMSReportCSAdmin(ObjectType):
    dp_no = graphene.String()
    po_no = graphene.String()
    so_no = graphene.String()
    item_no = graphene.String()
    material_description = graphene.String()
    quantity = graphene.Float()
    sale_unit = graphene.String()
    sold_to_code_name = graphene.String()
    ship_to_name = graphene.String()
    gi_date_time = graphene.String()
    car_registration_no = graphene.String()
    departure_place_position = graphene.String()
    estimate_date_time = graphene.String()
    transportation_status = graphene.String()
    current_position = graphene.String()
    remaining_distance_as_kilometers = graphene.String()
    estimated_arrival_date_and_time = graphene.String()


class GPSTracking(ObjectType):
    shipment_no = graphene.String()
    car_registration_no = graphene.String()
    current_position = graphene.String()
    carrier = graphene.String()
    speed = graphene.Float()
    date_and_time_of_the_last_signal_received = graphene.String()
    payment_no = graphene.String()
    place_of_delivery = graphene.String()
    car_status = graphene.String()
    destination_reach_time = graphene.String()
    estimate_to_customers_from_their_current_location = graphene.String()
    approximate_remaining_distance = graphene.Float()
    estimated_time = graphene.String()
    estimated_arrival_time = graphene.String()
    distance_from_factory_to_customer = graphene.Float()
    date_of_issuance_of_invoice = graphene.String()
    delivery_deadline = graphene.String()


class DPHyperLinkDetail(ObjectType):
    dp_no = graphene.String()
    po_no = graphene.String()
    so_no = graphene.String()
    item_no = graphene.String()
    material_description = graphene.String()
    quantity = graphene.Float()
    sale_unit = graphene.String()


class DPHyperLink(ObjectType):
    total_quantity = graphene.Float()
    dp_no_lines = graphene.List(
        DPHyperLinkDetail
    )


class LMSReportCSAdminInput(graphene.InputObjectType):
    sale_org = graphene.String()
    delivery_date = graphene.Field(DeliveryDateInput)
    sold_to = graphene.String()
    shipping_point = graphene.String()
    material_grade_gram = graphene.String()
    po_no = graphene.String()
    so_no = graphene.String()


class SAPChangeOrder(graphene.ObjectType):
    so_no = graphene.String()
    po_no = graphene.String()
    contract_no = graphene.String()
    sold_to_party = graphene.String()
    ship_to = graphene.String()
    country = graphene.String()
    incoterm = graphene.String()
    payment = graphene.String()
    bu = graphene.String()
    project_name = graphene.String()
    company = graphene.String()
    payment_terms = graphene.String()
    credit_status_of_document = graphene.String()
    order_date = graphene.String()
    order_status_sap = graphene.String()
    order_status_e_ordering = graphene.String()
    sales_org_code = graphene.String()
    sold_to_code = graphene.String()
    is_not_ref = graphene.Boolean()


class TelNoList(graphene.ObjectType):
    tel_no = graphene.String()
    tel_no_ext = graphene.String()

    @staticmethod
    def resolve_tel_no(root, info):
        return root.get('telNo', "")

    @staticmethod
    def resolve_tel_no_ext(root, info):
        return root.get('telNoExt', "")


class OrderTaxNumber(graphene.ObjectType):
    tax_number1 = graphene.String()
    tax_number2 = graphene.String()
    tax_id = graphene.String()
    branch_id = graphene.String()

    @staticmethod
    def resolve_tax_number1(root, info):
        return root.get('taxNumber1', "")

    @staticmethod
    def resolve_tax_number2(root, info):
        return root.get('taxNumber2', "")

    @staticmethod
    def resolve_tax_id(root, info):
        return root.get('taxId', "")

    @staticmethod
    def resolve_branch_id(root, info):
        return root.get('branchId', "")


class PartnersAddress(graphene.ObjectType):
    addr_no = graphene.String()
    name = graphene.String()
    city = graphene.String()
    post_code = graphene.String()
    district = graphene.String()
    street = graphene.String()
    transpzone = graphene.String()
    country = graphene.String()
    name_for_partners = graphene.String()
    location = graphene.String()
    str_suppl1 = graphene.String()
    str_suppl2 = graphene.String()
    str_suppl3 = graphene.String()
    tel_no_list = graphene.List(TelNoList)
    mobile_no = graphene.String()
    fax_no = graphene.String()
    fax_no_ext = graphene.String()
    language = graphene.String()
    order_tax_number = graphene.Field(OrderTaxNumber)
    country_name = graphene.String()

    @staticmethod
    def resolve_name_for_partners(root, info):
        name_for_partners = info.variable_values.get("name_for_partners", "")
        return name_for_partners

    @staticmethod
    def resolve_addr_no(root, info):
        return root.get('addrNo', "")

    @staticmethod
    def resolve_name(root, info):
        return root.get('name', "")

    @staticmethod
    def resolve_city(root, info):
        return root.get('city', "")

    @staticmethod
    def resolve_post_code(root, info):
        return root.get('postCode', "")

    @staticmethod
    def resolve_district(root, info):
        return root.get('district', "")

    @staticmethod
    def resolve_street(root, info):
        return root.get('street', "")

    @staticmethod
    def resolve_transpzone(root, info):
        return root.get('transpzone', "")

    @staticmethod
    def resolve_country(root, info):
        return root.get('country', "")

    @staticmethod
    def resolve_country_name(root, info):
        county_code = root.get('country', "")
        country = CountryMasterRepo.get_country_by_code(county_code)
        return country.country_name if country else county_code

    @staticmethod
    def resolve_str_suppl1(root, info):
        return root.get('strSuppl1', "")

    @staticmethod
    def resolve_str_suppl2(root, info):
        return root.get('strSuppl2', "")

    @staticmethod
    def resolve_str_suppl3(root, info):
        return root.get('strSuppl3', "")

    @staticmethod
    def resolve_location(root, info):
        return root.get('location', "")

    @staticmethod
    def resolve_tel_no_list(root, info):
        return root.get('telNoList', "")

    @staticmethod
    def resolve_mobile_no(root, info):
        return root.get('mobileNo', "")

    @staticmethod
    def resolve_fax_no(root, info):
        return root.get('faxNo', "")

    @staticmethod
    def resolve_fax_no_ext(root, info):
        return root.get('faxNoExt', "")

    @staticmethod
    def resolve_order_tax_number(root, info):
        return root.get('orderTaxNumber')


class OrderPartners(graphene.ObjectType):
    partner_role = graphene.String()
    partner_no = graphene.String()
    addr_link = graphene.String()
    payer_name = graphene.String()
    address = graphene.List(PartnersAddress)
    item_no = graphene.String()
    one_time_flag = graphene.Boolean()

    @staticmethod
    def resolve_partner_role(root, info):
        return root.get('partnerRole')

    @staticmethod
    def resolve_partner_no(root, info):
        partner_no = root.get("partnerNo")
        name = resolve_display_text(partner_no)
        info.variable_values.update({"name_for_partners": name})
        return root.get('partnerNo')

    @staticmethod
    def resolve_addr_link(root, info):
        return root.get('addrLink')

    @staticmethod
    def resolve_condition_unit(root, info):
        return root.get('address')

    @staticmethod
    def resolve_payer_name(root, info):
        payer_code = root.get('partnerNo')
        payer_name = resolve_display_text(payer_code)
        return payer_name

    @staticmethod
    def resolve_item_no(root, info):
        return root.get('itemNo', '000000')

    @staticmethod
    def resolve_one_time_flag(root, info):
        return SAP_RESPONSE_TRUE_VALUE == root.get("oneTimeFlag")

    @staticmethod
    def resolve_address(root, info):
        return root.get('address', [])


class DPNo(graphene.ObjectType):
    dp_no = graphene.String()

    @staticmethod
    def resolve_dp_no(root, info):
        return root.get('dpNo')


class InvoiceNo(graphene.ObjectType):
    invoice_no = graphene.String()

    @staticmethod
    def resolve_invoice_no(root, info):
        return root.get('billingNo')


class OrderItems(graphene.ObjectType):
    id = graphene.ID()
    item_no = graphene.String()
    material = graphene.String()
    material_desc = graphene.String()
    item_qty = graphene.String()
    item_remain = graphene.String()
    sales_unit = graphene.String()
    plant = graphene.String()
    payment_term = graphene.String()
    payment_term_desc_th = graphene.String()
    po_number = graphene.String()
    po_subcontract = graphene.String()
    item_category = graphene.String()
    material_group_1 = graphene.String()
    sale_text1_th = graphene.String()
    route_id = graphene.String()
    route_name = graphene.String()
    requested_date = graphene.String()
    original_request_date = graphene.String()
    weight_per_unit = graphene.String()
    order_qty = graphene.String()
    comfirm_qty = graphene.String()
    delivery_qty = graphene.String()
    delivery_status = graphene.String()
    sale_qty_division = graphene.String()
    sale_qty_factor = graphene.String()
    prd_hierachy = graphene.String()
    shipping_point = graphene.String()
    po_date = graphene.String()
    contract_no = graphene.String()
    contract_item_no = graphene.String()
    atp = graphene.String()
    atp_details = graphene.String()
    block = graphene.String()
    run = graphene.String()
    paper_machine = graphene.String()
    reason_reject = graphene.String()
    confirmed_date = graphene.String()
    product_material = graphene.String()
    remain_weight = graphene.Float()
    weight = graphene.Float()
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    internal_comments_to_logistic = graphene.String()
    product__information = graphene.String()
    over_delivery_tol = graphene.Float()
    under_delivery_tol = graphene.Float()

    delivery_tol_over = graphene.Float()
    delivery_tol_under = graphene.Float()

    delivery_tol_unlimited = graphene.String()
    untimated_tol = graphene.String()
    ship_to = graphene.String()
    ref_pi_stock = graphene.String()
    contract_product_id = graphene.ID()
    assign_quantity = graphene.Float()
    condition_group_1 = graphene.String()
    inquiry_method = graphene.String()
    order_type = graphene.String()
    flag_r5 = graphene.Boolean()
    item_status_en = graphene.String()
    item_status_en_display_text = graphene.String()
    item_status_enum = IPlanOrderItemStatus()
    item_production_state = EOrderingProductionStatus()
    is_material_outsource = graphene.Boolean()
    remaining_quantity = graphene.Float()
    net_price = graphene.Float()
    allow_change_inquiry_method = graphene.Boolean()
    request_date_change_reason = graphene.String()
    sap_confirm_status = graphene.String()
    remaining_quantity_ex = graphene.Float()
    weight_display = graphene.String()
    po_status = graphene.String()
    material_group1_desc = graphene.String()
    weight_unit = graphene.String()
    gross_weight_ton = graphene.Float()
    net_weight_ton = graphene.Float()
    weight_unit_ton = graphene.String()
    pr_no = graphene.String()
    pr_item = graphene.String()
    shipping_mark = graphene.String()

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
    def resolve_flag_r5(root, info):
        order_line = root.get("order_line_instance")
        if order_line and order_line.attention_type and "R5" in order_line.attention_type:
            return True
        else:
            return False

    @staticmethod
    def resolve_order_type(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.iplan and order_line.iplan.order_type or ""

    @staticmethod
    def resolve_sap_confirm_status(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.sap_confirm_status or ""

    @staticmethod
    def resolve_contract_product_id(root, info):
        contract_no = root.get("contractNo", "")
        material_code = root.get("material", "")
        product_material = OrderItems.resolve_product_material(root, info)
        contract_item_no = root.get("contractItemNo", None)
        contract_material = []
        if contract_item_no:
            contract_material = sap_migration.models.ContractMaterial.objects.filter(
                contract_no=contract_no,
                material_code__in=(material_code, product_material),
                item_no=contract_item_no, )
        if contract_item_no is None or not contract_material:
            contract_material = sap_migration.models.ContractMaterial.objects.filter(
                contract_no=contract_no,
                material_code__in=(material_code, product_material))
        contract_material = {x.material_code: x for x in contract_material}
        contract_material_object = contract_material.get(material_code) or contract_material.get(product_material)
        return getattr(contract_material_object, "id", None)

    @staticmethod
    def resolve_under_delivery_tol(root, info):
        return root.get('deliveryTolOverUnder')

    @staticmethod
    def resolve_over_delivery_tol(root, info):
        return root.get('deliveryTolOver')

    @staticmethod
    def resolve_delivery_tol_under(root, info):
        return root.get('deliveryTolOverUnder')

    @staticmethod
    def resolve_delivery_tol_over(root, info):
        return root.get('deliveryTolOver')

    @staticmethod
    def resolve_atp(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        return order_line.iplan.atp_ctp or ""

    @staticmethod
    def resolve_id(root, info):
        order_line = root.get("order_line_instance")
        return order_line.id if order_line else None

    @staticmethod
    def resolve_atp_details(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        return order_line.iplan.order_type or ""

    @staticmethod
    def resolve_block(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        return order_line.iplan.block or ""

    @staticmethod
    def resolve_run(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        return order_line.iplan.run or ""

    @staticmethod
    def resolve_paper_machine(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        return order_line.iplan.paper_machine or ""

    @staticmethod
    def resolve_assign_quantity(root, info):
        order_line = root.get("order_line_instance")
        if not order_line:
            return 0
        return order_line.assigned_quantity if order_line.assigned_quantity else 0

    @staticmethod
    def resolve_item_no(root, info):
        return root.get('itemNo')

    @staticmethod
    def resolve_material(root, info):
        return root.get('material')

    @staticmethod
    def resolve_material_desc(root, info):
        return root.get('materialDesc')

    @staticmethod
    def resolve_item_remain(root, info):
        material_code = root.get('material')
        contract_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')

        contract_mat = sap_migration.models.ContractMaterial.objects.filter(
            contract_no=contract_no,
            material_code=material_code,
        ).first()
        contract_remaining = contract_mat and contract_mat.remaining_quantity or 0

        order_items = from_api_response_es26_to_change_order(info, 'orderItems')
        order_item_quantity = sum(
            [float(x.get('orderQty', 0)) for x in order_items if x and x.get('material') == material_code])
        try:
            for order_item in order_items:
                if order_item.get("material") == material_code:
                    sale_qty_factor = 1000 if order_item.get("salesUnit") == "EA" else order_item.get("saleQtyFactor")

            conversion_rate = (1000 / sale_qty_factor)
            contract_remaining *= conversion_rate
            return round(contract_remaining + order_item_quantity, 3)
        except:
            return contract_remaining + order_item_quantity

    @staticmethod
    def resolve_product_material(root, info):
        item_material = root.get('material', "")
        material_variant = sap_migration.models.MaterialVariantMaster.objects. \
            filter(code=item_material, variant_type__in=('Standard', 'Non-Standard')).first()
        material = getattr(material_variant, 'material', None)
        return getattr(material, "material_code", "")

    @staticmethod
    def resolve_remain_weight(root, info):
        contract_items = None
        item_no = root.get('contractItemNo')
        contract_no = root.get('contractNo')
        sap_order_response = info.variable_values.get("sap_order_response")
        if sap_order_response:
            contract_items = sap_order_response.get("contractItem")
        if contract_items is None:
            response = get_sap_contract_items(info.context.plugins.call_api_sap_client, contract_no=contract_no)
            contract_items = next((x for x in response.get('data', {})), {}).get('contractItem', [])
            sap_order_response["contractItem"] = contract_items
            info.variable_values.update({"sap_order_response": sap_order_response})
        remain_weight = next((x for x in contract_items if x.get("itemNo") == item_no), {}).get("RemainQty", 0)
        return remain_weight

    @staticmethod
    def resolve_weight(root, info):
        order_line = root.get("order_line_instance")
        if order_line and order_line.weight:
            return order_line.weight

        material_code = root.get('material')
        return resolve_weight_contract(material_code)

    @staticmethod
    def resolve_item_qty(root, info):
        return root.get('itemQty')

    @staticmethod
    def resolve_sales_unit(root, info):
        return root.get('salesUnit')

    @staticmethod
    def resolve_plant(root, info):
        return root.get('plant')

    @staticmethod
    def resolve_payment_term(root, info):
        return root.get('paymentTerm')

    @staticmethod
    def resolve_po_number(root, info):
        return root.get('poNumber')

    @staticmethod
    def resolve_item_category(root, info):
        return root.get('itemCategory')

    @staticmethod
    def resolve_material_group_1(root, info):
        return root.get('materialGroup1')

    @staticmethod
    def resolve_sale_text1_th(root, info):
        return root.get('saleText1_th')

    @staticmethod
    def resolve_route_id(root, info):
        return root.get('routeId')

    @staticmethod
    def resolve_route_name(root, info):
        return root.get('routeName')

    @staticmethod
    def resolve_requested_date(root, info):
        return root.get('requestedDate')

    @staticmethod
    def resolve_delivery_tol_unlimited(root, info):
        return root.get('untimatedTol')

    @staticmethod
    def resolve_untimated_tol(root, info):
        return root.get('untimatedTol')

    @staticmethod
    def resolve_weight_per_unit(root, info):
        return root.get('weightPerUnit')

    @staticmethod
    def resolve_order_qty(root, info):
        return root.get('orderQty')

    @staticmethod
    def resolve_comfirm_qty(root, info):
        return root.get('comfirmQty')

    @staticmethod
    def resolve_delivery_qty(root, info):
        return root.get('deliveryQty')

    @staticmethod
    def resolve_delivery_status(root, info):
        return root.get('deliveryStatus')

    @staticmethod
    def resolve_sale_qty_division(root, info):
        return root.get('saleQtyDivision')

    @staticmethod
    def resolve_sale_qty_factor(root, info):
        return root.get('saleQtyFactor')

    @staticmethod
    def resolve_prd_hierachy(root, info):
        return root.get('prdHierachy')

    @staticmethod
    def resolve_shipping_point(root, info):
        order_line = root.get("order_line_instance")
        return getattr(order_line, "shipping_point", "") or ""

    @staticmethod
    def resolve_item_status_en(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.item_status_en and IPlanOrderItemStatus.get(
            order_line.item_status_en).name or ""

    @staticmethod
    def resolve_item_status_en_display_text(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.item_status_en or ""

    @staticmethod
    def resolve_po_date(root, info):
        return datetime.strptime(root.get('poDates'), '%d/%m/%Y') if root.get("poDates") else None

    @staticmethod
    def resolve_contract_no(root, info):
        return root.get('contractNo')

    @staticmethod
    def resolve_contract_item_no(root, info):
        return root.get('contractItemNo')

    @staticmethod
    def resolve_reason_reject(root, info):
        order_line = root.get("order_line_instance")
        if order_line.item_status_en == IPlanOrderItemStatus.CANCEL.value:
            return "93"
        return root.get('reasonReject')

    @staticmethod
    def resolve_confirmed_date(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.iplan:
            return ""
        if order_line.return_status in [IPLanResponseStatus.UNPLANNED.value.upper(),
                                        IPLanResponseStatus.TENTATIVE.value.upper()]:
            return order_line.confirmed_date
        return order_line.confirmed_date or order_line.iplan.iplant_confirm_date or ""

    @staticmethod
    def resolve_internal_comments_to_warehouse(root, info):
        return root.get("internal_comments_to_warehouse", "")

    @staticmethod
    def resolve_external_comments_to_customer(root, info):
        sap_order_response = info.variable_values.get("sap_order_response")
        if not sap_order_response:
            return root.external_comments_to_customer

        data = sap_order_response.get("data", [])
        result = []
        order_text_list = next((x.get("orderText") for x in data), [])

        for order_text in order_text_list:
            if order_text.get("ItemNo") == root.get("itemNo").zfill(6) and order_text.get("textId") == "Z002":
                text_line_list = order_text.get("textLine", "")
                for text_line in text_line_list:
                    result.append(text_line["text"])
        return '\n'.join(result)

    @staticmethod
    def resolve_internal_comments_to_logistic(root, info):
        return root.get("internal_comments_to_logistic", "")

    @staticmethod
    def resolve_product__information(root, info):
        return root.get("product__information", "")

    @staticmethod
    def resolve_payment_term_desc_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.get("paymentTerm"), root.get("paymentTerm"))

    @staticmethod
    def resolve_ship_to(root, info):
        return root.get("shipTo", "")

    @staticmethod
    def resolve_ref_pi_stock(root, info):
        order_line = root.get("order_line_instance")
        if not order_line or not order_line.ref_pi_no:
            return ""
        return order_line.ref_pi_no or ""

    @staticmethod
    def resolve_condition_group_1(root, info):
        order_line = root.get("order_line_instance")
        return getattr(order_line, "condition_group1", "") or getattr(getattr(order_line, "contract_material"),
                                                                      "condition_group1", "") or ""

    @staticmethod
    def resolve_inquiry_method(root, info):
        order_line = root.get("order_line_instance")
        return getattr(order_line, "inquiry_method", "") or ""

    @staticmethod
    def resolve_item_production_state(root, info):
        order_line = root.get("order_line_instance")
        return get_item_production_status(order_line)

    @staticmethod
    def resolve_is_material_outsource(root, info):
        order_line = root.get("order_line_instance")
        os_plant_list = MaterialType.MATERIAL_OS_PLANT.value
        material_plant = order_line.contract_material and order_line.contract_material.plant or ""
        return material_plant in os_plant_list or root.get("plant", "") in os_plant_list

    @staticmethod
    def resolve_remaining_quantity(root, info):
        material_code = root.get('material')
        contract_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')
        contract_mat = sap_migration.models.ContractMaterial.objects.filter(
            contract_no=contract_no,
            material_code=material_code,
        ).first()
        return contract_mat and contract_mat.remaining_quantity or 0

    @staticmethod
    def resolve_net_price(root, info):
        return root.get("netPrice", 0)

    @staticmethod
    def resolve_allow_change_inquiry_method(root, info):
        return resolve_allow_change_inquiry_method(root.get("order_line_instance"))

    @staticmethod
    def resolve_request_date_change_reason(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.request_date_change_reason or ""

    @staticmethod
    def resolve_remaining_quantity_ex(root, info):
        material_code = root.get('material')
        contract_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')
        contract_mat = sap_migration.models.ContractMaterial.objects.filter(
            contract_no=contract_no,
            material_code=material_code,
        ).first()
        return contract_mat and contract_mat.remaining_quantity_ex or 0

    @staticmethod
    def resolve_weight_display(root, info):
        return deepgetattr(root.get('order_line_instance', {}), 'weight_display', "TON")

    @staticmethod
    def resolve_po_subcontract(root, info):
        return root.get('poSubcontract', "")

    @staticmethod
    def resolve_po_status(root, info):
        po_status = root.get('poStatus', "")
        if po_status == "N":
            return POStatusEnum.N.value
        if po_status == "P":
            return POStatusEnum.P.value
        return ""

    @staticmethod
    def resolve_pr_no(root, info):
        return root.get('purchaseNo', "")

    @staticmethod
    def resolve_pr_item(root, info):
        return root.get('prItem', "")

    def resolve_original_request_date(root, info):
        order_line = root.get("order_line_instance")
        return (order_line and order_line.original_request_date or order_line.request_date).strftime("%d/%m/%Y")

    @staticmethod
    def resolve_weight_unit(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.weight_unit

    @staticmethod
    def resolve_gross_weight_ton(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.gross_weight_ton

    @staticmethod
    def resolve_net_weight_ton(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.net_weight_ton

    @staticmethod
    def resolve_weight_unit_ton(root, info):
        order_line = root.get("order_line_instance")
        return order_line and order_line.weight_unit_ton


class OrderCondition(graphene.ObjectType):
    item_no = graphene.String()
    condition_type = graphene.String()
    condition_rate = graphene.String()
    currency = graphene.String()
    condition_unit = graphene.String()
    condition_price_unit = graphene.String()
    condition_price_order = graphene.String()
    condition_base_value = graphene.String()

    @staticmethod
    def resolve_item_no(root, info):
        return root.get('itemNo', "").lstrip("0")

    @staticmethod
    def resolve_condition_type(root, info):
        return root.get('conditionType')

    @staticmethod
    def resolve_condition_rate(root, info):
        return root.get('conditionRate')

    @staticmethod
    def resolve_currency(root, info):
        return root.get('currency')

    @staticmethod
    def resolve_condition_unit(root, info):
        return root.get('conditionUnit')

    @staticmethod
    def resolve_condition_price_unit(root, info):
        return root.get('conditionPriceUnit')

    @staticmethod
    def resolve_condition_price_order(root, info):
        return root.get('conditionPriceOrder')

    @staticmethod
    def resolve_condition_base_value(root, info):
        return root.get('conditionBaseValue')


class TextLine(graphene.ObjectType):
    text = graphene.String()

    @staticmethod
    def resolve_invoice_no(root, info):
        return root.get('text')


class OrderText(graphene.ObjectType):
    item_no = graphene.String()
    text_id = graphene.String()
    language = graphene.String()
    text_line = graphene.List(TextLine)

    @staticmethod
    def resolve_item_no(root, info):
        return root.get('ItemNo')

    @staticmethod
    def resolve_text_id(root, info):
        return root.get('textId')

    @staticmethod
    def resolve_language(root, info):
        return root.get('language')

    @staticmethod
    def resolve_text_line(root, info):
        return root.get('textLine')


class ChangeOrder(graphene.ObjectType):
    so_no = graphene.String()
    contract_no = graphene.String()
    po_no = graphene.String()
    distribution_channel = graphene.String()
    distribution_channel_name = graphene.String()
    sales_org = graphene.String()
    sales_org_name = graphene.String()
    sales_org_short_name = graphene.String()
    sales_off = graphene.String()
    sales_off_name = graphene.String()
    division = graphene.String()
    division_name = graphene.String()
    price_date = graphene.String()
    status = graphene.String()
    order_amt_before_vat = graphene.String()
    order_amt_vat = graphene.String()
    order_amt_after_vat = graphene.String()
    currency = graphene.String()
    customer_group = graphene.String()
    customer_group_name = graphene.String()
    customer_group_1 = graphene.String()
    customer_group_1_name = graphene.String()
    customer_group_2 = graphene.String()
    customer_group_2_name = graphene.String()
    customer_group_3 = graphene.String()
    customer_group_3_name = graphene.String()
    customer_group_4 = graphene.String()
    customer_group_4_name = graphene.String()
    request_date = graphene.String()
    payment_terms = graphene.String()
    incoterms_1 = graphene.String()
    incoterms_1_name = graphene.String()
    incoterms_2 = graphene.String()
    incoterms_2_name = graphene.String()
    order_date = graphene.String()
    sales_group = graphene.String()
    sales_group_name = graphene.String()
    under_tol = graphene.String()
    over_tol = graphene.String()
    assigned_qty = graphene.String()
    delivery_block = graphene.String()
    dp = graphene.List(DPNo)
    invoice = graphene.List(InvoiceNo)
    order_partners = graphene.List(OrderPartners)
    order_items = graphene.List(OrderItems)
    order_condition = graphene.List(OrderCondition)
    order_text = graphene.List(OrderText)
    item_no_latest = graphene.String()
    po_date = graphene.String()
    order_type = graphene.String()
    order_type_desc = graphene.String()

    @staticmethod
    def resolve_order_type(root, info):
        order_type = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'docType')
        return order_type

    @staticmethod
    def resolve_order_type_desc(root, info):
        order_type = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'docType')
        if order_type:
            return get_order_type_desc(order_type)
        return ""

    @staticmethod
    def resolve_delivery_block(root, info):
        test = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'deliveryBlock')
        return test

    @staticmethod
    def resolve_so_no(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'saleDocument')

    @staticmethod
    def resolve_contract_no(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')

    @staticmethod
    def resolve_po_no(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'poNo')

    @staticmethod
    def resolve_distribution_channel(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'distributionChannel')

    @staticmethod
    def resolve_distribution_channel_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'distributionChannel')
        distribution_channel = master_models.DistributionChannelMaster.objects.filter(code=code).first()
        return distribution_channel.name if distribution_channel else ""

    @staticmethod
    def resolve_sales_org(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOrg')

    @staticmethod
    def resolve_sales_org_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOrg')
        sales_org = master_models.SalesOrganizationMaster.objects.filter(code=code).first()
        return sales_org.name if sales_org else ""

    @staticmethod
    def resolve_sales_org_short_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOrg')
        sales_org = master_models.SalesOrganizationMaster.objects.filter(code=code).first()
        return sales_org.short_name if sales_org else ""

    @staticmethod
    def resolve_sales_off(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOff')

    @staticmethod
    def resolve_sales_off_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOff')
        sales_off = migration_models.SalesOfficeMaster.objects.filter(code=code).first()
        return sales_off.name if sales_off else ""

    @staticmethod
    def resolve_division(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'division')

    @staticmethod
    def resolve_division_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'division')
        division = master_models.DivisionMaster.objects.filter(code=code).first()
        return division.name if division else ""

    @staticmethod
    def resolve_price_date(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'priceDate')

    @staticmethod
    def resolve_status(root, info):
        so_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'saleDocument')
        order = migration_models.Order.objects.filter(so_no=so_no).first()
        return order.status if order else ""

    @staticmethod
    def resolve_order_amt_before_vat(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtBeforeVat')

    @staticmethod
    def resolve_order_amt_vat(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtVat')

    @staticmethod
    def resolve_order_amt_after_vat(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtAfterVat')

    @staticmethod
    def resolve_currency(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'currency')

    @staticmethod
    def resolve_customer_group(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup')

    @staticmethod
    def resolve_customer_group_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup')
        customer_group = master_models.CustomerGroupMaster.objects.filter(code=code).first()
        return customer_group.name if customer_group else ""

    @staticmethod
    def resolve_customer_group_1(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup1')

    @staticmethod
    def resolve_customer_group_1_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup1')
        customer_group = master_models.CustomerGroup1Master.objects.filter(code=code).first()
        return customer_group.name if customer_group else ""

    @staticmethod
    def resolve_customer_group_2(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup2')

    @staticmethod
    def resolve_customer_group_2_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup2')
        customer_group = master_models.CustomerGroup2Master.objects.filter(code=code).first()
        return customer_group.name if customer_group else ""

    @staticmethod
    def resolve_customer_group_3(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup3')

    @staticmethod
    def resolve_customer_group_3_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup3')
        customer_group = master_models.CustomerGroup3Master.objects.filter(code=code).first()
        return customer_group.name if customer_group else ""

    @staticmethod
    def resolve_customer_group_4(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup4')

    @staticmethod
    def resolve_customer_group_4_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'customerGroup4')
        customer_group = master_models.CustomerGroup4Master.objects.filter(code=code).first()
        return customer_group.name if customer_group else ""

    @staticmethod
    def resolve_request_date(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'reqDate')

    @staticmethod
    def resolve_payment_terms(root, info):
        payment_terms = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'paymentTerms')
        return PAYMENT_TERM_MAPPING.get(payment_terms, payment_terms)

    @staticmethod
    def resolve_incoterms_1(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms1')

    @staticmethod
    def resolve_incoterms_1_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms1')
        incoterms_1 = master_models.Incoterms1Master.objects.filter(code=code).first()
        return incoterms_1.description if incoterms_1 else ""

    @staticmethod
    def resolve_incoterms_2(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms2')

    @staticmethod
    def resolve_order_date(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'createDate')

    @staticmethod
    def resolve_sales_group(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesGroup')

    @staticmethod
    def resolve_sales_group_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesGroup')
        sales_group = master_models.SalesGroup.objects.filter(sales_group_code=code).first()
        return sales_group.sales_group_description if sales_group else ""

    @staticmethod
    def resolve_under_tol(root, info):
        contract_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')
        contract_material = sap_migration.models.ContractMaterial.objects.filter(contract_no=contract_no).first()
        return contract_material.delivery_under if contract_material else 0

    @staticmethod
    def resolve_over_tol(root, info):
        contract_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')
        contract_material = sap_migration.models.ContractMaterial.objects.filter(contract_no=contract_no).first()
        return contract_material.delivery_over if contract_material else 0

    @staticmethod
    def resolve_assigned_qty(root, info):
        order_line = sap_migration.models.OrderLines.objects.filter(
            order__so_no=info.variable_values.get('soNo')).first()
        if not order_line:
            return 0
        return order_line.assigned_quantity if order_line.assigned_quantity else 0

    @staticmethod
    def resolve_order_partners(root, info):
        return from_api_response_es26_to_change_order(info, 'orderPartners')

    @staticmethod
    def resolve_order_items(root, info):
        return from_api_response_es26_to_change_order(info, 'orderItems')

    @staticmethod
    def resolve_order_condition(root, info):
        return from_api_response_es26_to_change_order(info, 'orderCondition')

    @staticmethod
    def resolve_order_text(root, info):
        return from_api_response_es26_to_change_order(info, 'orderText')

    @staticmethod
    def resolve_item_no_latest(root, info, **kwargs):
        order = sap_migration.models.Order.objects.filter(so_no=info.variable_values.get('soNo')).first()
        return getattr(order, "item_no_latest", 0)

    @staticmethod
    def resolve_dp(root, info):
        return from_api_response_es26_to_change_order(info, 'dp')

    @staticmethod
    def resolve_invoice(root, info):
        return from_api_response_es26_to_change_order(info, 'billing')

    @staticmethod
    def resolve_po_date(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'poDates')


class SAPOrderConfirmationLineGroup(graphene.ObjectType):
    sale_org = graphene.String()
    sold_to_code = graphene.String()
    sold_to_name = graphene.String()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    order_qty = graphene.String()
    confirm_quantity = graphene.String()
    non_confirm_quantity = graphene.String()
    sale_unit = graphene.String()
    request_date = graphene.String()
    confirm_date = graphene.String()
    status = graphene.String()
    remark_order = graphene.String()


class SAPOrderConfirmation(graphene.ObjectType):
    so_no = graphene.String()
    po_no = graphene.String()
    order_date = graphene.String()
    contract_no = graphene.String()
    contract_name = graphene.String()
    sales_org_name = graphene.String()
    sold_to_name = graphene.String()
    payment_method_name = graphene.String()
    ship_to_code = graphene.String()
    is_not_ref = graphene.Boolean()
    order_lines = graphene.List(
        SAPOrderConfirmationLineGroup
    )


class SAPOrderConfirmationDateInput(graphene.InputObjectType):
    gte = graphene.Date()
    lte = graphene.Date()


class SAPOrderConfirmationInput(graphene.InputObjectType):
    sold_to = graphene.List(graphene.String)
    sale_org = graphene.List(graphene.String, required=True)
    channel = graphene.String(required=True)
    product_group = graphene.String()
    create_date = graphene.Field(SAPOrderConfirmationDateInput)
    material_no_material_description = graphene.List(graphene.String)
    po_no = graphene.String()
    so_no = graphene.String()
    status = InquiryOrderConfirmationStatus()
    bu = graphene.String()
    source_of_app = graphene.String()


class OrderConfirmationLineInput(graphene.InputObjectType):
    item_no = graphene.String()
    remark = graphene.String()
    material_description = graphene.String()
    order_qty = graphene.Float()
    confirm_quantity = graphene.Float()
    non_confirm_quantity = graphene.Float()
    sale_unit = graphene.String()
    request_date = graphene.String()
    confirm_date = graphene.String()
    status = graphene.String()


class PrintOrderConfirmationInput(graphene.InputObjectType):
    sales_org_name = graphene.String()
    so_no = graphene.String()
    po_no = graphene.String()
    order_date = graphene.String()
    surname = graphene.String()
    sold_to_name = graphene.String()
    sold_to_address = graphene.String()
    payment_method_name = graphene.String()
    ship_to_name = graphene.String()
    ship_to_address = graphene.String()
    contract_no = graphene.String()
    contract_name = graphene.String()
    order_lines = graphene.List(
        OrderConfirmationLineInput
    )


class CustomerBlockResponse(graphene.ObjectType):
    customer_block = graphene.Boolean()

    class Meta:
        description = "Customer Block"


class CustomerBlockInput(graphene.InputObjectType):
    sold_to_code = graphene.String()
    contract_no = graphene.String()


class ContractOrderLineSplitInput(InputObjectType):
    id = graphene.ID(required=True)
    quantity = graphene.Int()
    request_date = graphene.Date()


class ChangeOrderHeaderPartnerInput(InputObjectType):
    ship_to = graphene.String()
    bill_to = graphene.String()
    customer_group_1 = graphene.ID()
    customer_group_2 = graphene.ID()
    customer_group_3 = graphene.ID()
    customer_group_4 = graphene.ID()
    po_date = graphene.String(description="dd/mm/YYYY")
    po_no = graphene.String()
    incoterms1 = graphene.ID()


class ChangeOrderHeaderAdditionalDataInput(InputObjectType):
    internal_comments_to_warehouse = graphene.String()
    internal_comments_to_logistic = graphene.String()
    external_comments_to_customer = graphene.String()
    production_information = graphene.String()


class ChangeOrderHeaderFixedDataInput(InputObjectType):
    so_no = graphene.String()
    po_no = graphene.String()
    contract_no = graphene.String()
    ship_to_code = graphene.String()
    sold_to_code = graphene.String()
    bill_to_code = graphene.String()


class ChangeOrderHeaderInput(InputObjectType):
    fixed_data = graphene.Field(ChangeOrderHeaderFixedDataInput)
    partner = graphene.Field(ChangeOrderHeaderPartnerInput)
    additional_data = graphene.Field(ChangeOrderHeaderAdditionalDataInput)


class DeliveryTolerance(InputObjectType):
    under = graphene.Int()
    over = graphene.Int()
    unlimited = graphene.Field(DeliveryUnlimited)


class ChangeOrderItemDetailsOrderInformationInput(InputObjectType):
    material_code = graphene.String()
    request_date = graphene.String(description="input format DD/MM/YYYY")
    reason_for_change_request_date = graphene.Field(ReasonForChangeRequestDateEnum)
    quantity = graphene.Float()
    unit = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.Field(WeightUnitEnum)
    plant = graphene.String()
    item_category = graphene.String()
    shipping_point = graphene.String()
    route = graphene.String(description="Input code")
    po_no = graphene.String()
    delivery_tolerance = graphene.Field(DeliveryTolerance)


class ChangeOrderItemDetailsIplanDetailsInput(InputObjectType):
    input_parameter = graphene.Field(InquiryMethodType)
    consignment_location = graphene.String()


class ChangeOrderItemDetailsAdditionalDataInput(InputObjectType):
    ship_to_party = graphene.String(description="Input code")
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    shipping_mark = graphene.String()


class ChangeOrderItemDetailsInput(InputObjectType):
    item_no = graphene.String()
    order_information = graphene.Field(ChangeOrderItemDetailsOrderInformationInput)
    iplan_details = graphene.Field(ChangeOrderItemDetailsIplanDetailsInput)
    additional_data = graphene.Field(ChangeOrderItemDetailsAdditionalDataInput)
    new = graphene.Boolean(description="Check if the order line is newly created", default=False)
    cancel_item = graphene.Field(CancelItem)
    split_from = graphene.String(description="input item_no of order line original")


class ChangeOrderEditInput(InputObjectType):
    header = graphene.Field(ChangeOrderHeaderInput)
    item_details = graphene.List(ChangeOrderItemDetailsInput)
    status = graphene.Field(ScgOrderStatus, description="", required=False)


class SapOrderMessage(graphene.ObjectType):
    error_code = graphene.String()
    so_no = graphene.String()
    error_message = graphene.String()


class SapItemMessage(graphene.ObjectType):
    error_code = graphene.String()
    item_no = graphene.String()
    error_message = graphene.String()


class IPlanMessage(graphene.ObjectType):
    item_no = graphene.String()
    first_code = graphene.String()
    second_code = graphene.String()
    message = graphene.String()
    so_no = graphene.String()


class WarningMessage(graphene.ObjectType):
    source = graphene.String()
    order = graphene.String()
    message = graphene.String()


class OrderInformationInput(InputObjectType):
    customer_id = graphene.ID(required=False)
    po_date = graphene.Date(required=False, description="date must be type yyyy-mm-dd")
    po_number = graphene.String(required=False)
    request_date = graphene.Date(
        required=False, description="date must be type yyyy-mm-dd"
    )
    contract_id = graphene.ID(required=False)
    order_type = graphene.String(required=False)
    ship_to = graphene.String(required=False)
    bill_to = graphene.String(required=False)
    customer_group_1_id = graphene.ID(require=False)
    customer_group_2_id = graphene.ID(require=False)
    customer_group_3_id = graphene.ID(require=False)
    customer_group_4_id = graphene.ID(require=False)
    internal_comments_to_warehouse = graphene.String(required=False)
    internal_comments_to_logistic = graphene.String(required=False)
    external_comments_to_customer = graphene.String(required=False)
    product_information = graphene.String(required=False)
    shipping_point = graphene.String(required=False)
    route = graphene.String(required=False)
    delivery_block = graphene.String(require=False)
    incoterms_id = graphene.ID(required=False)


class ContractOrderUpdateStatusInput(InputObjectType):
    id = graphene.ID(required=True, description="id of order")


class UpdateAtpCtpContractOrderLineInput(InputObjectType):
    id = graphene.Int(required=True)
    quantity = graphene.Float()
    confirmed_date = graphene.Date()
    plant = graphene.String()
    atp_ctp_status = graphene.Argument(ScgOrderlineAtpCtpStatus)
    # atp/ctp mock data input
    atp_ctp = graphene.String()
    atp_ctp_detail = graphene.String()
    block = graphene.String()
    run = graphene.String()


class SAPPendingOrderReportDateInput(graphene.InputObjectType):
    gte = graphene.Date()
    lte = graphene.Date()


class CancelDeleteOrderLinesInput(InputObjectType):
    item_no = graphene.String(required=True)
    status = graphene.String()


class SoldToSortInput(InputObjectType):
    sold_to = graphene.String()
    sort_field = graphene.String()
    sort_type = graphene.String()


class SAPPendingOrderReportInput(graphene.InputObjectType):
    sold_to = graphene.List(graphene.String, required=True)
    sale_org = graphene.List(graphene.String, required=True)
    ship_to = graphene.String()
    material_no_material_description = graphene.List(graphene.String)
    product_group = graphene.String()
    create_date = graphene.Field(SAPPendingOrderReportDateInput)
    request_delivery_date = graphene.Field(SAPPendingOrderReportDateInput)
    po_no = graphene.String()
    so_no = graphene.String()
    transactions = graphene.List(graphene.String)
    product_groups = graphene.String()
    report_format = graphene.String()
    sold_to_sort = graphene.List(SoldToSortInput)
    bu = graphene.String()
    is_order_tracking = graphene.Boolean()
    source_of_app = graphene.String()


class OrderOrganizationalDataInput(InputObjectType):
    sale_organization_id = graphene.ID(required=False)
    distribution_channel_id = graphene.ID(required=False)
    division_id = graphene.ID(required=False)
    sale_office_id = graphene.ID(required=False)
    sale_group_id = graphene.ID(required=False)


class ContractOrderLineInput(InputObjectType):
    checkout_line_id = graphene.ID()
    quantity = graphene.Float()
    request_date = graphene.Date(description="date must be type yyyy-mm-dd")
    plant = graphene.String()
    ship_to = graphene.String()
    internal_comments_to_warehouse = graphene.String(required=False)
    shipping_mark = graphene.String(required=False)
    material_no = graphene.String(required=False)
    unit = graphene.String(required=False)
    product_information = graphene.String()
    variant_id = graphene.ID()
    over_delivery_tol = graphene.Float()
    under_delivery_tol = graphene.Float()
    weight_unit = graphene.String()
    split_items = graphene.List(ContractOrderLineSplitInput, required=False)
    external_comments_to_customer = graphene.String()
    internal_comments_to_logistic = graphene.String()
    item_category = graphene.String()
    shipping_point = graphene.String()
    route = graphene.String()
    po_no = graphene.String()
    po_no_external = graphene.String()
    delivery_tol_unlimited = graphene.Boolean()
    payment_term = graphene.String()
    weight = graphene.Float()
    request_date_change_reason = graphene.String()


class ContractOrderLineUpdateInput(ContractOrderLineInput):
    id = graphene.ID(required=True, description="id of order line")
    item_no = graphene.String()


class ContractOrderUpdateInput(InputObjectType):
    order_information = graphene.Field(OrderInformationInput)
    order_organization_data = graphene.Field(
        OrderOrganizationalDataInput,
        description=("information about order organization data"),
        required=False,
    )
    lines = NonNullList(
        ContractOrderLineUpdateInput,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ),
        required=True,
    )
    status = graphene.Field(ScgOrderStatus, description="", required=False)


class DomesticOrderLineAddProductInput(InputObjectType):
    contract_material_id = graphene.ID(required=True)
    material_variant_id = graphene.ID(required=False)
    quantity = graphene.Float(required=True)


class ContractOrderLinesUpdateInput(InputObjectType):
    request_date = graphene.Date(description="date must be type yyyy-mm-dd")
    ship_to = graphene.String()
    bill_to = graphene.String()
    external_comments_to_customer = graphene.String()
    product_information = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    material_no = graphene.String(required=False)
    unit = graphene.String(required=False)
    internal_comments_to_logistic = graphene.String()
    shipping_point = graphene.String()
    route = graphene.String()


class ContractOrderCreateInput(InputObjectType):
    order_information = graphene.Field(OrderInformationInput)
    lines = NonNullList(
        ContractOrderLineInput,
        description=(
            "A list of order lines, each containing information about "
            "an item in the order."
        ),
        required=True,
    )


class ChangeOrderAddNewItemItemDetails(InputObjectType):
    item_no = graphene.String(required=True)
    order_information = graphene.Field(ChangeOrderItemDetailsOrderInformationInput)
    additional_data = graphene.Field(ChangeOrderItemDetailsAdditionalDataInput)
    ref_doc_it = graphene.String()


class ChangeOrderAddNewOrderLineInput(InputObjectType):
    order_headers = graphene.Field(ChangeOrderHeaderFixedDataInput)
    list_new_items = graphene.List(ChangeOrderAddNewItemItemDetails)


class ItemLevelErrorResponse(ObjectType):
    item_no = graphene.String()
    error_code = graphene.String()
    error_message = graphene.String()


class HeaderLevelErrorResponse(ObjectType):
    source_of_system = graphene.String()
    error_code = graphene.String()
    error_description = graphene.String()


class ErrorChangeOrder(ObjectType):
    header_level = graphene.Field(HeaderLevelErrorResponse)
    item_level = graphene.List(ItemLevelErrorResponse)


class SendEmailOrderLineInput(InputObjectType):
    item_no = graphene.String()
    remark = graphene.String()
    material_description = graphene.String()
    order_qty = graphene.String()
    confirm_qty = graphene.String()
    non_confirm_qty = graphene.String()
    sale_unit = graphene.String()
    first_delivery_date = graphene.String()
    sold_to = graphene.String()
    status = graphene.String()
    iplan_confirm_date = graphene.String()
    material_code = graphene.String()


class SendEmailOrderInput(InputObjectType):
    so_no = graphene.String()
    contract_no = graphene.String()
    created_date = graphene.String()
    po_no = graphene.String()
    payment_term_desc = graphene.String()
    contract_name = graphene.String()
    item_no = graphene.List(graphene.String)
    order_lines = graphene.List(SendEmailOrderLineInput)
    ship_to = graphene.String()
    sale_org = graphene.String()
    is_not_ref = graphene.Boolean()


class GPSReportCSCustomer(ObjectType):
    truck_no = graphene.String()
    box_position = graphene.String()
    carrier_name = graphene.String()
    box_speed = graphene.String()
    box_gps_time = graphene.String()
    shipment = graphene.String()
    destination_name = graphene.String()
    status_id = graphene.String()
    destination_inbound = graphene.String()
    estimated_time = graphene.String()
    eta_distance = graphene.String()
    eta_duration = graphene.String()
    acc_distance = graphene.String()
    good_issue_time = graphene.String()
    plan_delivery = graphene.String()
    status_text = graphene.String()
    dn_no = graphene.String()

    @staticmethod
    def resolve_status_text(root, info):
        status_id = root.get('status_id', "")
        status_text = ""
        if status_id:
            status_text = LMSStatusText.get(status_id, "")
            return f'{LMSStatusIdMapping.get(status_id, "")}. {status_text}'
        return status_text


class LMSReportCSCustomer(ObjectType):
    dn_no = graphene.String()
    data_item = graphene.List(lambda: DataItems)
    sold_to_code = graphene.String()
    sold_to_name = graphene.String()
    destination_name = graphene.String()
    cut_off_date = graphene.String()
    cut_off_time = graphene.String()
    truck_no = graphene.String()
    origin_name = graphene.String()
    plan_delivery = graphene.String()
    status_id = graphene.String()
    status_text = graphene.String()
    box_position = graphene.String()
    eta_distance = graphene.String()
    estimated_time = graphene.String()
    carrier_name = graphene.String()
    box_speed = graphene.String()
    box_gps_time = graphene.String()
    shipment = graphene.String()
    acc_distance = graphene.String()
    good_issue_time = graphene.String()
    destination_inbound = graphene.String()
    eta = graphene.String()
    eta_duration = graphene.String()
    status = graphene.String()
    message = graphene.String()
    shipping_point = graphene.String()
    return_flag = graphene.String()
    phone_no = graphene.String()
    contract_id = graphene.String()
    contract_abbr = graphene.String()
    gi_time = graphene.String()
    summary_grand_total = graphene.Float()

    @staticmethod
    def resolve_data_item(root, info):
        data_items = root.get('data_item', [])
        status_id = root.get('status_id', "")
        gi_time = root.get('gi_time', "")
        cut_off_date = root.get('cut_off_date', "")
        for data_item in data_items:
            data_item["lms_status"] = status_id
            data_item["gi_time"] = gi_time
            data_item["cut_off_date"] = cut_off_date

        return data_items

    @staticmethod
    def resolve_status_text(root, info):
        status_id = root.get('status_id', "")
        status_text = ""
        if status_id:
            status_text = LMSStatusText.get(status_id, "")
        return status_text

    @staticmethod
    def resolve_sold_to_name(root, info):
        sold_to_code = root.get('sold_to_code', "")
        sold_to_partner_address = get_sold_to_partner(sold_to_code)
        if not sold_to_partner_address:
            return ""

        name_fields = ["name1", "name2", "name3", "name4"]
        sold_to_name = "".join(
            [getattr(sold_to_partner_address, field) for field in name_fields if
             getattr(sold_to_partner_address, field)]
        )
        return sold_to_name

    @staticmethod
    def resolve_summary_grand_total(root, info):
        data_items = root.get('data_item', [])
        summary_grand_total = sum([data_item.get('deliveryQty', 0) for data_item in data_items])

        return summary_grand_total

    @staticmethod
    def resolve_eta_distance(root, info):
        eta_distance = root.get('eta_distance', "")
        if str(eta_distance) == "0":
            eta_distance = finish_work
        return eta_distance

    @staticmethod
    def resolve_estimated_time(root, info):
        estimated_time = root.get('estimated_time', "")
        eta_distance = root.get('eta_distance', "")
        if str(eta_distance) == "0":
            estimated_time = finish_work
        return estimated_time

    @staticmethod
    def resolve_cut_off_date(root, info):
        cut_off_date = root.get('cut_off_date', "")
        if cut_off_date:
            cut_off_date = datetime.strptime(cut_off_date, "%Y-%m-%d").strftime(format_date_2)
        return cut_off_date

    @staticmethod
    def resolve_status_id(root, info):
        status_id = root.get('status_id', "")
        if status_id:
            return LMSStatusIdMapping.get(status_id, "")
        return status_id


class DataItems(ObjectType):
    po_no = graphene.String()
    so_no = graphene.String()
    item_no = graphene.String()
    material_description = graphene.String()
    delivery_qty = graphene.Float()
    sale_unit = graphene.String()
    lms_status = graphene.String()
    gi_time = graphene.String()
    mat_number = graphene.String()
    delivery_weight = graphene.String()
    weight_unit_ton = graphene.String()

    @staticmethod
    def resolve_po_no(root, info):
        return root.get('poNo', "")

    @staticmethod
    def resolve_so_no(root, info):
        return root.get('soNo', "")

    @staticmethod
    def resolve_item_no(root, info):
        return root.get('itemNo', "")

    @staticmethod
    def resolve_material_description(root, info):
        return root.get('matDes', "")

    @staticmethod
    def resolve_delivery_qty(root, info):
        return root.get('deliveryQty', 0)

    @staticmethod
    def resolve_sale_unit(root, info):
        return root.get('saleUnit', "")

    @staticmethod
    def resolve_lms_status(root, info):
        lms_status = root.get('lms_status', "")
        so_no = root.get('soNo', "")
        item_no = root.get('itemNo', "")
        gi_time = root.get('gi_time', "")
        cut_off_date = root.get('cut_off_date', "")
        if not lms_status:
            if cut_off_date:
                cut_off_date = datetime.strptime(cut_off_date, "%Y-%m-%d").strftime(format_date_2)
                status_text = f"ออกใบจ่ายสินค้า (GI) วันที่ {cut_off_date} {gi_time}"
                return status_text
            return "รอดำเนินการ GI สินค้า"
        status_text = LMSStatusText.get(lms_status, "")
        return f'{LMSStatusIdMapping.get(lms_status, "")}. {status_text}'

    @staticmethod
    def resolve_mat_number(root, info):
        return root.get('matNumber', '')

    @staticmethod
    def resolve_delivery_weight(root, info):
        return f'{root.get("netWeightTon", 0):.3f}'

    @staticmethod
    def resolve_weight_unit_ton(root, info):
        return root.get('weightUnitTon', "")


class LMSReportCSCustomerInput(graphene.InputObjectType):
    sold_to_code = graphene.String(required=True)
    mat_no = graphene.String()
    sale_org_code = graphene.String(required=True)
    so_no = graphene.String()
    po_no = graphene.String()
    shipping_point = graphene.String()
    delivery_date = graphene.Field(SAPPendingOrderReportDateInput, required=True)


class GPSReportCSCustomerInput(graphene.InputObjectType):
    dp = graphene.String(required=True)
    shipping_point = graphene.String(required=True)
    sold_to = graphene.String(required=True)


class PendingOrderReportShipTos(graphene.ObjectType):
    name = graphene.String()
    code = graphene.String()


class CustomerMaterialUploadInput(graphene.InputObjectType):
    sold_to_code = graphene.String(required=True)
    sale_org_code = graphene.String(required=True)
    distribution_channel = graphene.String(required=True)


class SaleOrgByDistChannelRes(graphene.ObjectType):
    sales_org = graphene.String()
    distribution_channel = graphene.List(DistributionChannel)


class DistChannelBySalesOrgRes(graphene.ObjectType):
    distribution_channel = graphene.String()
    sales_org = graphene.List(SalesOrganization)


class GetSaleOrgDistChannelBySoldToRes(graphene.ObjectType):
    sales_organization = graphene.List(SalesOrganization)
    distribution_channel = graphene.List(DistributionChannel)
    sales_org_by_dist_channel = graphene.List(SaleOrgByDistChannelRes)
    dist_channel_by_sales_org = graphene.List(DistChannelBySalesOrgRes)


class CustomerMaterialErrorData(graphene.ObjectType):
    sold_to_code = graphene.String()
    sales_organization_code = graphene.String()
    distribution_channel_code = graphene.String()
    sold_to_material_code = graphene.String()
    material_code = graphene.String()
