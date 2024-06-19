import logging

import graphene
from graphene import ObjectType
from common.product_group import ProductGroupDescription
from saleor.graphql.core.types import ModelObjectType
from sap_master_data import models as sap_master_data_models
from sap_migration.graphql.types import SoldToMaster
from scg_checkout.graphql.resolves.orders import get_address_from_code
from scgp_export.graphql.resolvers.export_sold_tos import resolve_display_text
from scgp_export.graphql.types import ScgCountableConnection


class MaterialSaleMaster(ModelObjectType):
    material_code = graphene.String()
    sales_organization_code = graphene.String()
    distribution_channel_code = graphene.String()
    sales_unit = graphene.String()
    tax_class1 = graphene.String()
    tax_class1_desc = graphene.String()
    material_group1 = graphene.String()
    material_group1_desc = graphene.String()
    material_group2 = graphene.String()
    material_group2_desc = graphene.String()
    material_group3 = graphene.String()
    material_group3_desc = graphene.String()
    material_group4 = graphene.String()
    material_group4_desc = graphene.String()
    material_group5 = graphene.String()
    material_group5_desc = graphene.String()
    delivery_plant = graphene.String()
    delivery_plant_desc = graphene.String()
    prodh = graphene.String()
    prodh_desc = graphene.String()
    prodh1 = graphene.String()
    prodh1_desc = graphene.String()
    prodh2 = graphene.String()
    prodh2_desc = graphene.String()
    prodh3 = graphene.String()
    prodh3_desc = graphene.String()
    prodh4 = graphene.String()
    prodh4_desc = graphene.String()
    prodh5 = graphene.String()
    prodh5_desc = graphene.String()
    prodh6 = graphene.String()
    prodh6_desc = graphene.String()
    material_price_group = graphene.String()
    material_price_group_desc = graphene.String()
    item_category_group = graphene.String()
    item_category_group_desc = graphene.String()
    status = graphene.String()
    sale_text1_th = graphene.String()
    sale_text2_th = graphene.String()
    sale_text3_th = graphene.String()
    sale_text4_th = graphene.String()
    sale_text1_en = graphene.String()
    sale_text2_en = graphene.String()
    sale_text3_en = graphene.String()
    sale_text4_en = graphene.String()
    xchannel_status = graphene.String()
    xchannel_status_desc = graphene.String()
    xchannel_status_valid_from = graphene.String()
    distribution_channel_status = graphene.String()
    distribution_channel_status_desc = graphene.String()
    distribution_channel_status_valid_from = graphene.String()
    acct_asssmt_grp_mat = graphene.String()

    class Meta:
        model = sap_master_data_models.MaterialSaleMaster

    @staticmethod
    def resolve_material_group1_desc(root, info):
        try:
            material_group = ProductGroupDescription[root.material_group1].value
        except Exception as e:
            material_group = ""
            logging.info(
                f" Material group code : {root.material_group1} exception: {e}"
            )
        return material_group


class MaterialSaleMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = MaterialSaleMaster


class RequireAttentionFlag(ObjectType):
    key = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_key(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class SourceOfApp(ObjectType):
    key = graphene.String()
    value = graphene.String()

    @staticmethod
    def resolve_key(root, info):
        return root[0]

    @staticmethod
    def resolve_value(root, info):
        return root[1]


class SoldToPartnerAddressMaster(ModelObjectType):
    sold_to_code = graphene.String()
    partner_code = graphene.String()
    address_code = graphene.String()
    name1 = graphene.String()
    name2 = graphene.String()
    name3 = graphene.String()
    name4 = graphene.String()
    city = graphene.String()
    postal_code = graphene.String()
    district = graphene.String()
    street = graphene.String()
    street_sup1 = graphene.String()
    street_sup2 = graphene.String()
    street_sup3 = graphene.String()
    location = graphene.String()
    transport_zone_code = graphene.String()
    transport_zone_name = graphene.String()
    country_code = graphene.String()
    country_name = graphene.String()
    # belows are Fields from 'Telephone_List','Mobile_List','Fax','Email' Tab
    telephone_no = graphene.String()
    telephone_extension = graphene.String()
    mobile_no = graphene.String()
    fax_no = graphene.String()
    email = graphene.String()
    sold_to = graphene.Field(SoldToMaster)
    display_code_name = graphene.String()
    name = graphene.String()
    address_text = graphene.String()
    display_text = graphene.String()
    code = graphene.String()

    class Meta:
        model = sap_master_data_models.SoldToPartnerAddressMaster

    @staticmethod
    def resolve_display_code_name(root, _info):
        return f'{root.partner_code}-{root.name1 or ""} {root.name2 or ""} {root.name3 or ""} {root.name4 or ""}'

    @staticmethod
    def resolve_name(root, info):
        return root.name1

    @staticmethod
    def resolve_address_text(root, info):
        address_fields = [
            "street",
            "street_sup1",
            "street_sup2",
            "street_sup3",
            "location",
            "district",
            "city",
            "postal_code"
        ]
        address = " ".join(filter(None, [
            getattr(root, field, "") for field in address_fields
        ]))
        return address

    @staticmethod
    def resolve_display_text(root, info):
        sold_to_name = resolve_display_text(root.sold_to_code)
        return f"{root.sold_to_code} - {sold_to_name}"

    @staticmethod
    def resolve_code(root, info):
        return root.partner_code


class SoldToPartnerAddressMasterCountableConnection(ScgCountableConnection):
    class Meta:
        node = SoldToPartnerAddressMaster


class SoldToTextMaster(ModelObjectType):
    sold_to_code = graphene.String()
    text_id = graphene.String()
    text_id_desc = graphene.String()
    language = graphene.String()
    text_line = graphene.String()

    class Meta:
        model = sap_master_data_models.SoldToTextMaster
