import graphene
from django.contrib.auth import get_user_model
from graphene import (
    ObjectType,
    relay
)

from saleor.graphql.account.types import (
    User,
    UserCountableConnection
)

from saleor.graphql.core.fields import FilterConnectionField
from saleor.graphql.core.types import ModelObjectType
from saleor.graphql.meta.types import ObjectWithMetadata
from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migrations_models
from scg_checkout.graphql.mutations.order import SapOrderMessage
from scg_checkout.graphql.types import (
    SalesOrganization,
    SalesGroup,
    ScgpSalesEmployee, SoldToSortInput,
)
from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text,resolve_sold_to_name

from scgp_export.graphql.types import ScgCountableConnection
from scgp_require_attention_items.graphql.enums import (
    SaleOrderStatusEnum,
    MaterialPricingGroupEnum,
    ReasonForReject,
    ChangeOrderStatusEnum,
    ChangeOrderOrderStatus
)
from scgp_require_attention_items.graphql.filters import (
    InputSalesOrder,
    SalesOrderFilterInput
)

from scgp_require_attention_items.graphql.resolvers.require_attention_items import (
    resolve_grade,
    resolve_gram,
    resolve_sales_unit,
    resolve_unit,
    resolve_status,
    resolve_sold_to,
    resolve_material,
    resolve_mat_code,
    resolve_order_no,
    resolve_mat_description,
    resolve_consignment_value,
    resolve_type_of_delivery_value,
    resolve_partial_delivery_split_order_value,
    resolve_name_from_material_master,
    resolve_po_no,
    resolve_sales_organization,
    resolve_sales_group,
    resolve_scgp_sales_employee,
    resolve_request_quantity,
    resolve_material_group_from_material_classification_master,
    resolve_gram_from_material_classification_master,
    resolve_code_from_material_classification_master,
    resolve_name_from_material_classification_master,
    resolve_items_from_order_line_i_plan,
    resolve_material_group,
    resolve_iplant_confirm_quantity_from_order_line,
    resolve_item_status_from_order_line,
    resolve_original_date_from_order_line,
    resolve_inquiry_method_code_from_order_line,
    resolve_transportation_method_code_from_order_line,
    resolve_type_of_delivery_from_order_line,
    resolve_fix_source_assignment_from_order_line,
    resolve_split_order_item_from_order_line,
    resolve_partial_delivery_from_order_line,
    resolve_consignment_from_order_line,
    resolve_code_from_material_master,
    resolve_overdue_1_from_order_line_i_plan,
    resolve_overdue_2_from_order_line_i_plan,
    resolve_code_from_sold_to_master,
    resolve_name_from_sold_to_master,
    resolve_order_id,
    resolve_ship_to, resolve_sales_order,
    resolve_require_attention_flag,
    resolve_create_by,
    resolve_create_date_time,
    resolve_create_date,
    resolve_req_delivery_date,
    resolve_confirm_date,
    resolve_order_item,
    resolve_rejection,
    resolve_delivery_block,
    resolve_sales_org,
    resolve_unit_sales_order,
    resolve_weight_unit,
    resolve_currency,
    resolve_material_code_description,
    resolve_item_status_from_order_line_i_plan,
    resolve_inquiry_method_code_from_order_line_i_plan,
    resolve_delivery_qty,
    resolve_weight_sale_order,
    resolve_sale_order_material_code
)

from scg_checkout.graphql.enums import (
    IPlanOrderItemStatus,
)


class MaterialMaster(ModelObjectType):
    material_code = graphene.String()
    description_th = graphene.String()
    description_en = graphene.String()
    material_group = graphene.String()
    material_type = graphene.String()
    material_type_desc = graphene.String()
    base_unit = graphene.String()
    base_unit_desc = graphene.String()
    delete_flag = graphene.String()
    net_weight = graphene.Float()
    gross_weight = graphene.Float()
    weight_unit = graphene.String()
    name = graphene.String()
    sales_unit = graphene.String()

    class Meta:
        model = sap_master_data_models.MaterialMaster


class SAPScgpMaterialGroup(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()

    class Meta:
        model = sap_master_data_models.MaterialMaster

    @staticmethod
    def resolve_code(root, info):
        return resolve_code_from_material_master(root)

    @staticmethod
    def resolve_name(root, info):
        return resolve_name_from_material_master(root)


class SAPCustomer(User):
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


class SAPCustomerCountableConnection(UserCountableConnection):
    class Meta:
        node = SAPCustomer


class SAPCheckoutCompany(ModelObjectType):
    id = graphene.ID(description="ID of company")
    code = graphene.String(description="code of company")
    name = graphene.String(description="name of company")
    users = graphene.ConnectionField(SAPCustomerCountableConnection)
    business_unit = graphene.Field(lambda: SAPBusinessUnit)

    class Meta:
        model = sap_master_data_models.CompanyMaster


class SAPBusinessUnit(ModelObjectType):
    id = graphene.ID(description="ID of business_unit")
    name = graphene.String(description="name of business_unit")
    code = graphene.String(description="code of business_unit")
    companies = graphene.List(SAPCheckoutCompany)

    class Meta:
        model = sap_migrations_models.BusinessUnits


class SAPSalesOrganization(ModelObjectType):
    id = graphene.ID(description="ID of sales_organization")
    name = graphene.String(description="name of sales_organization")
    code = graphene.String(description="code of sales_organization")
    business_unit = graphene.Field(SAPBusinessUnit)

    class Meta:
        model = sap_master_data_models.SalesOrganizationMaster


class SAPSalesGroup(ModelObjectType):
    id = graphene.ID(description="ID of sales_group")
    name = graphene.String(description="name of sales_group")
    code = graphene.String(description="code of sales_group")
    sales_organization = graphene.Field(lambda: SAPSalesOrganization)
    company = graphene.Field(SAPCheckoutCompany)

    class Meta:
        model = sap_migrations_models.SalesGroupMaster


class SAPScgpSalesEmployee(ModelObjectType):
    id = graphene.ID()
    name = graphene.String()
    code = graphene.String()

    class Meta:
        model = sap_migrations_models.SalesEmployee


class RequireAttentionItemView(ModelObjectType):
    id = graphene.Int()
    type = graphene.String()
    order_no = graphene.String()
    item_no = graphene.String()
    sold_to = graphene.String()
    ship_to = graphene.String()
    request_date = graphene.Date()
    confirmed_date = graphene.Date()
    po_no = graphene.String()
    plant = graphene.String()
    status = graphene.String()
    unit = graphene.String()
    material = graphene.String()
    mat_code = graphene.String()
    mat_description = graphene.String()
    request_quantity = graphene.Float()
    material_group = graphene.Field(SAPScgpMaterialGroup)
    grade = graphene.String()
    gram = graphene.String()
    sales_organization = graphene.Field(SAPSalesOrganization)
    sales_group = graphene.Field(SAPSalesGroup)
    scgp_sales_employee = graphene.Field(SAPScgpSalesEmployee)
    attention_type = graphene.String()
    iplant_confirm_quantity = graphene.Float()
    item_status = graphene.String()
    original_date = graphene.Date()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    inquiry_method_code = graphene.String()
    transportation_method = graphene.String()
    type_of_delivery = graphene.String()
    fix_source_assignment = graphene.String()
    split_order_item = graphene.String()
    partial_delivery = graphene.String()
    consignment = graphene.String()
    i_plan = graphene.Field(lambda: RequireAttentionIPlan)
    type_of_delivery_value = graphene.String()
    split_order_item_value = graphene.String()
    partial_delivery_value = graphene.String()
    consignment_value = graphene.String()
    extends = graphene.Field(lambda: RequireAttention)
    order_id = graphene.Int()
    flag_r5 = graphene.Boolean()
    assigned_quantity = graphene.Float()
    item_status_en = graphene.String()

    class Meta:
        model = sap_migrations_models.OrderLines

    @staticmethod
    def resolve_extends(root, info):
        return root.iplan

    @staticmethod
    def resolve_i_plan(root, info):
        return root.iplan

    @staticmethod
    def resolve_order_no(root, info):
        return resolve_order_no(root)

    @staticmethod
    def resolve_sold_to(root, info):
        return resolve_sold_to(root)

    @staticmethod
    def resolve_status(root, info):
        return resolve_status(root)

    @staticmethod
    def resolve_unit(root, info):
        return root.sales_unit

    @staticmethod
    def resolve_material(root, info):
        return resolve_material(root)

    @staticmethod
    def resolve_mat_code(root, info):
        return resolve_mat_code(root)

    @staticmethod
    def resolve_mat_description(root, info):
        return resolve_mat_description(root)

    @staticmethod
    def resolve_request_quantity(root, info):
        return resolve_request_quantity(root)

    @staticmethod
    def resolve_material_group(root, info):
        return resolve_material_group(root)

    @staticmethod
    def resolve_grade(root, info):
        return resolve_grade(root.id)

    @staticmethod
    def resolve_gram(root, info):
        return resolve_gram(root.id)

    @staticmethod
    def resolve_sales_organization(root, info):
        return resolve_sales_organization(root)

    @staticmethod
    def resolve_sales_group(root, info):
        return resolve_sales_group(root)

    @staticmethod
    def resolve_scgp_sales_employee(root, info):
        return resolve_scgp_sales_employee(root)

    @staticmethod
    def resolve_iplant_confirm_quantity(root, info):
        return resolve_iplant_confirm_quantity_from_order_line(root)

    @staticmethod
    def resolve_item_status(root, info):
        return resolve_item_status_from_order_line(root)

    @staticmethod
    def resolve_original_date(root, info):
        return resolve_original_date_from_order_line(root)

    @staticmethod
    def resolve_inquiry_method_code(root, info):
        return resolve_inquiry_method_code_from_order_line(root)

    @staticmethod
    def resolve_transportation_method(root, info):
        return resolve_transportation_method_code_from_order_line(root)

    @staticmethod
    def resolve_type_of_delivery(root, info):
        return resolve_type_of_delivery_from_order_line(root)

    @staticmethod
    def resolve_fix_source_assignment(root, info):
        return resolve_fix_source_assignment_from_order_line(root)

    @staticmethod
    def resolve_split_order_item(root, info):
        return resolve_split_order_item_from_order_line(root)

    @staticmethod
    def resolve_partial_delivery(root, info):
        return resolve_partial_delivery_from_order_line(root)

    @staticmethod
    def resolve_consignment(root, info):
        return resolve_consignment_from_order_line(root)

    @staticmethod
    def resolve_type_of_delivery_value(root, info):
        return resolve_type_of_delivery_value(resolve_type_of_delivery_from_order_line(root))

    @staticmethod
    def resolve_partial_delivery_value(root, info):
        return resolve_partial_delivery_split_order_value(resolve_partial_delivery_from_order_line(root))

    @staticmethod
    def resolve_split_order_item_value(root, info):
        return resolve_partial_delivery_split_order_value(resolve_split_order_item_from_order_line(root))

    @staticmethod
    def resolve_consignment_value(root, info):
        return resolve_consignment_value(resolve_consignment_from_order_line(root))

    @staticmethod
    def resolve_po_no(root, info):
        return resolve_po_no(root)

    @staticmethod
    def resolve_order_id(root, info):
        return resolve_order_id(root)

    @staticmethod
    def resolve_ship_to(root, info):
        return resolve_ship_to(root)

    @staticmethod
    def resolve_flag_r5(root, info):
        if root.attention_type and "R5" in root.attention_type:
            return True
        return False

    @staticmethod
    def resolve_item_status_en(root, info):
        return root and root.item_status_en and IPlanOrderItemStatus.get(
            root.item_status_en).name or ""


class RequireAttentionItems(ModelObjectType):
    id = graphene.Int()
    type = graphene.String()
    order_no = graphene.String()
    item_no = graphene.Float()
    sold_to = graphene.String()
    ship_to = graphene.String()
    request_date = graphene.Date()
    confirmed_date = graphene.Date()
    po_no = graphene.String()
    plant = graphene.String()
    status = graphene.String()
    unit = graphene.String()
    material = graphene.String()
    mat_code = graphene.String()
    mat_description = graphene.String()
    request_quantity = graphene.Float()
    material_group = graphene.Field(SAPScgpMaterialGroup)
    grade = graphene.String()
    gram = graphene.String()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    sales_organization = graphene.Field(SAPSalesOrganization)
    sales_group = graphene.Field(SAPSalesGroup)
    scgp_sales_employee = graphene.Field(SAPScgpSalesEmployee)
    extends = graphene.Field(lambda: RequireAttention)
    i_plan = graphene.Field(lambda: RequireAttentionIPlan)
    material_pricing_group = graphene.String()

    class Meta:
        model = sap_migrations_models.OrderLines

    @staticmethod
    def resolve_order_no(root, info):
        return resolve_order_no(root)

    @staticmethod
    def resolve_sold_to(root, info):
        return resolve_sold_to(root)

    @staticmethod
    def resolve_status(root, info):
        return resolve_status(root)

    @staticmethod
    def resolve_unit(root, info):
        return resolve_unit(root)

    @staticmethod
    def resolve_material(root, info):
        return resolve_material(root)

    @staticmethod
    def resolve_mat_code(root, info):
        return resolve_mat_code(root)

    @staticmethod
    def resolve_mat_description(root, info):
        return resolve_mat_description(root)

    @staticmethod
    def resolve_request_quantity(root, info):
        return resolve_request_quantity(root)

    @staticmethod
    def resolve_grade(root, info):
        return resolve_grade(root.id)

    @staticmethod
    def resolve_gram(root, info):
        return resolve_gram(root.id)

    @staticmethod
    def resolve_sales_organization(root, info):
        return resolve_sales_organization(root)

    @staticmethod
    def resolve_sales_group(root, info):
        return resolve_sales_group(root)

    @staticmethod
    def resolve_scgp_sales_employee(root, info):
        return resolve_scgp_sales_employee(root)

    @staticmethod
    def resolve_extends(root, info):
        return root.iplan

    @staticmethod
    def resolve_i_plan(root, info):
        return root.iplan

    @staticmethod
    def resolve_po_no(root, info):
        return resolve_po_no(root)

    @staticmethod
    def resolve_ship_to(root, info):
        return resolve_ship_to(root)


class RequireAttention(ModelObjectType):
    items = graphene.Field(lambda: RequireAttentionItems)
    attention_type = graphene.String()
    iplant_confirm_quantity = graphene.Float()
    item_status = graphene.String()
    original_date = graphene.Date()
    inquiry_method_code = graphene.String()
    transportation_method = graphene.Int()
    type_of_delivery = graphene.String()
    fix_source_assignment = graphene.String()
    split_order_item = graphene.String()
    partial_delivery = graphene.String()
    consignment = graphene.String()
    type_of_delivery_value = graphene.String()
    split_order_item_value = graphene.String()
    partial_delivery_value = graphene.String()
    consignment_value = graphene.String()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()

    class Meta:
        model = sap_migrations_models.OrderLineIPlan

    @staticmethod
    def resolve_overdue_1(root, info):
        return resolve_overdue_1_from_order_line_i_plan(root)

    @staticmethod
    def resolve_overdue_2(root, info):
        return resolve_overdue_2_from_order_line_i_plan(root)

    @staticmethod
    def resolve_items(root, info):
        return resolve_items_from_order_line_i_plan(root)

    @staticmethod
    def resolve_type_of_delivery_value(root, info):
        return resolve_type_of_delivery_value(root.type_of_delivery)

    @staticmethod
    def resolve_partial_delivery_value(root, info):
        return resolve_partial_delivery_split_order_value(root.partial_delivery)

    @staticmethod
    def resolve_split_order_item_value(root, info):
        return resolve_partial_delivery_split_order_value(root.split_order_item)

    @staticmethod
    def resolve_consignment_value(root, info):
        return resolve_consignment_value(root.consignment)

    @staticmethod
    def resolve_item_status(root, info):
        return resolve_item_status_from_order_line_i_plan(root)

    @staticmethod
    def resolve_inquiry_method_code_from_order_line_i_plan(root, info):
        return resolve_inquiry_method_code_from_order_line_i_plan(root)


class RequireAttentionMaterial(ModelObjectType):
    id = graphene.Int()
    name = graphene.String()
    code = graphene.String()
    grade = graphene.String()
    gram = graphene.String()
    material_group = graphene.Field(SAPScgpMaterialGroup)

    class Meta:
        model = sap_master_data_models.MaterialClassificationMaster

    @staticmethod
    def resolve_gram(root, info):
        return resolve_gram_from_material_classification_master(root)

    @staticmethod
    def resolve_material_group(root, info):
        return resolve_material_group_from_material_classification_master(root)

    @staticmethod
    def resolve_code(root, info):
        return resolve_code_from_material_classification_master(root)

    @staticmethod
    def resolve_name(root, info):
        return resolve_name_from_material_classification_master(root)


class RequireAttentionSoldTo(ModelObjectType):
    id = graphene.Int()
    name = graphene.String()
    code = graphene.String()

    class Meta:
        model = sap_master_data_models.SoldToMaster

    @staticmethod
    def resolve_code(root, info):
        return resolve_code_from_sold_to_master(root)

    @staticmethod
    def resolve_name(root, info):
        return resolve_name_from_sold_to_master(root)


class RequireAttentionIPlan(ModelObjectType):
    items = graphene.Field(lambda: RequireAttentionItems)
    atp_ctp = graphene.String()
    atp_ctp_detail = graphene.String()
    block = graphene.String()
    run = graphene.String()

    class Meta:
        model = sap_migrations_models.OrderLineIPlan

    @staticmethod
    def resolve_items(root, info):
        return resolve_items_from_order_line_i_plan(root)


class RequireAttentionSoldToCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionSoldTo


class RequireAttentionSaleEmployeeCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ScgpSalesEmployee


class RequireAttentionMaterialCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionMaterial


class RequireAttentionMaterialGradeGramCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionMaterial


class RequireAttentionSalesOrganizationCountTableConnection(ScgCountableConnection):
    class Meta:
        node = SalesOrganization


class RequireAttentionSalesGroupCountTableConnection(ScgCountableConnection):
    class Meta:
        node = SalesGroup


class RequireAttentionEnums(ObjectType):
    name = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_name(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class RequireAttentionPlantCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionItems


class RequireAttentionCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttention


class RequireAttentionItemsCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionItems


class RequireAttentionItemsViewCountTableConnection(ScgCountableConnection):
    class Meta:
        node = RequireAttentionItemView


class ConfirmDate(ObjectType):
    success = FilterConnectionField(RequireAttentionItemsCountTableConnection)
    failed = FilterConnectionField(RequireAttentionItemsCountTableConnection)

    @staticmethod
    def resolve_success(root, info, **kwargs):
        return root[0]

    @staticmethod
    def resolve_failed(root, info, **kwargs):
        return root[1]


class OrderLineIPlan(ModelObjectType):
    attention_type = graphene.String()
    atp_ctp = graphene.String()
    atp_ctp_detail = graphene.String()
    block = graphene.String()
    run = graphene.String()
    iplant_confirm_quantity = graphene.Float()
    item_status = graphene.String()
    original_date = graphene.Date()
    inquiry_method_code = graphene.String()
    transportation_method = graphene.String()
    type_of_delivery = graphene.String()
    fix_source_assignment = graphene.String()
    split_order_item = graphene.String()
    partial_delivery = graphene.String()
    consignment = graphene.String()
    type_of_delivery_value = graphene.String()
    split_order_item_value = graphene.String()
    partial_delivery_value = graphene.String()
    consignment_value = graphene.String()
    paper_machine = graphene.String()
    sales_unit = graphene.String()

    class Meta:
        model = sap_migrations_models.OrderLineIPlan

    @staticmethod
    def resolve_type_of_delivery_value(root, info):
        return resolve_type_of_delivery_value(root.type_of_delivery)

    @staticmethod
    def resolve_partial_delivery_value(root, info):
        return resolve_partial_delivery_split_order_value(root.partial_delivery)

    @staticmethod
    def resolve_split_order_item_value(root, info):
        return resolve_partial_delivery_split_order_value(root.split_order_item)

    @staticmethod
    def resolve_consignment_value(root, info):
        return resolve_consignment_value(root.consignment)

    @staticmethod
    def resolve_paper_machine(root, info):
        # TODO Reconfirm with teammate on this field (run suppose to be paper machine)
        return root.paper_machine

    @staticmethod
    def resolve_sales_unit(root, info):
        return resolve_sales_unit(root)

    @staticmethod
    def resolve_item_status(root, info):
        return resolve_item_status_from_order_line_i_plan(root)


class ChangeParameterIPlanType(ObjectType):
    dropdown_domestic_or_export = graphene.String()
    dropdown_asap_clear_stock = graphene.String()

    @staticmethod
    def resolve_dropdown_asap_clear_stock(root, info):
        return root[1]

    @staticmethod
    def resolve_dropdown_domestic_or_export(root, info):
        return root[0]


class SalesOrder(ModelObjectType):
    id = graphene.ID()
    require_attention_flag = graphene.String()
    create_by = graphene.String()
    create_date_time = graphene.DateTime()
    sale_group = graphene.String()
    sales_org = graphene.String()
    sold_to = graphene.String()
    po_no = graphene.String()
    original_request_date = graphene.Date()
    create_date = graphene.Date()
    req_delivery_date = graphene.Date()
    confirm_date = graphene.Date()
    order_no = graphene.String()
    order_item = graphene.String()  # item_no ?
    material_code_description = graphene.String()
    material_code = graphene.String()
    order_qty = graphene.Float()
    confirm_order_qty = graphene.Float()
    delivery_qty = graphene.Float()
    pending_qty = graphene.Float()  # Order quantity - delivery quantity
    unit = graphene.String()
    plant = graphene.String()
    shipping_point = graphene.String()
    order_weight = graphene.Float()
    delivery_weight = graphene.Float()
    pending_weight = graphene.Float()  # Order weight - delivery weight
    weight_unit = graphene.String()
    net_price = graphene.Float()
    net_value = graphene.Float()
    currency = graphene.String()
    rejection = graphene.String()
    delivery_block = graphene.String()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    order_id = graphene.ID()

    class Meta:
        model = sap_migrations_models.OrderLines

    @staticmethod
    def resolve_require_attention_flag(root, info):
        return resolve_require_attention_flag(root)

    @staticmethod
    def resolve_create_by(root, info):
        return resolve_create_by(root)

    @staticmethod
    def resolve_sale_group(root, info):
        return resolve_sales_group(root)

    @staticmethod
    def resolve_create_date_time(root, info):
        return resolve_create_date_time(root)

    @staticmethod
    def resolve_sales_org(root, info):
        return resolve_sales_org(root)

    @staticmethod
    def resolve_sold_to(root, info):
        return resolve_sold_to(root)

    @staticmethod
    def resolve_po_no(root, info):
        return resolve_po_no(root)

    @staticmethod
    def resolve_original_request_date(root, info):
        return resolve_original_date_from_order_line(root)

    @staticmethod
    def resolve_create_date(root, info):
        return resolve_create_date(root)

    @staticmethod
    def resolve_req_delivery_date(root, info):
        return resolve_req_delivery_date(root)

    @staticmethod
    def resolve_confirm_date(root, info):
        return resolve_confirm_date(root)

    @staticmethod
    def resolve_order_no(root, info):
        return resolve_order_no(root)

    @staticmethod
    def resolve_order_item(root, info):
        return resolve_order_item(root)

    @staticmethod
    def resolve_material_code_description(root, info):
        return resolve_material_code_description(root)

    @staticmethod
    def resolve_order_qty(root, info):
        return resolve_request_quantity(root)

    @staticmethod
    def resolve_confirm_order_qty(root, info):
        return resolve_iplant_confirm_quantity_from_order_line(root)

    @staticmethod
    def resolve_delivery_qty(root, info):
        return resolve_delivery_qty(root)

    @staticmethod
    def resolve_pending_qty(root, info):
        return resolve_request_quantity(root) - resolve_delivery_qty(root)

    @staticmethod
    def resolve_unit(root, info):
        return resolve_unit_sales_order(root)

    @staticmethod
    def resolve_order_weight(root, info):
        return resolve_weight_sale_order(root.id, 'quantity')

    @staticmethod
    def resolve_delivery_weight(root, info):
        return resolve_weight_sale_order(root.id, 'delivery_quantity')

    @staticmethod
    def resolve_pending_weight(root, info):
        return resolve_weight_sale_order(root.id, 'quantity') - resolve_weight_sale_order(root.id, 'delivery_quantity')

    @staticmethod
    def resolve_weight_unit(root, info):
        return resolve_weight_unit(root)

    @staticmethod
    def resolve_currency(root, info):
        return resolve_currency(root)

    @staticmethod
    def resolve_rejection(root, info):
        return resolve_rejection(root)

    @staticmethod
    def resolve_delivery_block(root, info):
        return resolve_delivery_block(root)

    @staticmethod
    def resolve_order_id(root, info):
        return resolve_order_id(root)

    @staticmethod
    def resolve_material_code(root, info):
        return resolve_sale_order_material_code(root)


class SalesOrderCountableConnection(ScgCountableConnection):
    class Meta:
        node = SalesOrder


class Summary(ObjectType):
    order_qty = graphene.Float()
    confirm_order_qty = graphene.Float()
    delivery_qty = graphene.Float()
    pending_qty = graphene.Float()
    unit = graphene.String()
    order_weight = graphene.Float()
    delivery_weight = graphene.Float()
    pending_weight = graphene.Float()
    weight_unit = graphene.String()
    net_price = graphene.Float()
    net_value = graphene.Float()
    currency = graphene.String()


class SummaryCountableConnection(ScgCountableConnection):
    class Meta:
        node = Summary


class ReportListOfSalesOrder(ModelObjectType):
    id = graphene.ID()
    sold_to_code = graphene.String()
    sold_to_name = graphene.String()
    sales_order = FilterConnectionField(
        SalesOrderCountableConnection,
        sort_by=graphene.Argument(
            graphene.List(
                InputSalesOrder
            ), description="Sort_by",
        ),
        filter=SalesOrderFilterInput()
    )
    summary = FilterConnectionField(
        SummaryCountableConnection,
        filter=SalesOrderFilterInput()
    )

    class Meta:
        model = sap_master_data_models.SoldToMaster

    @staticmethod
    def resolve_sales_order(root, info, **kwargs):
        qs = resolve_sales_order(root.id)
        return resolve_connection_slice(
            qs, info, kwargs, SalesOrderCountableConnection)


class ReportListOfSalesOrderCountableConnection(ScgCountableConnection):
    class Meta:
        node = ReportListOfSalesOrder


class CreateBy(User):
    user_id = graphene.ID()

    class Meta:
        model = get_user_model()

    @staticmethod
    def resolve_user_id(root, info):
        return root.pk


class CreateByCountableConnection(ScgCountableConnection):
    class Meta:
        node = CreateBy


class RequireAttentionEditItems(graphene.ObjectType):
    order_no = graphene.String()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    request_date = graphene.Date()
    request_quantity = graphene.Float()
    original_quantity = graphene.Float()
    confirm_quantity = graphene.Float()
    original_request_date = graphene.Date()
    confirm_date = graphene.Date()
    sap_order_messages = graphene.List(SapOrderMessage)


class ReportOrderPendingSoldTo(RequireAttentionSoldTo):
    class Meta:
        model = sap_master_data_models.SoldToMaster

    @staticmethod
    def resolve_name(root, info):
        return resolve_sold_to_name(root.sold_to_code)


class ReportOrderPendingSoldToCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ReportOrderPendingSoldTo


class ReportOrderPendingShipToItems(graphene.ObjectType):
    name = graphene.String()
    code = graphene.String()


class ReportOrderPendingShipToCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ReportOrderPendingShipToItems


class SAPOrderLine(graphene.ObjectType):
    create_date_time = graphene.String()
    sales_org = graphene.String()
    sales_group = graphene.String()
    sold_to = graphene.String()
    po_no = graphene.String()
    original_request_date = graphene.String()
    create_date = graphene.String()
    req_delivery_date = graphene.String()
    order_no = graphene.String()
    item_no = graphene.String()
    mat_no = graphene.String()
    mat_desc = graphene.String()
    material_pricing_group = graphene.String()
    order_qty = graphene.String()
    confirm_order_qty = graphene.String()
    delivery_qty = graphene.String()
    pending_qty = graphene.String()
    unit = graphene.String()
    plant = graphene.String()
    shipping_point = graphene.String()
    order_weight = graphene.String()
    delivery_weight = graphene.String()
    pending_weight = graphene.String()
    weight_unit = graphene.String()
    net_price = graphene.String()
    net_value = graphene.String()
    currency = graphene.String()
    rejection = graphene.String()
    delivery_block = graphene.String()
    e_ordering_overdue_1 = graphene.Boolean()
    e_ordering_overdue_2 = graphene.Boolean()
    e_ordering_required_attention_flag = graphene.String()
    e_ordering_create_by = graphene.String()
    e_ordering_confirm_date = graphene.String()
    confirm_qty = graphene.String()
    non_confirm_qty = graphene.String()
    ship_to_name = graphene.String()
    e_ordering_request_date = graphene.String()
    e_ordering_item_status = graphene.String()
    iplan_confirm_date = graphene.String()
    sap_status = graphene.String()
    is_not_ref = graphene.Boolean()
    price_date = graphene.String()
    bom_flag = graphene.Boolean()
    parent_item_no = graphene.String()
    tracking_url = graphene.String()
    order_tracking_status = graphene.String()


class QuantitySummaryData(graphene.ObjectType):
    order_qty = graphene.String()
    confirm_order_qty = graphene.String()
    delivery_qty = graphene.String()
    pending_qty = graphene.String()
    quantity_unit = graphene.String()


class SAPListOfSaleOrderSummary(graphene.ObjectType):
    order_qty = graphene.String()
    quantity_data = graphene.String()
    confirm_order_qty = graphene.String()
    delivery_qty = graphene.String()
    pending_qty = graphene.String()
    unit = graphene.String()
    order_weight = graphene.String()
    delivery_weight = graphene.String()
    pending_weight = graphene.String()
    weight_unit = graphene.String()
    net_price = graphene.String()
    net_value = graphene.String()
    currency = graphene.String()
    quantity_data = graphene.List(
        QuantitySummaryData
    )


class SAPListOfSaleOrder(graphene.ObjectType):
    total_sold_to = graphene.Int()
    sold_to = graphene.String()
    sold_to_name_1 = graphene.String()
    order_lines = graphene.List(
        SAPOrderLine
    )
    summary = graphene.Field(SAPListOfSaleOrderSummary)


class SAPListOfSaleOrderDateInput(graphene.InputObjectType):
    gte = graphene.Date()
    lte = graphene.Date()


class SAPListOfSaleOrderInput(graphene.InputObjectType):
    sold_to = graphene.List(graphene.String)
    sale_org = graphene.String()
    channel = graphene.String()
    material_no_material_description = graphene.List(graphene.String)
    order_type = graphene.String()
    sale_group = graphene.String()
    create_date = graphene.Field(SAPListOfSaleOrderDateInput)
    request_delivery_date = graphene.Field(SAPListOfSaleOrderDateInput)
    material_group_1 = graphene.String()
    material_pricing_group = graphene.Argument(MaterialPricingGroupEnum)
    purchase_order_no = graphene.String()
    sale_order_no = graphene.String()
    plant = graphene.String()
    delivery_block = graphene.String()
    status = graphene.Argument(SaleOrderStatusEnum)
    require_attention_flag = graphene.String()
    sales_employee_no = graphene.String()
    create_by = graphene.String()
    sort_by_field = graphene.Field(SoldToSortInput)
    source_of_app = graphene.String()
    bu = graphene.String()
    is_order_tracking = graphene.Boolean()


class SAPListOfSaleOrderPendingInput(graphene.InputObjectType):
    sold_to = graphene.List(graphene.String)
    sale_org = graphene.List(graphene.String, required=True)
    ship_to = graphene.String()
    material_no_material_description = graphene.List(graphene.String)
    product_groups = graphene.String()
    create_date = graphene.Field(SAPListOfSaleOrderDateInput)
    request_delivery_date = graphene.Field(SAPListOfSaleOrderDateInput)
    po_no = graphene.String()
    so_no = graphene.String()
    transactions = graphene.List(graphene.String)
    bu = graphene.String()
    is_order_tracking = graphene.Boolean()
    source_of_app = graphene.String()


class SAPOrderLinePending(graphene.ObjectType):
    sale_org = graphene.String()
    sold_to = graphene.String()
    ship_to = graphene.String()
    request_date = graphene.String()
    order_date = graphene.String()  # create_date from ES25
    po_no = graphene.String()
    so_no = graphene.String()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    order_qty = graphene.String()
    pending_qty = graphene.String()
    atp_qty = graphene.String()
    ctp_qty = graphene.String()
    delivery_qty = graphene.String()
    sale_unit = graphene.String()
    confirm_date = graphene.String()
    ship_to_name = graphene.String()
    ship_to_code = graphene.String()
    ship_to_po_date = graphene.String()
    bom_flag = graphene.Boolean()
    parent_item_no = graphene.String()


class SAPListOfSaleOrderPendingSummary(graphene.ObjectType):
    order_qty = graphene.String()
    pending_qty = graphene.String()
    atp_qty = graphene.String()  # confirm qty
    ctp_qty = graphene.String()  # non-confirm qty
    delivery_qty = graphene.String()
    sale_unit = graphene.String()


class SAPListOfSaleOrderLineGroup(graphene.ObjectType):
    product_group = graphene.String()
    material_group = graphene.String()
    order_lines = graphene.List(
        SAPOrderLinePending
    )
    summary = graphene.List(SAPListOfSaleOrderPendingSummary)


class SAPListOfSaleOrderPending(graphene.ObjectType):
    sold_to = graphene.String()
    sold_to_name = graphene.String()
    product_groups = graphene.List(
        SAPListOfSaleOrderLineGroup
    )


class ReasonForRejectInput(graphene.InputObjectType):
    reason_for_reject = graphene.Field(ReasonForReject)


class SAPListOfSaleOrderAndExcel(graphene.ObjectType):
    excel = graphene.String()
    list_of_sale_order_sap = graphene.List(
        SAPListOfSaleOrder
    )


class SAPChangeOrderInput(SAPListOfSaleOrderInput):
    contract_no = graphene.String()
    dp_no = graphene.String()
    invoice_no = graphene.String()
    last_update_date = graphene.Field(SAPListOfSaleOrderDateInput)
    bu = graphene.String()
    status = graphene.Argument(ChangeOrderStatusEnum)
    ship_to = graphene.String()
    order_status = graphene.List(ChangeOrderOrderStatus)
    purchase_order_no = graphene.String()


class RequireAttentionCancelDeleteItems(graphene.ObjectType):
    order_no = graphene.String()
    item_no = graphene.String()
    material_code = graphene.String()
    material_description = graphene.String()
    confirm_quantity = graphene.Float()
    confirm_date = graphene.Date()
    message = graphene.String()


class ShowR5Popup(ObjectType):
    status = graphene.Boolean()
    item_errors = graphene.List(graphene.String)
