import graphene
from django.contrib.auth import get_user_model

from saleor.graphql.core.connection import CountableConnection, create_connection_slice
from saleor.graphql.core.fields import ConnectionField
from saleor.graphql.core.types import ModelObjectType, NonNullList
from saleor.graphql.meta.types import ObjectWithMetadata
from sap_migration.graphql.types import SoldToMaster, ScgCountableConnection
from scg_checkout.contract_order_update import get_tax_percent
from scg_checkout.graphql.enums import AlternatedMaterialLogChangeError
from scg_checkout.graphql.resolves.contracts import resolve_variants
from scg_checkout.graphql.resolves.orders import resolve_sold_to_address
from scg_checkout.graphql.resolves.product_variant import resolve_limit_quantity
from scg_checkout.graphql.helper import PAYMENT_TERM_MAPPING, get_mat_desc_from_master_for_alt_mat_old
from scg_customer.graphql.types import ScgUser
from scgp_customer.graphql.sorters import CustomerProductSortingInput, OrderLinesSortingInput
from scgp_customer.graphql.resolvers import customer_contract
from scgp_customer.graphql.resolvers.carts import (
    resolve_quantity,
    resolve_variant,
    resolve_contract_product_in_cart,
)
from scgp_customer.graphql.sorters import CustomerCartsSortingInput
from scgp_customer.graphql.resolvers.carts import (
    resolve_customer_product,
    resolve_cart_items,
)
from scgp_customer.graphql.resolvers.orders import (
    resolve_order_lines,
    resolve_available_quantity,
    resolve_fail_order_lines,
    resolve_material_description,
    resolve_confirmed_date,
    resolve_order_quantity_ton,
    resolve_material_variant_code,
    resolve_customer_sold_to_order,
    resolve_material_variant,
    resolve_description_en_preview_order,
    resolve_weight_per_unit,
    resolve_total_weight,
)
from sap_migration import models as sap_migration_models
from sap_migration.graphql import types as sap_migration_type
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from sap_master_data import models as sap_master_data_models
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text,resolve_sold_to_name
from scg_checkout.models import AlternatedMaterial
from sap_migration.models import MaterialVariantMaster


class ScgUserDetail(ScgUser):
    class Meta:
        description = "Represents user data."
        interfaces = [graphene.relay.Node, ObjectWithMetadata]
        model = get_user_model()

    @staticmethod
    def resolve_customer_no(root, info):
        customer_no = "{:07d}".format(root.id)
        return customer_no


class CustomerContract(ModelObjectType):
    id = graphene.ID()
    sold_to = graphene.Field(sap_migration_type.SoldToMaster)
    company = graphene.Field(sap_migration_type.CompanyMaster)
    customer = graphene.Field(ScgUserDetail)
    code = graphene.String()
    project_name = graphene.String()
    start_date = graphene.Date()
    end_date = graphene.Date()
    payment_term = graphene.String()
    products = graphene.List(lambda: CustomerContractProduct, sort_by=CustomerProductSortingInput())
    currency = graphene.String()
    payment_term_key = graphene.String()
    payment_term_description_th = graphene.String()

    class Meta:
        model = sap_migration_models.Contract

    @staticmethod
    def resolve_customer(root, info):
        if not info.context.user.id:
            raise ValueError("You have to login!")
        return info.context.user

    @staticmethod
    def resolve_products(root, info, sort_by=None):
        return customer_contract.resolve_products(root.id, sort_by, info=info)

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_key + " - " + root.payment_term

    @staticmethod
    def resolve_payment_term_description_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.payment_term_key)


class CustomerContractCountableConnection(CountableConnection):
    class Meta:
        node = CustomerContract


class CustomerProduct(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    slug = graphene.String()
    variants = graphene.List(lambda: CustomerProductVariant)
    description_en = graphene.String()
    material_type = graphene.String()
    sales_unit = graphene.String()

    class Meta:
        model = sap_migration_models.MaterialMaster

    @staticmethod
    def resolve_name(root, info):
        return root.name

    @staticmethod
    def resolve_variants(root, info):
        return resolve_variants(root, info)

    @staticmethod
    def resolve_slug(root, info):
        return root.material_code

    @staticmethod
    def resolve_sales_unit(root, info):
        if root.sales_unit is not None and root.sales_unit.lower() == "EA".lower():
            return root.sales_unit
        else:
            return "ROL"


class CustomerProductVariant(ModelObjectType):
    id = graphene.ID()
    product = graphene.Field(CustomerProduct)
    name = graphene.String()
    slug = graphene.String()
    code = graphene.String()
    description_th = graphene.String()
    variant_type = graphene.String()
    sales_unit = graphene.String()
    description_en = graphene.String()
    weight = graphene.Float()
    limit_quantity = graphene.Float()

    class Meta:
        model = sap_migration_models.MaterialVariantMaster

    @staticmethod
    def resolve_slug(root, info):
        return root.code

    @staticmethod
    def resolve_weight(root, info):
        calculation = getattr(root, "calculation", 0)
        if not calculation:
            conversion_master = sap_master_data_models.Conversion2Master.objects.filter(
                material_code=root.code, to_unit='ROL'
            ).distinct('material_code').order_by("material_code", "-id").values('calculation').first()

            calculation = conversion_master and conversion_master['calculation'] or 0

        return round(calculation / 1000, 3)

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = info.variable_values.get("contractId",
                                               info.variable_values.get("contract_id", "") or
                                               info.variable_values.get("cart_contract_id", ""))
        material_id = info.variable_values.get("productId", root.material.id)
        contract_material_id = info.variable_values.get("contract_material_id", "")
        return resolve_limit_quantity(contract_id=contract_id, material_id=material_id,
                                      variant_code=root.code, contract_mat_id=contract_material_id)


class CustomerContractProduct(ModelObjectType):
    id = graphene.ID()
    contract = graphene.Field(CustomerContract)
    product = graphene.Field(CustomerProduct)
    total_quantity = graphene.Float()
    remaining_quantity = graphene.Float(order_id=graphene.ID())
    price_per_unit = graphene.Float()
    quantity_unit = graphene.String()
    currency = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.String()
    limit_quantity = graphene.Float()
    material_description = graphene.String()

    class Meta:
        model = sap_migration_models.ContractMaterial

    @staticmethod
    def resolve_price_per_unit(root, info):
        return round(root.price_per_unit, 2)

    @staticmethod
    def resolve_weight(root, info):
        return round(root.weight, 3)

    @staticmethod
    def resolve_remaining_quantity(root, info, order_id=None):
        return root.remaining_quantity

    @staticmethod
    def resolve_product(root, info):
        info.variable_values.update({"cart_contract_id": root.contract.id})
        return root.material

    @staticmethod
    def resolve_quantity_unit(root, info):
        return root.weight_unit

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = root.contract.id
        material_id = root.material.id
        variant_code = root.material.material_code
        return resolve_limit_quantity(contract_id, material_id, variant_code, contract_mat_id=root.id)


class CurrencyMaster(ModelObjectType):
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_master_data_models.CurrencyMaster


class CustomerOrder(ModelObjectType):
    id = graphene.ID()
    contract = graphene.Field(CustomerContract)
    total_price = graphene.Float()
    total_price_inc_tax = graphene.Float()
    tax_amount = graphene.Float()
    tax_percent = graphene.Float()
    status = graphene.String()
    # Header
    order_date = graphene.Date()
    order_no = graphene.String()
    request_delivery_date = graphene.Date()
    ship_to = graphene.String()
    bill_to = graphene.String()
    unloading_point = graphene.String()
    remark_for_invoice = graphene.String()
    remark_for_logistic = graphene.String()
    created_by = graphene.Field(ScgUser)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    so_no = graphene.String()
    po_no = graphene.String()
    payment_term = graphene.String()
    sold_to = graphene.Field(SoldToMaster)
    lines = graphene.List(lambda: CustomerOrderLine)
    fail_order_lines = graphene.List(lambda: CustomerOrderLine)
    company = graphene.Field(lambda: CustomerCompany)
    credit_status = graphene.String()
    currency = graphene.Field(lambda: CurrencyMaster)
    customer_sold_to_order = graphene.String()
    sold_to_address = graphene.String()
    internal_comments_to_warehouse = graphene.String()
    internal_comments_to_logistic = graphene.String()
    payment_term_description_th = graphene.String()

    class Meta:
        model = sap_migration_models.Order

    @staticmethod
    def resolve_lines(root, info):
        return resolve_order_lines(root.id)

    @staticmethod
    def resolve_fail_order_lines(root, info):
        return resolve_fail_order_lines(root.id)

    @staticmethod
    def resolve_total_price(root, info):
        return round(root.total_price, 2)

    @staticmethod
    def resolve_total_price_inc_tax(root, info):
        return round(root.total_price_inc_tax, 2)

    @staticmethod
    def resolve_tax_amount(root, info):
        return round(root.tax_amount, 2)

    @staticmethod
    def resolve_request_delivery_date(root, info):
        return root.request_date

    @staticmethod
    def resolve_customer_sold_to_order(root, info):
        try:
            sold_to_name = resolve_sold_to_name(root.sold_to.sold_to_code)
            return f"{root.sold_to.sold_to_code} - {sold_to_name}"
        except Exception:
            return ""

    @staticmethod
    def resolve_sold_to_address(root, info):
        return resolve_sold_to_address(root, info)

    @staticmethod
    def resolve_tax_percent(root, info):
        return get_tax_percent(root.sold_to.sold_to_code)

    @staticmethod
    def resolve_payment_term_description_th(root, info):
        payment_term_key = (root.payment_term or "").split(" ")[0]
        return PAYMENT_TERM_MAPPING.get(payment_term_key) or ""


class CustomerOrderLine(ModelObjectType):
    id = graphene.ID()
    order = graphene.Field(CustomerOrder)
    contract_product = graphene.Field(CustomerContractProduct)
    variant = graphene.Field(CustomerProductVariant)
    quantity = graphene.Float()
    quantity_unit = graphene.String()
    weight_per_unit = graphene.Float()
    total_weight = graphene.Float()
    price_per_unit = graphene.Float()
    total_price = graphene.Float()
    request_delivery_date = graphene.Date()
    available_quantity = graphene.Float()
    cart_item = graphene.Field(lambda: CustomerCartItem)
    original_request_date = graphene.Date()
    confirmed_date = graphene.Date()
    request_date = graphene.Date()
    material_variant_code = graphene.String()
    material_description = graphene.String()
    item_no = graphene.String()
    sales_unit = graphene.String()
    order_quantity_ton = graphene.Float()
    item_status_en = graphene.String()
    item_status_th = graphene.String()
    assigned_quantity = graphene.Float()
    non_confirm_quantity = graphene.Float()
    confirm_quantity = graphene.Float()
    sap_confirm_status = graphene.String()
    payment_term = graphene.String()
    description_en = graphene.String()
    payment_term_description_th = graphene.String()

    class Meta:
        model = sap_migration_models.OrderLines

    @staticmethod
    def resolve_order_quantity_ton(root, info):
        return resolve_order_quantity_ton(root, info)

    @staticmethod
    def resolve_material_variant_code(root, info):
        return resolve_material_variant_code(root.material_variant_id)

    @staticmethod
    def resolve_material_description(root, info):
        return resolve_material_description(root.material_variant_id)

    @staticmethod
    def resolve_weight_per_unit(root, info):
        return resolve_weight_per_unit(root)

    @staticmethod
    def resolve_confirmed_date(root, info):
        return resolve_confirmed_date(root.id)

    @staticmethod
    def resolve_total_weight(root, info):
        return resolve_total_weight(root)

    @staticmethod
    def resolve_price_per_unit(root, info):
        return round(root.price_per_unit, 2)

    @staticmethod
    def resolve_total_price(root, info):
        return round(root.total_price, 2)

    @staticmethod
    def resolve_available_quantity(root, info):
        return resolve_available_quantity(root.order_id, root.contract_material_id)

    @staticmethod
    def resolve_contract_product(root, info):
        return root.contract_material

    @staticmethod
    def resolve_request_delivery_date(root, info):
        return root.request_date

    @staticmethod
    def resolve_sales_unit(root, info):
        # return root.contract_material.weight_unit
        return root.sales_unit

    @staticmethod
    def resolve_variant(root, info):
        return resolve_material_variant(root, info)

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_item

    @staticmethod
    def resolve_description_en(root, info):
        return resolve_description_en_preview_order(root.material_variant.code)

    def resolve_payment_term_description_th(root, info):
        return PAYMENT_TERM_MAPPING.get(root.payment_term_item)

    @staticmethod
    def resolve_original_request_date(root, info):
        return root.original_request_date


class PreviewCustomerTempOrderLine(CustomerOrderLine):
    log_errors = graphene.String()
    log_old_product = graphene.String()

    class Meta:
        model = sap_migration_models.OrderLines

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


class CustomerOrderLineCountableConnection(CountableConnection):
    class Meta:
        node = CustomerOrderLine


class CustomerOrderExtended(CustomerOrder):
    lines = graphene.ConnectionField(CustomerOrderLineCountableConnection)

    class Meta:
        model = sap_migration_models.Order

    @staticmethod
    def resolve_lines(root, info, **kwargs):
        info.variable_values.update({"contract_id": root.contract.id})
        qs = resolve_order_lines(root.id)
        return create_connection_slice(qs, info, kwargs, CustomerOrderLineCountableConnection)


class CustomerCartItem(ModelObjectType):
    id = graphene.ID(description="ID of cart item")
    cart = graphene.Field(lambda: CustomerCart)
    contract_product = graphene.Field(CustomerContractProduct)
    variant = graphene.Field(CustomerProductVariant)
    quantity = graphene.Float()
    customer_product = graphene.Field(CustomerProduct)
    customer_product_variant = graphene.Field(CustomerProductVariant)
    contract_product_id = graphene.ID(description="ID of Contract product id")

    class Meta:
        model = sap_migration_models.CartLines

    @staticmethod
    def resolve_product(root, info):
        return resolve_customer_product(root.product_id)

    @staticmethod
    def resolve_contract_product(root, info):
        return resolve_contract_product_in_cart(root)

    @staticmethod
    def resolve_variant(root, info):
        if root.contract_material_id:
            info.variable_values.update({"contract_material_id": root.contract_material_id})
        return resolve_variant(root)

    @staticmethod
    def resolve_contract_product_id(root, info):
        return root.contract_material_id


class CustomerCartLines(ModelObjectType):
    id = graphene.ID(description="ID of cart"),
    cart_items = NonNullList(CustomerCartItem, sort_by=CustomerCartsSortingInput())

    class Meta:
        model = sap_migration_models.Cart


class CustomerCart(ModelObjectType):
    id = graphene.ID(description="ID of cart")
    contract = graphene.Field(CustomerContract)
    created_by = graphene.Field(ScgUser)
    quantity = graphene.Float()
    cart_items = NonNullList(CustomerCartItem, sort_by=CustomerCartsSortingInput())

    class Meta:
        model = sap_migration_models.Cart

    @staticmethod
    def resolve_quantity(root, info):
        return resolve_quantity(root.id)

    @staticmethod
    def resolve_cart_items(root, info, sort_by=None):
        info.variable_values.update({"contract_id": root.contract.id})
        return resolve_cart_items(root.id, sort_by)


class CustomerCartProductVariant(ModelObjectType):
    contract_product = graphene.List(CustomerContractProduct)

    class Meta:
        model = sap_migration_models.Cart

    @staticmethod
    def resolve_contract_product(root, info):
        return sap_migration_models.ContractMaterial.objects.filter(contract_id=root.contract_id)


class CustomerCartCountableConnection(CountableConnection):
    class Meta:
        node = CustomerCart


class CustomerCartTotals(graphene.ObjectType):
    total_contracts = graphene.Int()
    total_products = graphene.Int()

    class Meta:
        description = "Customer Cart Totals"


# class CustomerCartTotals(ModelObjectType):
#     total_contracts = graphene.Int()
#     total_products = graphene.Int()
#
#     class Meta:
#         model = sap_migration_models.Cart
#
#     @staticmethod
#     def resolve_total_contracts(root, info):
#         sold_to_id = root.get("total_contracts")
#         return resolve_total_contracts(info.context.user, sold_to_id)
#
#     @staticmethod
#     def resolve_total_products(root, info):
#         sold_to_id = root.get("total_products")
#         return resolve_total_products(info.context.user, sold_to_id)


class OrderLinesCountableConnection(ScgCountableConnection):
    class Meta:
        node = PreviewCustomerTempOrderLine


class PreviewOrderLines(CustomerOrder):
    class Meta:
        model = sap_migration_models.Order

    preview_order_lines = ConnectionField(lambda: OrderLinesCountableConnection, sort_by=OrderLinesSortingInput())

    @staticmethod
    def resolve_preview_order_lines(root, info, **kwargs):
        qs = resolve_order_lines(root.id)
        return resolve_connection_slice(qs, info, kwargs, OrderLinesCountableConnection)


class CustomerMaterialCodeNameCountTableConnection(CountableConnection):
    class Meta:
        node = CustomerProductVariant


class CustomerOrderCountTableConnection(ScgCountableConnection):
    class Meta:
        node = CustomerOrder


class CustomerBusinessUnit(ModelObjectType):
    id = graphene.ID(description="ID of business_unit")
    name = graphene.String(description="name of business_unit")
    code = graphene.String(description="code of business_unit")
    is_default_for_inquiry_search = graphene.Boolean(default_value=False)

    class Meta:
        model = sap_migration_models.BusinessUnits


class CustomerCompany(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()
    business_unit = graphene.Field(CustomerBusinessUnit)
    short_name = graphene.String()

    class Meta:
        model = sap_migration_models.CompanyMaster


class CustomerSalesOrganization(ModelObjectType):
    id = graphene.ID(description="ID of sales_organization")
    name = graphene.String(description="name of sales_organization")
    code = graphene.String(description="code of sales_organization")
    business_unit = graphene.Field(CustomerBusinessUnit)

    class Meta:
        model = sap_migration_models.SalesOrganizationMaster


class CustomerSalesGroup(ModelObjectType):
    id = graphene.ID(description="ID of sales_group")
    name = graphene.String(description="name of sales_group")
    code = graphene.String(description="code of sales_group")
    sales_organization = graphene.Field(CustomerSalesOrganization)
    company = graphene.Field(CustomerCompany)

    class Meta:
        model = sap_migration_models.SalesGroupMaster


class CustomerCompanyCountTableConnection(ScgCountableConnection):
    class Meta:
        node = CustomerCompany


class CustomerSalesGroupCountTableConnection(CountableConnection):
    class Meta:
        node = CustomerSalesGroup


class SAPOrderMapping(graphene.ObjectType):
    id = graphene.Int()
    sd_doc = graphene.String()
    status = graphene.String()
    create_date = graphene.String()
    create_time = graphene.String()
    po_no = graphene.String()
    sales_org = graphene.String()
    description_in_contract = graphene.String()
    credit_status = graphene.String()
    deliver_status = graphene.String()
    sold_to = graphene.String()
    sold_to_name_1 = graphene.String()
    ship_to = graphene.String()
    ship_to_name_1 = graphene.String()
    country_sh = graphene.String()
    country_name = graphene.String()
    incoterm_s1 = graphene.String()
    incoterm_s2 = graphene.String()
    payment_term = graphene.String()
    payment_term_desc = graphene.String()
    e_ordering_status = graphene.String()
    contract_pi = graphene.String()


class CustomerUnloadingPoint(ModelObjectType):
    id = graphene.ID()
    sold_to_code = graphene.String()
    factory_calendar = graphene.String()
    factory_calendar_desc = graphene.String()
    unloading_point = graphene.String()

    class Meta:
        model = sap_master_data_models.SoldToUnloadingPointMaster


class CustomerLmsReportDateInput(graphene.InputObjectType):
    gte = graphene.Date()
    lte = graphene.Date()


class CustomerGpsTracking(graphene.ObjectType):
    car_registration_no = graphene.String()
    current_position = graphene.String()
    carrier = graphene.String()
    velocity = graphene.Float()
    last_signal_received_datetime = graphene.DateTime()
    payment_number = graphene.String()
    delivery_place = graphene.String()
    car_status = graphene.String()
    destination_reach_time = graphene.Time()
    estimated_to_customer_from_current_location = graphene.Time()
    remaining_distance_as_kilometer = graphene.String()
    estimate_arrival_time = graphene.Time()
    distance_from_factory_to_customer = graphene.Float()
    isssuance_of_invoice_date = graphene.DateTime()
    delivery_deadline = graphene.DateTime()
    shipment_no = graphene.String()
    estimated_time = graphene.String()


class LmsReportCustomer(graphene.ObjectType):
    dp_no = graphene.String()
    po_no = graphene.String()
    so_no = graphene.String()
    item_no = graphene.String()
    departure_place_positions = graphene.String()
    material_description = graphene.String()
    quantity = graphene.Float()
    ship_to = graphene.String()
    gi_date = graphene.DateTime()
    car_registration_no = graphene.String()
    estimate_date_time = graphene.DateTime()
    transport_status = graphene.String()
    current_position = graphene.String()
    remaining_distance_as_kilometer = graphene.String()
    estimated_arrival_datetime = graphene.String()
    sale_unit = graphene.String()
    gps_tracking = graphene.Field(CustomerGpsTracking)


class CustomerLmsReportInput(graphene.InputObjectType):
    sold_to = graphene.List(graphene.String)
    material_no = graphene.List(graphene.String)
    po_no = graphene.String()
    so_no = graphene.String()
    sale_organization = graphene.String()
    delivery_date = graphene.Field(CustomerLmsReportDateInput)
