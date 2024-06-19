import graphene
from django.db.models import Count
from graphene import ObjectType

from saleor.graphql.core.connection import (
    filter_connection_queryset
)
from saleor.graphql.core.fields import (
    FilterConnectionField,
    ConnectionField,
)
from saleor.graphql.core.types import ModelObjectType
from saleor.graphql.core.connection import CountableConnection
from sap_migration.graphql.types import (
    SapContract,
    SalesOrganizationMaster,
    DistributionChannelMaster,
    DivisionMaster,
    SalesOfficeMaster,
    SalesGroupMaster,
    ContractMaterial,
    SoldToMaster,
)
from sap_master_data.models import (
    MaterialMaster,
    Conversion2Master
)
from scg_checkout.contract_order_update import get_tax_percent
from scg_checkout.graphql.enums import MaterialType
from scg_checkout.graphql.resolves.orders import resolve_sold_to_address, resolve_weight
from scg_checkout.graphql.helper import from_api_response_es26_to_change_order, resolve_ref_pi_no
from scg_checkout.graphql.resolves.product_variant import resolve_limit_quantity, resolve_cart_quantity
from scg_checkout.graphql.types import (
    OrderPartners,
    OrderItems,
    OrderCondition,
    OrderText,
)

from scg_checkout.graphql.types import (
    ScgpMaterialGroup,
    ScgpSalesEmployee,
)
from sap_migration import models as sap_migration_model
from sap_master_data import models as sap_master_models

from scgp_export.graphql.filters import CartPiFilterInput, CartFilterInput
from scgp_export.graphql.resolvers.carts import (
    resolve_cart_items,
    resolve_products,
    resolve_items,
)
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.resolvers.export_pis import resolve_remaining_quantity, resolve_remaining_quantity_ex
from scgp_export.graphql.resolvers.orders import (
    resolve_order_lines,
    resolve_currency,
)
from scg_customer.graphql.types import ScgUser
from scgp_export.graphql.sorters import (
    ExportCartSortingInput,
    ExportCartItemSortingInput,
    ExportOrderLinesSortingInput,
    ExportPIProductsSortingInput,
)
from sap_migration.models import (
    Contract,
    Cart,
    ContractMaterial as ContractMaterialModel,
    CartLines,
)
from scgp_require_attention_items.graphql.helper import PLANT_MAPPING
from scgp_user_management.graphql.types import ScgpUser


class ScgCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")

    class Meta:
        abstract = True


class ExportSoldToCountableConnection(CountableConnection):
    class Meta:
        node = SoldToMaster


class ExportPI(ModelObjectType):
    id = graphene.ID()
    sold_to = graphene.Field(SoldToMaster)
    code = graphene.String()
    po_no = graphene.String()
    sold_to_name = graphene.String()
    ship_to_name = graphene.String()
    ship_to_country = graphene.String()
    incoterm = graphene.String()
    payment_term = graphene.String()
    pi_products = FilterConnectionField(lambda: ExportPIProductCountTableConnection,
                                        sort_by=ExportPIProductsSortingInput())
    all_pi_products = graphene.List(
        lambda: ExportPIProduct,
    )
    currency = graphene.String()
    payment_term_key = graphene.String()
    sales_organization_code = graphene.String()
    ship_to = graphene.String()

    class Meta:
        model = Contract

    @staticmethod
    def resolve_pi_products(root, info, **kwargs):
        qs = resolve_products(root.id, info=info)
        return resolve_connection_slice(qs, info, kwargs, ExportPIProductCountTableConnection)

    @staticmethod
    def resolve_all_pi_products(root, info, **kwargs):
        qs = resolve_products(root.id, info=info)
        return qs

    @staticmethod
    def resolve_code(root, info):
        return root.code

    @staticmethod
    def resolve_ship_to_name(root, info):
        return root.ship_to

    @staticmethod
    def resolve_sales_organization_code(root, info):
        return root.sales_organization.code if root.sales_organization else ""

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_key


class ExportPICountableConnection(ScgCountableConnection):
    class Meta:
        node = ExportPI


class ExportProduct(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    slug = graphene.String()
    description = graphene.String()
    grade = graphene.String()
    gram = graphene.String()
    material_group = graphene.Field(lambda: ScgpMaterialGroup)
    material_type = graphene.String()

    class Meta:
        model = MaterialMaster

    @staticmethod
    def resolve_slug(root, info):
        return root.material_code

    @staticmethod
    def resolve_description(root, info):
        return root.description_th

    @staticmethod
    def resolve_name(root, info):
        contract_material_id = info.variable_values.get("contract_material_id")
        if not root.name:
            return ContractMaterialModel.objects.filter(id=contract_material_id).first().material_code
        return root.name


class ExportPIProduct(ModelObjectType):
    id = graphene.ID()
    item_no = graphene.String()
    pi = graphene.Field(SapContract)
    product = graphene.Field(ExportProduct)
    total_quantity = graphene.Float()
    remaining_quantity = graphene.Float(order_id=graphene.ID())
    remaining_quantity_ex = graphene.Float(order_id=graphene.ID())
    price_per_unit = graphene.Float()
    quantity_unit = graphene.String()
    currency = graphene.String()
    weight = graphene.Float()
    sales_unit = graphene.String()
    weight_unit = graphene.String()
    calculation = graphene.String()
    limit_quantity = graphene.Float()
    cart_quantity = graphene.Float()
    mat_group_1 = graphene.String()
    limit_quantity_order_line = graphene.Float()

    class Meta:
        model = ContractMaterialModel

    @staticmethod
    def resolve_remaining_quantity(root, info, order_id=None):
        return resolve_remaining_quantity(root.id, order_id, root.remaining_quantity)

    @staticmethod
    def resolve_remaining_quantity_ex(root, info, order_id=None):
        return resolve_remaining_quantity_ex(root.id, order_id, root.remaining_quantity_ex)

    @staticmethod
    def resolve_product(root, info):
        contract_material_id = root.id
        info.variable_values.update({"contract_material_id": contract_material_id})
        return root.material

    @staticmethod
    def resolve_sales_unit(root, info):
        # Confirmed with K.Piya on SEO-1652 ES-14 contractItem.salesUnit map with col sap_migration_contractmaterial.weight_unit
        return root.weight_unit

    @staticmethod
    def resolve_limit_quantity_order_line(root, info):
        return resolve_limit_quantity(root.contract.id, root.material.id, root.material.material_code, root.id,
                                      info=info, calculate_cart_quantity=False, item_no=root.item_no)

    @staticmethod
    def resolve_cart_quantity(root, info):
        return resolve_cart_quantity(root.contract.id, root.material.id, root.id,
                                      info=info, item_no=root.item_no)

    @staticmethod
    def resolve_limit_quantity(root, info):
        return resolve_limit_quantity(root.contract.id, root.material.id, root.material.material_code, root.id, info,
                                      item_no=root.item_no)

    @staticmethod
    def resolve_weight(root, info):
        mat_code = root.material_code or root.material.material_code
        calculation = getattr(root, "calculation", 0)
        if not calculation:
            conversion_objects = (
                Conversion2Master.objects.filter(
                    material_code=mat_code,
                    to_unit="ROL",
                )
                    .order_by("material_code", "-id")
                    .distinct("material_code")
                    .in_bulk(field_name="material_code")
            )
            conversion_object = conversion_objects.get(str(mat_code), None)
            calculation = conversion_object and conversion_object.calculation or 0
        return round(calculation / 1000, 3)

    @staticmethod
    def resolve_currency(root, info):
        return root.contract.currency


class ExportOrder(ModelObjectType):
    id = graphene.ID()
    pi = graphene.Field(SapContract)
    total_price = graphene.Float()
    tax_amount = graphene.Float()
    currency = graphene.String()
    status = graphene.String()
    # Agency
    request_delivery_date = graphene.Date()
    order_type = graphene.String()
    sales_organization = graphene.Field(SalesOrganizationMaster)
    distribution_channel = graphene.Field(DistributionChannelMaster)
    division = graphene.Field(DivisionMaster)
    sales_office = graphene.Field(SalesOfficeMaster)
    sales_group = graphene.Field(SalesGroupMaster)
    # Header
    ship_to = graphene.String()
    bill_to = graphene.String()
    po_date = graphene.Date()
    po_no = graphene.String()
    request_date = graphene.Date()
    ref_pi_no = graphene.String()
    net_price = graphene.Float()
    doc_currency = graphene.String()
    payment_term = graphene.String()
    incoterm = graphene.String()
    usage = graphene.String()
    unloading_point = graphene.String()
    place_of_delivery = graphene.String()
    port_of_discharge = graphene.String()
    port_of_loading = graphene.String()
    no_of_containers = graphene.String()
    shipping_mark = graphene.String()
    uom = graphene.String()
    gw_uom = graphene.String()
    etd = graphene.String()
    eta = graphene.String()
    dlc_expiry_date = graphene.Date()
    dlc_no = graphene.String()
    dlc_latest_delivery_date = graphene.Date()
    description = graphene.String()
    payer = graphene.String()
    end_customer = graphene.String()
    contact_person = graphene.String()
    sales_employee = graphene.String()
    author = graphene.String()
    payment_instruction = graphene.String()
    remark = graphene.String()
    production_information = graphene.String()
    internal_comment_to_warehouse = graphene.String()
    created_by = graphene.Field(ScgUser)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    lines = graphene.List(lambda: ExportOrderLine)
    eo_no = graphene.String()
    status_sap = graphene.String()
    order_no = graphene.String()
    scgp_sales_employee = graphene.Field(lambda: ScgpSalesEmployee)
    contract_type = graphene.String()
    sold_to_address = graphene.String()
    so_no = graphene.String()
    tax_percent = graphene.Float()
    incoterms_2 = graphene.String()

    class Meta:
        model = sap_migration_model.Order

    @staticmethod
    def resolve_shipping_mark(root, info):
        return root.shipping_mark

    @staticmethod
    def resolve_lines(root, info):
        return resolve_order_lines(root.id)

    @staticmethod
    def resolve_pi(root, info):
        return root.contract

    @staticmethod
    def resolve_currency(root, info):
        return resolve_currency(root.currency_id)

    @staticmethod
    def resolve_sold_to_address(root, info):
        return resolve_sold_to_address(root, info)

    @staticmethod
    def resolve_tax_percent(root, info):
        return get_tax_percent(root.sold_to.sold_to_code)

    @staticmethod
    def resolve_eo_no(root, info):
        return root.so_no


class ExportOrderLine(ModelObjectType):
    id = graphene.ID()
    order = graphene.Field(ExportOrder)
    pi_product = graphene.Field(ContractMaterial)
    quantity = graphene.Float()
    quantity_unit = graphene.String()
    weight = graphene.Float()
    weight_unit = graphene.String()
    vat_percent = graphene.Float()
    item_cat_eo = graphene.String()
    reject_reason = graphene.String()
    ref_pi_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    condition_group1 = graphene.String()
    material_group2 = graphene.String()
    commission_percent = graphene.Float()
    commission_amount = graphene.Float()
    commission_unit = graphene.String()
    request_date = graphene.Date()
    plant = graphene.String()
    route = graphene.String()
    roll_quantity = graphene.String()
    roll_diameter = graphene.String()
    roll_core_diameter = graphene.String()
    roll_per_pallet = graphene.String()
    package_quantity = graphene.String()
    pallet_size = graphene.String()
    pallet_no = graphene.String()
    packing_list = graphene.String()
    shipping_point = graphene.String()
    delivery_tol_under = graphene.Float()
    delivery_tol_over = graphene.Float()
    delivery_tol_unlimited = graphene.Boolean()
    remark = graphene.String()
    shipping_mark = graphene.String()
    cart_item = graphene.Field(lambda: ExportCartItem)
    net_price = graphene.Float()
    item_no = graphene.Float()
    confirmed_date = graphene.Date()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    attention_type = graphene.String()
    item_cat_pi = graphene.String()
    price_currency = graphene.String()
    no_of_rolls = graphene.String()
    no_of_package = graphene.String()
    eo_item_no = graphene.String()
    inquiry_method = graphene.String()
    item_status_en = graphene.String()
    item_status_th = graphene.String()
    assigned_quantity = graphene.Float()
    payment_term = graphene.String()
    is_material_outsource = graphene.Boolean()
    sales_unit = graphene.String()

    class Meta:
        model = sap_migration_model.OrderLines

    @staticmethod
    def resolve_pi_product(root, info):
        return root.contract_material

    @staticmethod
    def resolve_payment_term(root, info):
        return root.payment_term_item

    @staticmethod
    def resolve_weight(root, info):
        return resolve_weight(root, info)

    @staticmethod
    def resolve_material_description(root, info):
        if root.contract_material is None:
            return ""
        return root.contract_material.material_description

    @staticmethod
    def resolve_remark(root, info):
        if root.order.type == "export":
            return root.remark
        return root.shipping_mark

    @staticmethod
    def resolve_commission_unit(root, info):
        if root.commission_amount == "" or root.commission_amount is None:
            return ""
        return root.commission_unit

    @staticmethod
    def resolve_is_material_outsource(root, info):
        os_plant_list = MaterialType.MATERIAL_OS_PLANT.value
        material_plant = root.contract_material and root.contract_material.plant or ""
        return material_plant in os_plant_list

    @staticmethod
    def resolve_route(root, info):
        if root.route and root.route_name:
            return f"{root.route} - {root.route_name}"
        return root.route

    @staticmethod
    def resolve_sales_unit(root, info):
        """
        default EA for Container items else ROL
        """
        contract_material = root.contract_material
        if contract_material and contract_material.material.material_group == "PK00":
            return "EA"
        return "ROL"


class ExportCart(ModelObjectType):
    id = graphene.ID()
    pi = graphene.Field(ExportPI)
    sold_to = graphene.Field(SoldToMaster)
    created_by = graphene.Field(ScgUser)
    items = graphene.List(lambda: ExportCartItem)
    total_items = graphene.Int()
    is_active = graphene.Boolean()

    class Meta:
        model = Cart

    @staticmethod
    def resolve_items(root, info):
        return resolve_cart_items(root.id)

    @staticmethod
    def resolve_total_items(root, info):
        qs = resolve_cart_items(root.id)
        return len(qs)

    @staticmethod
    def resolve_pi(root, info):
        return root.contract


class ExportCartDetail(ExportCart):
    class Meta:
        model = Cart

    items = ConnectionField(lambda: ExportCartItemsCountableConnection, sort_by=ExportCartItemSortingInput())

    @staticmethod
    def resolve_items(root, info, **kwargs):
        qs = resolve_cart_items(root.id)
        return resolve_connection_slice(qs, info, kwargs, ExportCartItemsCountableConnection)


class ExportCartItem(ModelObjectType):
    id = graphene.ID()
    cart = graphene.Field(ExportCart)
    pi_product = graphene.Field(ExportPIProduct)
    quantity = graphene.Int()

    class Meta:
        model = CartLines

    @staticmethod
    def resolve_pi_product(root, info):
        return root.contract_material


class ScgCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")

    class Meta:
        abstract = True


class ExportCartCountableConnection(ScgCountableConnection):
    class Meta:
        node = ExportCart


class ExportCartExtended(ModelObjectType):
    total_pi = graphene.Int()
    total_sold_to = graphene.Int()
    total_cart_item = graphene.Int()
    carts = FilterConnectionField(
        ExportCartCountableConnection,
        filter=CartPiFilterInput(),
        sort_by=ExportCartSortingInput(),
    )

    class Meta:
        model = Cart

    @staticmethod
    def resolve_total_pi(root, info):
        return Cart.objects.annotate(quantity_cart_lines=Count('cartlines')).filter(created_by=info.context.user,
                                                                                    is_active=True,
                                                                                    quantity_cart_lines__gt=0,
                                                                                    type="export").count()

    @staticmethod
    def resolve_total_sold_to(root, info):
        count = set()
        qs = Cart.objects.annotate(quantity_cart_lines=Count('cartlines')).filter(created_by=info.context.user,
                                                                                  is_active=True,
                                                                                  quantity_cart_lines__gt=0,
                                                                                  type="export").values_list(
            'sold_to__id', flat=True)
        for q in qs:
            count.add(q)
        return len(count)

    @staticmethod
    def resolve_total_cart_item(root, info):
        return CartLines.objects.filter(cart__created_by=info.context.user, cart__type="export").count()

    @staticmethod
    def resolve_carts(root, info, **kwargs):
        qs = resolve_items(info.context.user.id)
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(qs, info, kwargs, ExportCartCountableConnection)


class ExportCartSearchExtended(ExportCartExtended):
    export_carts = FilterConnectionField(
        ExportCartCountableConnection,
        filter=CartFilterInput(),
        sort_by=ExportCartSortingInput(),
    )

    class Meta:
        model = Cart

    @staticmethod
    def resolve_export_carts(root, info, **kwargs):
        qs = resolve_items(info.context.user.id)
        qs = filter_connection_queryset(qs, kwargs)
        return resolve_connection_slice(qs, info, kwargs, ExportCartCountableConnection)


class ExportCartItemsCountableConnection(ScgCountableConnection):
    class Meta:
        node = ExportCartItem


class ExportOrderLineCountableConnection(ScgCountableConnection):
    class Meta:
        node = ExportOrderLine


class ExportOrderExtended(ExportOrder):
    lines = FilterConnectionField(
        ExportOrderLineCountableConnection,
        description="Order lines",
        sort_by=ExportOrderLinesSortingInput(description="Sort order line"),
    )

    class Meta:
        model = sap_migration_model.Order

    @staticmethod
    def resolve_lines(root, info, **kwargs):
        qs = resolve_order_lines(root.id)
        return resolve_connection_slice(qs, info, kwargs, ExportOrderLineCountableConnection)


class ExportOrderWithAllOrderLine(ExportOrder):
    lines = graphene.List(
        ExportOrderLine,
        description="Order lines",
        sort_by=ExportOrderLinesSortingInput(description="Sort order line"),
    )

    class Meta:
        model = sap_migration_model.Order

    @staticmethod
    def resolve_lines(root, info, **kwargs):
        return resolve_order_lines(root.id, **kwargs)


class ExportPIProductCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ExportPIProduct


class ExportOrderExtendedCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ExportOrderExtended


class SalesOrganizationCountTableConnection(ScgCountableConnection):
    class Meta:
        node = SalesOrganizationMaster


class ExportOrderCountableConnection(ScgCountableConnection):
    class Meta:
        node = ExportOrder


class StatusTypes(ObjectType):
    name = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_name(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class RouteListType(ObjectType):
    route = graphene.String()
    routeDescription = graphene.String()


class RouteType(ObjectType):
    piMessageId = graphene.String()
    status = graphene.String()
    reason = graphene.String()
    routeList = graphene.List(RouteListType)


class CreditLimit(graphene.ObjectType):
    credit_control_area = graphene.String()
    credit_limit = graphene.String()
    credit_account = graphene.String()
    credit_limit_used = graphene.String()
    receivables = graphene.String()
    special_liabil = graphene.String()
    sale_value = graphene.String()
    credit_exposure = graphene.String()
    second_receivables = graphene.String()
    credit_avaiable = graphene.String()
    currency = graphene.String()
    credit_block_status = graphene.Boolean()

    class Meta:
        description = "Credit master mapping fields."


class CreditLimitInput(graphene.InputObjectType):
    contract_no = graphene.String()
    sold_to_code = graphene.String()
    sales_org_code = graphene.String()


class CustomerOrderList(graphene.ObjectType):
    customer = graphene.String()
    so_no_slash_item = graphene.String()
    quantity = graphene.Float()
    pending_quantity = graphene.Float()
    request_date = graphene.String()
    plant = graphene.String()
    so_no = graphene.String()
    create_date = graphene.String()
    create_by = graphene.Field(ScgpUser)
    sale_rep = graphene.String()
    po_no = graphene.String()


class ConsignmentList(graphene.ObjectType):
    customer_session = graphene.String()
    quantity = graphene.Float()
    future_dummy_stock = graphene.Float()
    plant = graphene.String()


class FreeStockList(graphene.ObjectType):
    plant = graphene.String()
    quantity = graphene.Float()


class StockOnHandReport(graphene.ObjectType):
    product_code = graphene.String()
    total_ur = graphene.Float()
    customer_order_quantity = graphene.Float()
    consignment_quantity = graphene.Float()
    free_quantity = graphene.Float()
    unit = graphene.String()
    summary_as_of = graphene.String()

    customer_order_list = graphene.List(CustomerOrderList)
    consignment_list = graphene.List(ConsignmentList)
    free_stock_list = graphene.List(FreeStockList)
    all_plant = graphene.List(graphene.String)

    @staticmethod
    def resolve_all_plant(root, info):
        return [f'{key} - {value.get("name2")}' for key, value in PLANT_MAPPING.items()]


class ExportOrderAllItemBySoNo(graphene.ObjectType):
    eo_no = graphene.String()
    contract_no = graphene.String()
    order_type = graphene.String()
    sales_org = graphene.String()
    sales_org_name = graphene.String()
    distribution_channel = graphene.String()
    division = graphene.String()
    sales_off = graphene.String()
    sales_off_name = graphene.String()
    sales_group = graphene.String()
    sales_group_name = graphene.String()
    po_no = graphene.String()
    request_date = graphene.String()
    original_request_date = graphene.String()
    doc_currency = graphene.String()
    payment_terms = graphene.String()
    incoterms_1 = graphene.String()
    incoterms_1_name = graphene.String()
    incoterms_2 = graphene.String()
    order_amt_before_vat = graphene.String()
    order_amt_vat = graphene.String()
    order_amt_after_vat = graphene.String()
    confirm_date = graphene.String()
    description = graphene.String()
    usage = graphene.String()
    unloading_point = graphene.String()
    order_partners = graphene.List(OrderPartners)
    order_items = graphene.List(OrderItems)
    order_condition = graphene.List(OrderCondition)
    order_text = graphene.List(OrderText)
    fixed_item_no = graphene.List(graphene.String)
    tax_percent = graphene.Float()
    ref_pi_no = graphene.String()
    po_date = graphene.String()
    order_status = graphene.String()

    @staticmethod
    def resolve_eo_no(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'saleDocument')

    @staticmethod
    def resolve_contract_no(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'contractNo')

    @staticmethod
    def resolve_order_type(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'docType')

    @staticmethod
    def resolve_sales_org(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOrg')
        sales_org = sap_master_models.SalesOrganizationMaster.objects.filter(code=code).first()
        return f"{sales_org.code} - {sales_org.short_name}" if sales_org else ""

    @staticmethod
    def resolve_sales_org_name(root, info, **kwargs):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOrg')
        sales_org = sap_master_models.SalesOrganizationMaster.objects.filter(code=code).first()
        return sales_org.name if sales_org else ""

    @staticmethod
    def resolve_distribution_channel(root, info, **kwargs):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'distributionChannel')
        distribution_channel = sap_master_models.DistributionChannelMaster.objects.filter(code=code).first()
        return f"{distribution_channel.code} - {distribution_channel.name}" if distribution_channel else ""

    @staticmethod
    def resolve_division(root, info):
        div_code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'division')
        division = sap_master_models.DivisionMaster.objects.filter(code=div_code).first()
        return f"{division.code} - {division.name}" if division else ""

    @staticmethod
    def resolve_sales_off(root, info):
        return ExportOrderAllItemBySoNo.resolve_sales_off_name(root, info)

    @staticmethod
    def resolve_sales_off_name(root, info):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesOff')
        sales_off = sap_migration_model.SalesOfficeMaster.objects.filter(code=code).first()
        return f"{code} - {sales_off.name}" if sales_off else ""

    @staticmethod
    def resolve_sales_group(root, info):
        sale_group_code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesGroup')
        sales_group = sap_migration_model.SalesGroupMaster.objects.filter(code=sale_group_code).first()
        return f"{sales_group.code} - {sales_group.name}"

    @staticmethod
    def resolve_sales_group_name(root, info, **kwargs):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'salesGroup')
        sales_group = sap_master_models.SalesGroup.objects.filter(sales_group_code=code).first()
        return sales_group.sales_group_description if sales_group else ""

    @staticmethod
    def resolve_po_no(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'poNo')

    @staticmethod
    def resolve_request_date(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'reqDate')

    @staticmethod
    def resolve_doc_currency(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'currency')

    @staticmethod
    def resolve_payment_terms(root, info, **kwargs):
        payment_term_key = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'paymentTerms')
        return payment_term_key

    @staticmethod
    def resolve_incoterms_1(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms1')

    @staticmethod
    def resolve_incoterms_1_name(root, info, **kwargs):
        code = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms1')
        incoterms_1 = sap_master_models.Incoterms1Master.objects.filter(code=code).first()
        return incoterms_1.description if incoterms_1 else ""

    @staticmethod
    def resolve_incoterms_2(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'incoterms2')

    @staticmethod
    def resolve_order_amt_before_vat(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtBeforeVat')

    @staticmethod
    def resolve_order_amt_vat(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtVat')

    @staticmethod
    def resolve_order_amt_after_vat(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'orderAmtAfterVat')

    @staticmethod
    def resolve_confirm_date(root, info, **kwargs):
        order_lines = sap_migration_model.OrderLines.objects.filter(
            order__eo_no=info.variable_values.get('soNo')).first()
        return order_lines.confirmed_date if order_lines else ''

    @staticmethod
    def resolve_description(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'description')

    @staticmethod
    def resolve_usage(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'usage')

    @staticmethod
    def resolve_unloading_point(root, info, **kwargs):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'unloadingPoint')

    @staticmethod
    def resolve_order_partners(root, info):
        return from_api_response_es26_to_change_order(info, 'orderPartners')

    @staticmethod
    def resolve_order_items(root, info):
        order = info.variable_values.get("order")
        lines = from_api_response_es26_to_change_order(info, 'orderItems')
        list_item_no = list(map(lambda x: x.get("itemNo").lstrip("0"), lines))
        item_no_of_order_line_exits_in_database = order.orderlines_set.filter(item_no__in=list_item_no).distinct(
            "item_no").order_by("item_no").in_bulk(field_name="item_no")
        for line in lines:
            item_no = line.get("itemNo", "").lstrip("0")
            line["id"] = item_no_of_order_line_exits_in_database.get(item_no).id \
                if item_no_of_order_line_exits_in_database.get(item_no) else None
        return lines

    @staticmethod
    def resolve_order_condition(root, info):
        return from_api_response_es26_to_change_order(info, 'orderCondition')

    @staticmethod
    def resolve_order_text(root, info):
        return from_api_response_es26_to_change_order(info, 'orderText')

    @staticmethod
    def resolve_fixed_item_no(root, info):
        order_item = from_api_response_es26_to_change_order(info, 'orderItems')
        return map(lambda x: x.get("itemNo", "").lstrip("0"), order_item)

    @staticmethod
    def resolve_tax_percent(root, info):
        order_partners = from_api_response_es26_to_change_order(info, "orderPartners")
        sold_to = list(filter(lambda item: item.get("partnerRole", "") == "AG", order_partners))

        if sold_to:
            sold_to_code = sold_to[0].get("partnerNo", "")
            return get_tax_percent(sold_to_code=sold_to_code)

        return 0.0

    @staticmethod
    def resolve_ref_pi_no(root, info):
        so_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'saleDocument')
        return resolve_ref_pi_no(so_no)

    @staticmethod
    def resolve_po_date(root, info):
        return from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'poDates')

    @staticmethod
    def resolve_order_status(root, info):
        so_no = from_api_response_es26_to_change_order(info, 'orderHeaderIn', 'saleDocument')
        return sap_migration_model.Order.objects.filter(so_no=so_no).first().status
