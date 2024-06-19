import graphene

from saleor.graphql.account.types import User
from saleor.graphql.core.connection import CountableConnection
from saleor.graphql.core.fields import FilterConnectionField
from saleor.graphql.core.types import ModelObjectType

from sap_master_data import models as sap_data_models
from sap_migration import models as sap_migrate_models
from sap_migration.graphql.resolvers.contract_materials import resolve_contract_materials
from scg_checkout.graphql.resolves.checkouts import resolve_purchase_unit
from scg_checkout.graphql.resolves.orders import get_address_from_code,get_sold_to_address_from_code
from scg_checkout.graphql.resolves.product_variant import resolve_limit_quantity

from scgp_export.graphql.resolvers.connections import resolve_connection_slice
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text, \
    resolve_domestic_sold_to_search_filter_display_text, resolve_sold_to_name
from scgp_export.graphql.sorters import ExportPIProductsSortingInput
from sap_migration.graphql.resolvers.sold_tos import (
    resolve_representatives,
    resolve_sold_to_address_text,
    resolve_external_comments_to_customer,
    resolve_internal_comments_to_warehouse,
    resolve_show_po_upload,
)


class ScgCountableConnection(CountableConnection):
    latest_page_item_number = graphene.Int(description="Item in last page.")

    class Meta:
        abstract = True


class SoldToMaster(ModelObjectType):
    id = graphene.ID()
    sold_to_code = graphene.String()
    sold_to_name = graphene.String()
    account_group_code = graphene.String()
    account_group_name = graphene.String()
    customer_class = graphene.String()
    customer_class_desc = graphene.String()
    status = graphene.String()
    customer_block = graphene.String()
    customer_block_desc = graphene.String()
    delete_flag = graphene.String()
    language = graphene.String()

    code = graphene.String()
    name = graphene.String()
    address_text = graphene.String()
    display_text = graphene.String()
    representatives = graphene.List("scgp_user_management.graphql.types.ScgpUser")
    internal_comments_to_warehouse = graphene.String()
    external_comments_to_customer = graphene.String()
    show_po_upload = graphene.Boolean()
    domestic_sold_to_search_filter_display_text = graphene.String()

    class Meta:
        model = sap_data_models.SoldToMaster

    @staticmethod
    def resolve_code(root, info):
        return root.sold_to_code

    @staticmethod
    def resolve_name(root, info):
        return get_sold_to_address_from_code(root.sold_to_code, type="name")

    @staticmethod
    def resolve_address_text(root, info):
        return get_sold_to_address_from_code(root.sold_to_code, "", info)

    @staticmethod
    def resolve_display_text(root, info):
        sold_to_name = resolve_sold_to_name(root.sold_to_code)
        return f"{root.sold_to_code} - {sold_to_name}"

    @staticmethod
    def resolve_representatives(root, info):
        return resolve_representatives(root)

    @staticmethod
    def resolve_internal_comments_to_warehouse(root, info):
        return resolve_internal_comments_to_warehouse(root)

    @staticmethod
    def resolve_external_comments_to_customer(root, info):
        return resolve_external_comments_to_customer(root)

    @staticmethod
    def resolve_show_po_upload(root, info):
        return resolve_show_po_upload(root)

    @staticmethod
    def resolve_sold_to_name(root, info):
        return resolve_sold_to_name(root.sold_to_code)

    @staticmethod
    def resolve_domestic_sold_to_search_filter_display_text(root, info):
        return resolve_domestic_sold_to_search_filter_display_text(root)


class SoldToMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SoldToMaster


class SoldToExternalMaster(ModelObjectType):
    id = graphene.ID()
    sold_to_code = graphene.String()
    sold_to_name = graphene.String()
    partner_function = graphene.String()
    external_customer_code = graphene.String()
    customer_code = graphene.String()
    customer_name = graphene.String()
    sold_to = graphene.Field(SoldToMaster)

    class Meta:
        model = sap_data_models.SoldToExternalMaster


class SoldToExternalMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SoldToExternalMaster


class MaterialMaster(ModelObjectType):
    id = graphene.ID()
    material_code = graphene.String()
    description = graphene.String()
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
    purchase_unit = graphene.String()
    width_of_roll = graphene.String()
    length_of_roll = graphene.String()
    limit_quantity = graphene.Float()
    code = graphene.String()

    class Meta:
        model = sap_data_models.MaterialMaster

    @staticmethod
    def resolve_purchase_unit(root, info, **kwargs):
        return resolve_purchase_unit(root, info)

    @staticmethod
    def resolve_width_of_roll(root, info):
        rs = root.materialclassificationmaster_set.first()
        if rs:
            return rs.roll_width or 0
        return 0

    @staticmethod
    def resolve_length_of_roll(root, info):
        rs = root.materialclassificationmaster_set.first()
        if rs:
            return rs.roll_length or 0
        return 0

    @staticmethod
    def resolve_limit_quantity(root, info):
        contract_id = info.variable_values.get("contractId")
        material_id = root.material.id
        variant_code = root.material.material_code
        return resolve_limit_quantity(contract_id, material_id, variant_code)

    @staticmethod
    def resolve_code(root, info):
        return root.material_code


class MaterialMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = MaterialMaster


class BusinessUnits(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_migrate_models.BusinessUnits


class BusinessUnitCountableConnection(ScgCountableConnection):
    class Meta:
        node = BusinessUnits


class SalesOrganizationMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()
    business_unit = graphene.Field(BusinessUnits)
    short_name = graphene.String()

    class Meta:
        model = sap_data_models.SalesOrganizationMaster


class SalesOrganizationMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SalesOrganizationMaster


class SalesGroupMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()
    sales_organization = graphene.Field(SalesOrganizationMaster)

    class Meta:
        model = sap_migrate_models.SalesGroupMaster


class SalesGroupMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SalesGroupMaster


class DistributionChannelMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_migrate_models.DistributionChannelMaster


class DistributionChannelMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = DistributionChannelMaster


class DivisionMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_migrate_models.DivisionMaster


class DivisionMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = DivisionMaster


class SalesOfficeMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()
    sales_organization = graphene.Field(SalesOrganizationMaster)

    class Meta:
        model = sap_migrate_models.SalesOfficeMaster


class SalesOfficeMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SalesOfficeMaster


class CompanyMaster(ModelObjectType):
    id = graphene.Int()
    code = graphene.String()
    name = graphene.String()
    business_unit = graphene.Field(BusinessUnits)
    user = graphene.Field(User)
    short_name = graphene.String()
    full_name = graphene.String()

    class Meta:
        model = sap_data_models.CompanyMaster


class Currency(ModelObjectType):
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CurrencyMaster


class SapContract(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    po_no = graphene.String()
    sold_to_code = graphene.String()
    project_name = graphene.String()
    start_date = graphene.Date()
    end_date = graphene.Date()
    payment_term = graphene.String()
    incoterm = graphene.String()
    company_code = graphene.String()
    sold_to = graphene.Field(SoldToMaster)
    business_unit = graphene.Field(BusinessUnits)
    company = graphene.Field(CompanyMaster)
    sold_to_name = graphene.String()
    ship_to_name = graphene.String()
    ship_to_country = graphene.String()
    pi_products = FilterConnectionField(lambda: ContractMaterialCountTableConnection,
                                        sort_by=ExportPIProductsSortingInput())
    all_pi_products = graphene.List(
        lambda: ContractMaterial,
    )
    po_date = graphene.Date()
    ship_to = graphene.String()
    bill_to = graphene.String()
    external_comments_to_customer = graphene.String()
    product_information = graphene.String()
    sales_organization = graphene.Field(SalesOrganizationMaster)
    distribution_channel = graphene.Field(DistributionChannelMaster)
    division = graphene.Field(DivisionMaster)
    sales_group = graphene.Field(SalesGroupMaster)
    sales_office = graphene.Field(SalesOfficeMaster)
    internal_comments_to_warehouse = graphene.String()
    currency = graphene.String()
    payment_term_key = graphene.String()
    etd = graphene.Date()
    eta = graphene.Date()
    place_of_delivery = graphene.String()

    class Meta:
        model = sap_migrate_models.Contract

    @staticmethod
    def resolve_pi_products(root, info, **kwargs):
        qs = resolve_contract_materials(root.id)
        return resolve_connection_slice(qs, info, kwargs, ContractMaterialCountTableConnection)

    @staticmethod
    def resolve_all_pi_products(root, info, **kwargs):
        qs = resolve_contract_materials(root.id)
        return qs

    @staticmethod
    def resolve_sold_to_name(root, info, **kwargs):
        return root.sold_to.sold_to_name

    @staticmethod
    def resolve_place_of_delivery(root, info, **kwargs):
        return getattr(root, "incoterms_2", None)


class ContractMaterial(ModelObjectType):
    id = graphene.ID()
    item_no = graphene.String()
    material_code = graphene.String()
    contract_no = graphene.String()
    total_quantity = graphene.Float()
    remaining_quantity = graphene.Float()
    remaining_quantity_ex = graphene.Float()
    price_per_unit = graphene.Float()
    quantity_unit = graphene.String()
    currency = graphene.String()
    weight_unit = graphene.String()
    weight = graphene.Float()
    delivery_over = graphene.Float()
    delivery_under = graphene.Float()
    plant = graphene.String()
    contract = graphene.Field(SapContract)
    material = graphene.Field(MaterialMaster)
    product = graphene.Field(MaterialMaster)
    condition_group1 = graphene.String()
    commission = graphene.String()
    commission_amount = graphene.String()
    com_unit = graphene.String()
    calculation = graphene.String()
    limit_quantity = graphene.Float()
    mat_group_1 = graphene.String()

    class Meta:
        model = sap_migrate_models.ContractMaterial

    @staticmethod
    def resolve_product(root, info):
        return root.material

    @staticmethod
    def resolve_calculation(root, info):
        conversion = sap_data_models.Conversion2Master.objects.filter(
            material_code=root.material.material_code, to_unit="ROL"
        ).last()
        if conversion is None:
            return 0
        return conversion.calculation

    @staticmethod
    def resolve_limit_quantity(root, info):
        return resolve_limit_quantity(root.contract.id, root.material.id, root.material.material_code, item_no=root.item_no)


class ContractMaterialCountTableConnection(ScgCountableConnection):
    class Meta:
        node = ContractMaterial


class CustomerGroupMaster(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CustomerGroupMaster


class CustomerGroup1Master(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CustomerGroup1Master


class CustomerGroup2Master(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CustomerGroup2Master


class CustomerGroup3Master(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CustomerGroup3Master


class CustomerGroup4Master(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()

    class Meta:
        model = sap_data_models.CustomerGroup4Master


class Incoterms1Master(ModelObjectType):
    id = graphene.ID()
    code = graphene.String()
    description = graphene.String()

    class Meta:
        model = sap_data_models.Incoterms1Master


class MaterialVariantMaster(ModelObjectType):
    material = graphene.Field(MaterialMaster)
    name = graphene.String()
    code = graphene.String()
    weight = graphene.Float()
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
    suggestion_material_grade_gram = graphene.String()

    class Meta:
        model = sap_migrate_models.MaterialVariantMaster

    @staticmethod
    def resolve_suggestion_material_grade_gram(root, info):
        return root.code[:10]


class MaterialVariantMasterCountTableConnection(ScgCountableConnection):
    class Meta:
        node = MaterialVariantMaster


class MaterialMasterCountTableConnection(ScgCountableConnection):
    class Meta:
        node = MaterialMaster


class Route(ModelObjectType):
    id = graphene.Int()
    route_code = graphene.String()
    route_description = graphene.String()

    class Meta:
        model = sap_migrate_models.Route


class RouteCountTableConnection(ScgCountableConnection):
    class Meta:
        node = Route
