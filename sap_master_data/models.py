from django.db import models

from saleor.account.models import User
from scg_checkout.models import ScgpMaterialGroup


class CurrencyMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CustomerGroupMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CustomerGroup1Master(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CustomerGroup2Master(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CustomerGroup3Master(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CustomerGroup4Master(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class CompanyMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    business_unit = models.ForeignKey(
        "sap_migration.BusinessUnits",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="company_master",
    )
    user = models.ManyToManyField(User, blank=True, related_name="master_company")
    short_name = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)


class SalesOrganizationMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    business_unit = models.ForeignKey(
        "sap_migration.BusinessUnits", null=True, blank=True, on_delete=models.CASCADE
    )
    user = models.ManyToManyField(
        User, blank=True, related_name="master_sales_organizations"
    )
    short_name = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)


class DistributionChannelMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["type"]),
        ]


class DivisionMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class TextIDMaster(models.Model):
    section = models.CharField(max_length=20, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)


class MaterialMaster(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True, unique=True)
    description_th = models.CharField(max_length=255, null=True, blank=True)
    description_en = models.CharField(max_length=255, null=True, blank=True)
    material_group = models.CharField(max_length=50, null=True, blank=True)
    material_type = models.CharField(max_length=10, null=True, blank=True)
    material_type_desc = models.CharField(max_length=255, null=True, blank=True)
    base_unit = models.CharField(max_length=10, null=True, blank=True)
    base_unit_desc = models.CharField(max_length=255, null=True, blank=True)
    delete_flag = models.CharField(max_length=1, null=True, blank=True)
    net_weight = models.FloatField(null=True, blank=True)
    gross_weight = models.FloatField(null=True, blank=True)
    weight_unit = models.CharField(max_length=10, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    sales_unit = models.CharField(max_length=255, null=True, blank=True)
    scgp_material_group = models.ForeignKey(
        ScgpMaterialGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    batch_flag = models.CharField(max_length=1, null=True, blank=True)


class MaterialSaleMaster(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    sales_unit = models.CharField(max_length=10, null=True, blank=True)
    tax_class1 = models.CharField(max_length=10, null=True, blank=True)
    tax_class1_desc = models.CharField(max_length=255, null=True, blank=True)
    material_group1 = models.CharField(max_length=10, null=True, blank=True)
    material_group1_desc = models.CharField(max_length=255, null=True, blank=True)
    material_group2 = models.CharField(max_length=10, null=True, blank=True)
    material_group2_desc = models.CharField(max_length=255, null=True, blank=True)
    material_group3 = models.CharField(max_length=10, null=True, blank=True)
    material_group3_desc = models.CharField(max_length=255, null=True, blank=True)
    material_group4 = models.CharField(max_length=10, null=True, blank=True)
    material_group4_desc = models.CharField(max_length=255, null=True, blank=True)
    material_group5 = models.CharField(max_length=10, null=True, blank=True)
    material_group5_desc = models.CharField(max_length=255, null=True, blank=True)
    delivery_plant = models.CharField(max_length=10, null=True, blank=True)
    delivery_plant_desc = models.CharField(max_length=255, null=True, blank=True)
    prodh = models.CharField(max_length=50, null=True, blank=True)
    prodh_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh1 = models.CharField(max_length=50, null=True, blank=True)
    prodh1_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh2 = models.CharField(max_length=50, null=True, blank=True)
    prodh2_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh3 = models.CharField(max_length=50, null=True, blank=True)
    prodh3_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh4 = models.CharField(max_length=50, null=True, blank=True)
    prodh4_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh5 = models.CharField(max_length=50, null=True, blank=True)
    prodh5_desc = models.CharField(max_length=50, null=True, blank=True)
    prodh6 = models.CharField(max_length=50, null=True, blank=True)
    prodh6_desc = models.CharField(max_length=50, null=True, blank=True)
    material_price_group = models.CharField(max_length=10, null=True, blank=True)
    material_price_group_desc = models.CharField(max_length=255, null=True, blank=True)
    item_category_group = models.CharField(max_length=10, null=True, blank=True)
    item_category_group_desc = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=10, null=True, blank=True)
    sale_text1_th = models.CharField(max_length=255, null=True, blank=True)
    sale_text2_th = models.CharField(max_length=255, null=True, blank=True)
    sale_text3_th = models.CharField(max_length=255, null=True, blank=True)
    sale_text4_th = models.CharField(max_length=255, null=True, blank=True)
    sale_text1_en = models.CharField(max_length=255, null=True, blank=True)
    sale_text2_en = models.CharField(max_length=255, null=True, blank=True)
    sale_text3_en = models.CharField(max_length=255, null=True, blank=True)
    sale_text4_en = models.CharField(max_length=255, null=True, blank=True)
    xchannel_status = models.CharField(max_length=50, null=True, blank=True)
    xchannel_status_desc = models.CharField(max_length=50, null=True, blank=True)
    xchannel_status_valid_from = models.CharField(max_length=50, null=True, blank=True)
    distribution_channel_status = models.CharField(max_length=50, null=True, blank=True)
    distribution_channel_status_desc = models.CharField(
        max_length=50, null=True, blank=True
    )
    distribution_channel_status_valid_from = models.CharField(
        max_length=50, null=True, blank=True
    )
    acct_asssmt_grp_mat = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = (
            "material_code",
            "sales_organization_code",
            "distribution_channel_code",
        )
        # separate index for material_code and material_group1
        indexes = [
            models.Index(fields=["material_code"]),
            models.Index(fields=["material_group1"]),
            models.Index(fields=["distribution_channel_code"]),
        ]


class MaterialPlantMaster(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True)
    plant_code = models.CharField(max_length=10, null=True, blank=True)
    sloc = models.CharField(max_length=10, null=True, blank=True)
    sloc_desc = models.CharField(max_length=255, null=True, blank=True)
    unit_issue = models.CharField(max_length=10, null=True, blank=True)
    plant_batch_flag = models.CharField(max_length=1, null=True, blank=True)
    plant_name2 = models.CharField(max_length=1, null=True, blank=True)

    class Meta:
        unique_together = ("material_code", "plant_code", "sloc")


class MaterialPurchaseMaster(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True)
    plant_code = models.CharField(max_length=10, null=True, blank=True)
    plant_name = models.CharField(max_length=255, null=True, blank=True)
    purchase_group = models.CharField(max_length=10, null=True, blank=True)
    purchase_group_desc = models.CharField(max_length=255, null=True, blank=True)
    order_unit = models.CharField(max_length=10, null=True, blank=True)
    auto_po = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = ("material_code", "plant_code")


class MaterialClassificationMaster(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True)
    grade = models.CharField(max_length=10, null=True, blank=True)
    basis_weight = models.CharField(max_length=50, null=True, blank=True)
    roll_width = models.CharField(max_length=50, null=True, blank=True)
    diameter = models.CharField(max_length=50, null=True, blank=True)
    roll_length = models.CharField(max_length=50, null=True, blank=True)
    core_size = models.CharField(max_length=50, null=True, blank=True)
    material = models.ForeignKey(
        MaterialMaster, null=True, blank=True, on_delete=models.CASCADE
    )


class Conversion1Master(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True, unique=True)
    pac_ream = models.FloatField(null=True, blank=True)
    ream_pal = models.FloatField(null=True, blank=True)
    sh_pac = models.FloatField(null=True, blank=True)
    pac_box = models.FloatField(null=True, blank=True)
    box_pal = models.FloatField(null=True, blank=True)
    msm_kg = models.FloatField(null=True, blank=True)


class Conversion2Master(models.Model):
    class Meta:
        indexes = [models.Index(fields=["material_code"])]

    material_code = models.CharField(max_length=50, null=True, blank=True)
    from_unit = models.CharField(max_length=10, null=True, blank=True)
    from_value = models.FloatField(null=True, blank=True)
    to_unit = models.CharField(max_length=10, null=True, blank=True)
    to_value = models.FloatField(null=True, blank=True)
    calculation = models.FloatField(null=True, blank=True)


class Conversion3Master(models.Model):
    material_code = models.CharField(max_length=50, null=True, blank=True)
    action = models.CharField(max_length=10, null=True, blank=True)
    unit = models.CharField(max_length=10, null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)


class SoldToMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    sold_to_name = models.CharField(max_length=255, null=True, blank=True)
    account_group_code = models.CharField(max_length=10, null=True, blank=True)
    account_group_name = models.CharField(max_length=255, null=True, blank=True)
    customer_class = models.CharField(max_length=10, null=True, blank=True)
    customer_class_desc = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=10, null=True, blank=True)
    customer_block = models.CharField(max_length=10, null=True, blank=True)
    customer_block_desc = models.CharField(max_length=255, null=True, blank=True)
    delete_flag = models.CharField(max_length=10, null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    user = models.ManyToManyField(User, related_name="master_sold_to")


class SoldToUnloadingPointMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    factory_calendar = models.CharField(max_length=10, null=True, blank=True)
    factory_calendar_desc = models.CharField(max_length=255, null=True, blank=True)
    unloading_point = models.CharField(max_length=255, null=True, blank=True)


class SoldToChannelMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    division_code = models.CharField(max_length=10, null=True, blank=True)
    company_code = models.CharField(max_length=10, null=True, blank=True)
    sales_group = models.CharField(max_length=10, null=True, blank=True)
    sales_group_desc = models.CharField(max_length=50, null=True, blank=True)
    payment_term = models.CharField(max_length=10, null=True, blank=True)
    payment_term_desc = models.CharField(max_length=50, null=True, blank=True)
    taxkd = models.CharField(max_length=10, null=True, blank=True)
    taxkd_desc = models.CharField(max_length=50, null=True, blank=True)
    incoterm1 = models.CharField(max_length=10, null=True, blank=True)
    incoterm2 = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, null=True, blank=True)
    customer_block = models.CharField(max_length=10, null=True, blank=True)
    customer_block_desc = models.CharField(max_length=50, null=True, blank=True)
    delete_flag = models.CharField(max_length=10, null=True, blank=True)
    del_plant = models.CharField(max_length=10, null=True, blank=True)
    del_plant_desc = models.CharField(max_length=50, null=True, blank=True)
    currency = models.CharField(max_length=10, null=True, blank=True)
    currency_desc = models.CharField(max_length=50, null=True, blank=True)
    unlimit_tol = models.CharField(max_length=10, null=True, blank=True)
    over_delivery_tol = models.FloatField(max_length=10, null=True, blank=True)
    under_delivery_tol = models.FloatField(max_length=10, null=True, blank=True)
    unlimit_tol = models.CharField(max_length=10, null=True, blank=True)
    price_group = models.CharField(max_length=10, null=True, blank=True)
    price_group_desc = models.CharField(max_length=50, null=True, blank=True)
    customer_group_code = models.CharField(max_length=10, null=True, blank=True)
    customer_group1_code = models.CharField(max_length=10, null=True, blank=True)
    customer_group2_code = models.CharField(max_length=10, null=True, blank=True)
    customer_group3_code = models.CharField(max_length=10, null=True, blank=True)
    customer_group4_code = models.CharField(max_length=10, null=True, blank=True)
    customer_group5_code = models.CharField(max_length=10, null=True, blank=True)
    customer_user = models.CharField(max_length=255, null=True, blank=True)
    sales_office = models.CharField(max_length=10, null=True, blank=True)
    sales_office_name = models.CharField(max_length=50, null=True, blank=True)
    credit_area = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = (
            "sold_to_code",
            "sales_organization_code",
            "distribution_channel_code",
            "division_code",
        )


class SoldToExternalMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sold_to_name = models.CharField(max_length=100, null=True, blank=True)
    partner_function = models.CharField(max_length=10, null=True, blank=True)
    external_customer_code = models.CharField(max_length=10, null=True, blank=True)
    customer_code = models.CharField(max_length=10, null=True, blank=True)
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    sold_to = models.ForeignKey(
        SoldToMaster, null=True, blank=True, on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (
            "sold_to_code",
            "external_customer_code",
        )


class SoldToChannelPartnerMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    division_code = models.CharField(max_length=10, null=True, blank=True)
    partner_code = models.CharField(max_length=10, null=True, blank=True)
    partner_role = models.CharField(max_length=10, null=True, blank=True)
    address_link = models.TextField(null=True, blank=True)


class SoldToPartnerAddressMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    partner_code = models.CharField(max_length=10, null=True, blank=True)
    address_code = models.CharField(max_length=10, null=True, blank=True)
    name1 = models.CharField(max_length=255, null=True, blank=True)
    name2 = models.CharField(max_length=255, null=True, blank=True)
    name3 = models.CharField(max_length=255, null=True, blank=True)
    name4 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    postal_code = models.CharField(max_length=10, null=True, blank=True)
    district = models.CharField(max_length=50, null=True, blank=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    street_sup1 = models.CharField(max_length=255, null=True, blank=True)
    street_sup2 = models.CharField(max_length=255, null=True, blank=True)
    street_sup3 = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    transport_zone_code = models.CharField(max_length=10, null=True, blank=True)
    transport_zone_name = models.CharField(max_length=50, null=True, blank=True)
    country_code = models.CharField(max_length=10, null=True, blank=True)
    country_name = models.CharField(max_length=50, null=True, blank=True)
    # belows are Fields from 'Telephone_List','Mobile_List','Fax','Email' Tab
    telephone_no = models.CharField(max_length=50, null=True, blank=True)
    telephone_extension = models.CharField(max_length=50, null=True, blank=True)
    mobile_no = models.CharField(max_length=50, null=True, blank=True)
    fax_no = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=50, null=True, blank=True)
    sold_to = models.ForeignKey(
        SoldToMaster, null=True, blank=True, on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (
            "sold_to_code",
            "partner_code",
            "address_code",
        )


class SoldToMaterialMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    sold_to_material_code = models.CharField(max_length=128, null=True, blank=True)
    material_code = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        unique_together = (
            "sold_to_code",
            "sales_organization_code",
            "distribution_channel_code",
            "sold_to_material_code",
        )


class SoldToTextMaster(models.Model):
    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    division_code = models.CharField(max_length=10, null=True, blank=True)
    text_id = models.CharField(max_length=10, null=True, blank=True)
    text_id_desc = models.CharField(max_length=255, null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    text_line = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = (
            "sold_to_code",
            "sales_organization_code",
            "distribution_channel_code",
            "division_code",
            "text_id",
        )


class Incoterms1Master(models.Model):
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)


class SoldToExternalSalesArea(models.Model):
    """
    table represent for tab 'Customer's sales area' in SEO-1316
    """

    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    distribution_channel_code = models.CharField(max_length=10, null=True, blank=True)
    division_code = models.CharField(max_length=10, null=True, blank=True)


class SoldToExternalSalesGroup(models.Model):
    """
    table represent for tab 'SKIC-TCP SalesGRP' in SEO-1316
    """

    sold_to_code = models.CharField(max_length=10, null=True, blank=True)
    sold_to_name = models.CharField(max_length=255, null=True, blank=True)
    material_group_code = models.CharField(max_length=50, null=True, blank=True)
    sales_group_code = models.CharField(max_length=10, null=True, blank=True)


class SalesGroup(models.Model):
    """
    table for Sale Group in SEO-1316
    """

    sales_organization_code = models.CharField(max_length=10, null=True, blank=True)
    sales_office_code = models.CharField(max_length=10, null=True, blank=True)
    sales_group_code = models.CharField(max_length=10, null=True, blank=True)
    sales_group_description = models.CharField(max_length=255, null=True, blank=True)


class CountryMaster(models.Model):
    country_code = models.CharField(max_length=10, unique=True)
    country_name = models.CharField(max_length=50, null=True)

    class Meta:
        db_table = "sap_master_data_countrymaster"


class TransportZone(models.Model):
    country_code = models.CharField(max_length=10, null=True)
    transport_zone_code = models.CharField(max_length=20, null=True)
    transport_zone_name = models.CharField(max_length=100, null=True)

    class Meta:
        db_table = "sap_master_data_transportzone"


class BomMaterial(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent_material_code = models.CharField(max_length=50, null=False)
    plant = models.CharField(max_length=50, null=True)
    item_number = models.CharField(max_length=10, null=False)
    material_code = models.CharField(max_length=50, null=False)
    quantity = models.FloatField(null=True)
    unit = models.CharField(max_length=10, null=True)
    valid_from = models.DateField(null=True)
    valid_to = models.DateField(null=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by_id = models.IntegerField(null=True)
    last_updated_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_updated_by_id = models.IntegerField(null=True)

    class Meta:
        db_table = "sap_master_data_bom_material"
        unique_together = ("parent_material_code", "material_code")
