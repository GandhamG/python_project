import graphene
from graphene import InputObjectType

from saleor.graphql.core.connection import CountableConnection
from sap_master_data.models import Conversion2Master
from sap_migration import models as sap_migration_models
from saleor.graphql.core.types import ModelObjectType
from scgp_cip.common.enum import ProductionFlag
from scgp_cip.dao.order_line.bom_material_repo import BomMaterialRepo
from scgp_cip.dao.order_line.conversion2master_repo import Conversion2MasterRepo
from scgp_cip.dao.order_line.material_master_repo import MaterialMasterRepo


class CipConversion2Master(ModelObjectType):
    to_unit = graphene.String()
    from_unit = graphene.String()
    calculation = graphene.Float()

    class Meta:
        model = Conversion2Master


class OrderOtcPartnerAddress(ModelObjectType):
    address_code = graphene.String()
    name1 = graphene.String()
    name2 = graphene.String()
    name3 = graphene.String()
    name4 = graphene.String()
    city = graphene.String()
    postal_code = graphene.String()
    district = graphene.String()
    street_1 = graphene.String()
    street_2 = graphene.String()
    street_3 = graphene.String()
    street_4 = graphene.String()
    location = graphene.String()
    transport_zone_code = graphene.String()
    transport_zone_name = graphene.String()
    country_code = graphene.String()
    country_name = graphene.String()
    telephone_no = graphene.String()
    telephone_extension = graphene.String()
    mobile_no = graphene.String()
    fax_no = graphene.String()
    fax_no_ext = graphene.String()
    email = graphene.String()
    language = graphene.String()
    tax_number1 = graphene.String()
    tax_number2 = graphene.String()
    tax_id = graphene.String()
    branch_id = graphene.String()

    class Meta:
        model = sap_migration_models.OrderOtcPartnerAddress


class OrderOtcPartner(ModelObjectType):
    id = graphene.ID()
    sold_to_code = graphene.String()
    partner_role = graphene.String()
    address = graphene.Field(OrderOtcPartnerAddress)

    class Meta:
        model = sap_migration_models.OrderOtcPartner


class CipTempOrderLine(ModelObjectType):
    id = graphene.ID()
    material_code = graphene.String()
    material_type = graphene.String()
    material_description = graphene.String()
    quantity = graphene.Float()
    customer_mat_code = graphene.String()
    plant = graphene.String()
    request_date = graphene.Date()
    payment_term_item = graphene.String()
    production_flag = graphene.String()
    item_no = graphene.String()
    price_currency = graphene.String()
    weight = graphene.Float()
    sales_unit = graphene.String()
    weight_unit = graphene.String()
    over_delivery_tol = graphene.Float()
    under_delivery_tol = graphene.Float()
    prc_group_1 = graphene.String()
    bom_flag = graphene.Boolean()
    parent_id = graphene.ID()
    parent_item_no = graphene.String()
    batch_no = graphene.String()
    sales_unit_list = graphene.List(CipConversion2Master)
    batch_flag = graphene.Boolean()
    net_price = graphene.Float()
    price = graphene.Float()
    internal_comments_to_warehouse = graphene.String()
    additional_remark = graphene.String()
    remark = graphene.String()
    ship_to = graphene.String()
    product_information = graphene.String()
    payment_term = graphene.String()
    confirmed_date = graphene.Date()
    overdue_1 = graphene.Boolean()
    overdue_2 = graphene.Boolean()
    attention_type = graphene.String()
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
    item_category = graphene.String()
    delivery_tol_unlimited = graphene.Boolean()
    po_no = graphene.String()
    po_date = graphene.Date()
    price_date = graphene.Date()
    request_date_change_reason = graphene.String()
    po_no_external = graphene.String()
    payment_condition = graphene.String()
    unit = graphene.String()
    status = graphene.String()
    order_quantity_ton = graphene.Float()
    split_items = graphene.List(lambda: CipTempOrderLine)
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
    po_item_no = graphene.String()
    sale_text1 = graphene.String()
    sale_text2 = graphene.String()
    sale_text3 = graphene.String()
    sale_text4 = graphene.String()
    batch_choice_flag = graphene.Boolean()
    item_note = graphene.String()
    lot_no = graphene.String()
    pr_item_text = graphene.String()
    production_memo = graphene.String()
    otc_ship_to = graphene.Field(OrderOtcPartner)
    bom_unit_quantity = graphene.Float()
    delivery_tol_under = graphene.Float()
    delivery_tol_over = graphene.Float()

    class Meta:
        model = sap_migration_models.OrderLines

    @staticmethod
    def resolve_sales_unit_list(root, info):
        is_bom_parent = root.bom_flag and not root.parent
        sales_unit_list = list(
            Conversion2MasterRepo.get_conversion_by_material_code(root.material_code)) if not is_bom_parent else []
        if not any(unit.to_unit == root.sales_unit for unit in sales_unit_list):
            sales_unit_list.append({
                "from_unit": root.weight_unit,
                "calculation": (root.weight or 0) / (root.quantity or 1),
                "to_unit": root.sales_unit,
            })
        return sales_unit_list

    @staticmethod
    def resolve_batch_flag(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.material_code)
        return material.batch_flag

    @staticmethod
    def resolve_customer_mat_code(root, info):
        return root.customer_mat_35

    @staticmethod
    def resolve_material_type(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.material_code)
        return material.material_type

    @staticmethod
    def resolve_material_description(root, info):
        material = MaterialMasterRepo.get_material_by_material_code(root.material_code)
        return material.description_en if material else ""

    @staticmethod
    def resolve_production_flag(root, info):
        return root.production_flag

    @staticmethod
    def resolve_bom_unit_quantity(root, info):
        return BomMaterialRepo.get_bom_unit_quantity(
            root.parent.material_code, root.material_code
        ) if root.parent else None

    @staticmethod
    def resolve_parent_item_no(root, info):
        return root.parent.item_no if root.parent else None

    def resolve_under_delivery_tol(root, info):
        return root.delivery_tol_under

    @staticmethod
    def resolve_over_delivery_tol(root, info):
        return root.delivery_tol_over

    @staticmethod
    def resolve_price(root, info):
        return root.price_per_unit

    @staticmethod
    def resolve_ship_to(root, info):
        return "" if root.otc_ship_to else root.ship_to


class CpOrderLineInput(InputObjectType):
    item_no = graphene.String()
    request_date = graphene.Date(description="date must be type yyyy-mm-dd")
    manual_price_flag = graphene.Boolean()


class CipOrderLineInput(InputObjectType):
    id = graphene.ID(description="id of order line")
    item_no = graphene.String()
    quantity = graphene.Float()
    request_date = graphene.Date(description="date must be type yyyy-mm-dd")
    plant = graphene.String()
    material_no = graphene.String(required=False)
    unit = graphene.String(required=False)
    product_information = graphene.String()
    delivery_tol_over = graphene.Float()
    delivery_tol_under = graphene.Float()
    delivery_tol_unlimited = graphene.Boolean()
    weight_unit = graphene.String()
    item_category = graphene.String()
    shipping_point = graphene.String()
    route = graphene.String()
    po_no = graphene.String()
    po_no_external = graphene.String()
    po_item_no = graphene.String()
    payment_term = graphene.String()
    weight = graphene.Float()
    request_date_change_reason = graphene.String()
    batch_choice_flag = graphene.Boolean()
    batch_no = graphene.String(required=False)
    bom_material_id = graphene.String(required=False)
    bom_flag = graphene.Boolean()
    production_flag = graphene.String()
    price_per_unit = graphene.Float()
    price_date = graphene.Date(description="date must be type yyyy-mm-dd")
    ship_to = graphene.String()
    internal_comments_to_warehouse = graphene.String(required=False)
    external_comments_to_customer = graphene.String()
    internal_comments_to_logistic = graphene.String()
    remark = graphene.String(required=False)
    sale_text1 = graphene.String(required=False)
    sale_text2 = graphene.String(required=False)
    sale_text3 = graphene.String(required=False)
    sale_text4 = graphene.String(required=False)
    item_note = graphene.String(required=False)
    pr_item_text = graphene.String(required=False)
    lot_no = graphene.String(required=False)
    production_memo = graphene.String(required=False)
    manual_price_flag = graphene.Boolean()


class CipAddOrderLineInput(InputObjectType):
    id = graphene.ID(description="id of order line")
    item_no = graphene.String()
    material_no = graphene.String()
    quantity = graphene.Float()
    unit = graphene.String()
    productionFlag = graphene.String()
    batch_no = graphene.String()
    request_date = graphene.Date(description="date must be type yyyy-mm-dd")
    price_per_unit = graphene.Float()
    payment_term = graphene.String()
    plant = graphene.String(required=False)
    delivery_tol_over = graphene.Float(required=False)
    delivery_tol_under = graphene.Float(required=False)
    delivery_tol_unlimited = graphene.Boolean(required=False)
    weight_unit = graphene.String(required=False)
    shipping_point = graphene.String(required=False)
    route = graphene.String(required=False)
    po_no = graphene.String(required=False)
    po_no_external = graphene.String(required=False)
    po_item_no = graphene.String(required=False)
    weight = graphene.Float(required=False)
    request_date_change_reason = graphene.String(required=False)
    batch_choice_flag = graphene.Boolean(required=False)
    bom_material_id = graphene.String(required=False)
    price_date = graphene.Date(description="date must be type yyyy-mm-dd")
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


class MaterialSearchSuggestionResponse(graphene.ObjectType):
    id = graphene.ID()
    material_code = graphene.String()
    description_en = graphene.String()
    sold_to_material_code = graphene.String()
    display_text = graphene.String()

    @staticmethod
    def resolve_display_text(root, info):
        return root.search_text


class MaterialSearchSuggestionCountableConnection(CountableConnection):
    class Meta:
        node = MaterialSearchSuggestionResponse


class PlantResponse(graphene.ObjectType):
    plant_code = graphene.String()
    plant_name = graphene.String()


class SplitCipOrderLineInput(graphene.InputObjectType):
    id = graphene.Int()
    item_no = graphene.String()
    quantity = graphene.Float()
    request_date = graphene.Date()
    production_flag = graphene.Field(ProductionFlag)
    is_parent = graphene.Boolean()
    original_item_id = graphene.Int()
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    sale_text_1 = graphene.String()
    sale_text_2 = graphene.String()
    sale_text_3 = graphene.String()
    sale_text_4 = graphene.String()
    remark = graphene.String()
    item_note_cip = graphene.String()
    pr_item_text_cip = graphene.String()
    lot_no = graphene.String()
    production_memo_pp = graphene.String()


class SplitCipOrderLineInputAfterCp(graphene.InputObjectType):
    id = graphene.Int()
    item_no = graphene.String()
    quantity = graphene.Float()
    request_date = graphene.Date()
    production_flag = graphene.Field(ProductionFlag)
    is_parent = graphene.Boolean()
    original_item_id = graphene.Int()
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    sale_text_1 = graphene.String()
    sale_text_2 = graphene.String()
    sale_text_3 = graphene.String()
    sale_text_4 = graphene.String()
    remark = graphene.String()
    item_note_cip = graphene.String()
    pr_item_text_cip = graphene.String()
    lot_no = graphene.String()
    production_memo_pp = graphene.String()
    plant = graphene.String()
    confirm_date = graphene.Date()
    parent_bom = graphene.String()
