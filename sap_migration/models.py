from django.db import models
from django.utils import timezone

from saleor.account.models import User
from saleor.order import OrderStatus
from sap_master_data.models import (
    CompanyMaster,
    CurrencyMaster,
    CustomerGroup1Master,
    CustomerGroup2Master,
    CustomerGroup3Master,
    CustomerGroup4Master,
    CustomerGroupMaster,
    DistributionChannelMaster,
    DivisionMaster,
    Incoterms1Master,
    MaterialMaster,
    SalesOrganizationMaster,
    SoldToMaster,
)
from scgp_eo_upload.models import EoUploadLog
from scgp_export.graphql.enums import ScgpExportOrderStatusSAP
from scgp_po_upload.models import PoUploadFileLog
from scgp_po_upload.s3_storage import EOrderingS3Storage


class BusinessUnits(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class SalesEmployee(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class MaterialVariantMaster(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["material"]),
            models.Index(fields=["variant_type"]),
            models.Index(fields=["type"]),
        ]

    material = models.ForeignKey(
        MaterialMaster, blank=False, null=False, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, null=False, blank=False)
    code = models.CharField(
        max_length=50, null=True, blank=True, unique=False
    )  # matCode
    weight = models.FloatField(null=True, blank=True)
    description_th = models.CharField(
        max_length=255, null=True, blank=True
    )  # matDescriptionTH
    description_en = models.CharField(
        max_length=255, null=True, blank=True
    )  # matDescriptionEN
    type = models.CharField(max_length=255, null=True, blank=True)  # matType
    sales_unit = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)  # matStatus
    determine_type = models.CharField(
        max_length=255, null=True, blank=True
    )  # matDetermineType
    key_combination = models.CharField(max_length=255, null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    propose_reason = models.CharField(max_length=255, null=True, blank=True)
    grade = models.CharField(max_length=10, null=True, blank=True)
    basis_weight = models.CharField(max_length=50, null=True, blank=True)  # gram
    diameter = models.CharField(max_length=50, null=True, blank=True)  # dia
    variant_type = models.CharField(max_length=100, null=True, blank=True)


class AlternateMaterial(models.Model):
    material_own = models.ForeignKey(
        MaterialMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alternate_material_created_by",
    )
    sales_organization = models.ForeignKey(
        SalesOrganizationMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    sold_to = models.ForeignKey(
        SoldToMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alternate_material_updated_by",
    )
    type = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ("id",)
        unique_together = (
            "sales_organization",
            "sold_to",
            "material_own",
        )


class AlternateMaterialOs(models.Model):
    priority = models.IntegerField()
    alternate_material = models.ForeignKey(
        AlternateMaterial, on_delete=models.CASCADE, null=True, blank=True
    )
    material_os = models.ForeignKey(
        MaterialMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    diameter = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = []


class AlternateMaterialOSMappingFileLog(models.Model):
    file_name = models.CharField(max_length=255, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_path = models.FileField(
        upload_to="alternate_material_os_mapping_files",
        blank=True,
        storage=EOrderingS3Storage(),
    )
    uploaded_by = models.ForeignKey(
        User,
        related_name="alternate_material_os_mapping_file_logs",
        on_delete=models.CASCADE,
        null=True,
    )


class Contract(models.Model):
    code = models.CharField(max_length=255, null=True, blank=True, unique=True)
    po_no = models.CharField(max_length=255, null=True, blank=True)
    sold_to_code = models.CharField(max_length=255, null=True, blank=True)
    project_name = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    payment_term = models.CharField(max_length=255, blank=True, null=True)
    incoterm = models.CharField(max_length=10, blank=True, null=True)
    company = models.ForeignKey(
        CompanyMaster, on_delete=models.SET_NULL, null=True, blank=True
    )
    sold_to = models.ForeignKey(
        SoldToMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    ship_to_name = models.CharField(max_length=128, blank=True, null=True)
    ship_to_country = models.CharField(max_length=128, blank=True, null=True)
    business_unit = models.ForeignKey(
        BusinessUnits, null=True, blank=True, on_delete=models.CASCADE
    )
    po_date = models.DateField(blank=True, null=True)
    ship_to = models.CharField(max_length=255, blank=True, null=True)
    bill_to = models.CharField(max_length=255, blank=True, null=True)
    external_comments_to_customer = models.TextField(blank=True, null=True)
    product_information = models.CharField(max_length=250, blank=True, null=True)
    sales_organization = models.ForeignKey(
        SalesOrganizationMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    distribution_channel = models.ForeignKey(
        DistributionChannelMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    division = models.ForeignKey(
        DivisionMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    sales_group = models.ForeignKey(
        "sap_migration.SalesGroupMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sales_office = models.ForeignKey(
        "sap_migration.SalesOfficeMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    internal_comments_to_warehouse = models.TextField(blank=True, null=True)
    unloading_point = models.CharField(max_length=255, blank=True, null=True)
    payment_term_key = models.CharField(max_length=255, blank=True, null=True)
    payer = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    sales_employee = models.CharField(max_length=255, blank=True, null=True)
    author = models.CharField(max_length=255, blank=True, null=True)
    end_customer = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=255, blank=True, null=True)
    port_of_loading = models.CharField(max_length=255, null=True, blank=True)
    shipping_mark = models.TextField(null=True, blank=True)
    uom = models.CharField(max_length=255, null=True, blank=True)
    port_of_discharge = models.CharField(max_length=255, null=True, blank=True)
    no_of_containers = models.CharField(max_length=255, null=True, blank=True)
    gw_uom = models.CharField(max_length=255, null=True, blank=True)
    payment_instruction = models.TextField(null=True, blank=True)
    production_information = models.TextField(null=True, blank=True)
    remark = models.TextField(blank=True, null=True)
    contract_status = models.CharField(max_length=255, null=True, blank=True)
    prc_group1 = models.CharField(max_length=255, null=True, blank=True)
    incoterms_2 = models.CharField(max_length=255, null=True, blank=True)
    etd = models.DateField(blank=True, null=True)
    eta = models.DateField(blank=True, null=True)
    surname = models.CharField(max_length=255, blank=True, null=True)
    internal_comments_to_logistic = models.TextField(blank=True, null=True)
    usage = models.CharField(max_length=255, blank=True, null=True)
    usage_no = models.CharField(max_length=255, blank=True, null=True)
    port_of_loading_lang = models.CharField(max_length=10, blank=True, null=True)
    shipping_mark_lang = models.CharField(max_length=10, blank=True, null=True)
    uom_lang = models.CharField(max_length=10, blank=True, null=True)
    port_of_discharge_lang = models.CharField(max_length=10, blank=True, null=True)
    no_of_containers_lang = models.CharField(max_length=10, blank=True, null=True)
    gw_uom_lang = models.CharField(max_length=10, blank=True, null=True)
    payment_instruction_lang = models.CharField(max_length=10, blank=True, null=True)
    remark_lang = models.CharField(max_length=10, blank=True, null=True)
    production_information_lang = models.CharField(max_length=10, blank=True, null=True)
    internal_comments_to_warehouse_lang = models.CharField(
        max_length=10, blank=True, null=True
    )
    etd_lang = models.CharField(max_length=10, blank=True, null=True)
    eta_lang = models.CharField(max_length=10, blank=True, null=True)
    surname_lang = models.CharField(max_length=10, blank=True, null=True)
    external_comments_to_customer_lang = models.CharField(
        max_length=10, blank=True, null=True
    )
    internal_comments_to_logistic_lang = models.CharField(
        max_length=10, blank=True, null=True
    )
    web_user_line_lang = models.CharField(max_length=10, blank=True, null=True)
    web_user_line = models.CharField(max_length=255, blank=True, null=True)


class ContractMaterialDefaultManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ContractMaterialAllManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class ContractMaterial(models.Model):
    # set default manager to compatible with old code
    objects = ContractMaterialDefaultManager()

    # manager that return all record
    all_objects = ContractMaterialAllManager()
    item_no = models.CharField(max_length=255, null=True, blank=True)
    material_code = models.CharField(max_length=500, null=True, blank=True)
    material_description = models.CharField(max_length=255, null=True, blank=True)
    contract_no = models.CharField(max_length=500, null=True, blank=True)
    total_quantity = models.FloatField(null=True, blank=True)
    remaining_quantity = models.FloatField(null=True, blank=True)
    remaining_quantity_ex = models.FloatField(null=True, blank=True)
    price_per_unit = models.FloatField(null=True, blank=True)
    quantity_unit = models.CharField(null=True, blank=True, max_length=255)
    currency = models.CharField(null=True, blank=True, max_length=255)
    weight_unit = models.CharField(null=True, blank=True, max_length=255)
    weight = models.FloatField(null=True, blank=True)
    delivery_over = models.FloatField(null=True, blank=True)
    delivery_under = models.FloatField(null=True, blank=True)
    plant = models.CharField(null=True, blank=True, max_length=255)
    contract = models.ForeignKey(
        Contract, null=True, blank=True, on_delete=models.CASCADE
    )
    material = models.ForeignKey(
        MaterialMaster, null=True, blank=True, on_delete=models.CASCADE
    )
    payment_term = models.CharField(max_length=255, blank=True, null=True)
    condition_group1 = models.CharField(max_length=255, blank=True, null=True)
    commission = models.CharField(max_length=255, blank=True, null=True)
    commission_amount = models.CharField(max_length=255, blank=True, null=True)
    com_unit = models.CharField(max_length=255, blank=True, null=True)
    mat_type = models.CharField(max_length=255, blank=True, null=True)
    mat_group_1 = models.CharField(max_length=255, blank=True, null=True)
    additional_remark = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            "remaining_quantity",
            "pk",
        ]

        unique_together = ("item_no", "material_id", "contract_id")

        indexes = [
            models.Index(fields=["contract"]),
            models.Index(fields=["material"]),
            models.Index(fields=["material_code"]),
            models.Index(fields=["contract_no"]),
            models.Index(fields=["plant"]),
        ]


class Cart(models.Model):
    contract_no = models.CharField(max_length=255, null=True, blank=True)
    sold_to = models.ForeignKey(
        SoldToMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True
    )
    is_active = models.BooleanField(null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    contract = models.ForeignKey(
        Contract, null=True, blank=True, on_delete=models.CASCADE
    )


class CartLines(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)
    contract_material = models.ForeignKey(
        ContractMaterial, on_delete=models.CASCADE, null=True, blank=True
    )
    price = models.FloatField(blank=True, null=True)
    material_variant = models.ForeignKey(
        MaterialVariantMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    material = models.ForeignKey(
        MaterialMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    selected = models.BooleanField(blank=True, null=True, default=False)


class SalesOfficeMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    sales_organization = models.ForeignKey(
        SalesOrganizationMaster, null=True, blank=True, on_delete=models.CASCADE
    )
    company = models.ForeignKey(
        CompanyMaster, null=True, blank=True, on_delete=models.CASCADE
    )


class SalesGroupMaster(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    sales_organization = models.ForeignKey(
        SalesOrganizationMaster, null=True, blank=True, on_delete=models.CASCADE
    )
    company = models.ForeignKey(
        CompanyMaster, null=True, blank=True, on_delete=models.CASCADE
    )


class OrderLineIPlan(models.Model):
    attention_type = models.CharField(max_length=255, null=True, blank=True)
    atp_ctp = models.CharField(max_length=255, null=True, blank=True)
    atp_ctp_detail = models.CharField(max_length=500, null=True, blank=True)
    block = models.CharField(max_length=255, null=True, blank=True)
    run = models.CharField(max_length=255, null=True, blank=True)
    iplant_confirm_quantity = models.FloatField(null=True, blank=True)
    item_status = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    original_date = models.DateField(blank=True, null=True)
    inquiry_method_code = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    transportation_method = models.CharField(max_length=255, null=True, blank=True)
    type_of_delivery = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    fix_source_assignment = models.CharField(max_length=255, null=True, blank=True)
    split_order_item = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    partial_delivery = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    consignment = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    paper_machine = models.CharField(max_length=255, null=True, blank=True)
    iplant_confirm_date = models.DateField(null=True)
    order_type = models.CharField(max_length=255, null=True, blank=True)
    on_hand_stock = models.BooleanField(null=True)
    item_no = models.CharField(max_length=255, null=True, blank=True)
    use_inventory = models.BooleanField(null=True)
    use_consignment_inventory = models.BooleanField(null=True)
    use_projected_inventory = models.BooleanField(null=True)
    use_production = models.BooleanField(null=True)
    single_source = models.BooleanField(null=True)
    re_atp_required = models.BooleanField(null=True)
    request_type = models.CharField(max_length=255, null=True, blank=True)
    plant = models.CharField(max_length=255, null=True, blank=True)
    request_iplan_response = models.JSONField(null=True, blank=True)


class Order(models.Model):
    doc_type = models.CharField(max_length=255, null=True, blank=True)
    sales_organization = models.ForeignKey(
        SalesOrganizationMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    distribution_channel = models.ForeignKey(
        DistributionChannelMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    division = models.ForeignKey(
        DivisionMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    sales_group = models.ForeignKey(
        SalesGroupMaster, on_delete=models.SET_NULL, null=True, blank=True
    )
    sales_office = models.ForeignKey(
        SalesOfficeMaster, on_delete=models.SET_NULL, null=True, blank=True
    )
    request_date = models.DateField(blank=True, null=True)
    incoterms_1 = models.ForeignKey(
        Incoterms1Master, on_delete=models.SET_NULL, null=True, blank=True
    )
    incoterms_2 = models.CharField(max_length=255, null=True, blank=True)
    payment_term = models.CharField(max_length=255, null=True, blank=True)
    po_no = models.CharField(max_length=500, null=True, blank=True)
    po_date = models.DateField(blank=True, null=True)
    price_group = models.CharField(max_length=255, null=True, blank=True)
    price_date = models.DateField(blank=True, null=True)
    currency = models.ForeignKey(
        CurrencyMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    customer_group = models.ForeignKey(
        CustomerGroupMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    sales_district = models.CharField(max_length=255, null=True, blank=True)
    shipping_condition = models.CharField(max_length=255, null=True, blank=True)
    customer_group_1 = models.ForeignKey(
        CustomerGroup1Master, on_delete=models.CASCADE, null=True, blank=True
    )
    customer_group_2 = models.ForeignKey(
        CustomerGroup2Master, on_delete=models.CASCADE, null=True, blank=True
    )
    customer_group_3 = models.ForeignKey(
        CustomerGroup3Master, on_delete=models.CASCADE, null=True, blank=True
    )
    customer_group_4 = models.ForeignKey(
        CustomerGroup4Master, on_delete=models.CASCADE, null=True, blank=True
    )
    delivery_block = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, null=True, blank=True
    )
    type = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        User, default=None, null=True, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    internal_comments_to_warehouse = models.TextField(blank=True, null=True)
    internal_comments_to_logistic = models.TextField(blank=True, null=True)
    external_comments_to_customer = models.TextField(blank=True, null=True)
    product_information = models.TextField(blank=True, null=True)
    product_memo = models.CharField(max_length=250, blank=True, null=True)
    text_in_sales_order = models.CharField(max_length=250, blank=True, null=True)
    sb_lot_number = models.CharField(max_length=250, blank=True, null=True)
    item_note = models.CharField(max_length=250, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    adjust_qty = models.CharField(max_length=250, blank=True, null=True)
    remark_for_order_information = models.TextField(blank=True, null=True)
    material_sales_text = models.CharField(max_length=250, blank=True, null=True)
    payment_instruction = models.TextField(null=True, blank=True)
    total_price = models.FloatField(null=True, blank=True)
    total_price_inc_tax = models.FloatField(null=True, blank=True)
    tax_amount = models.FloatField(null=True, blank=True)
    status = models.CharField(default=OrderStatus.DRAFT, max_length=255)
    order_date = models.DateField(blank=True, null=True)
    order_no = models.CharField(max_length=50, blank=True, null=True)
    request_delivery_date = models.DateField(blank=True, null=True)
    ship_to = models.CharField(max_length=500, blank=True, null=True)
    bill_to = models.CharField(max_length=500, blank=True, null=True)
    unloading_point = models.CharField(max_length=255, blank=True, null=True)
    remark_for_invoice = models.TextField(null=True, blank=True)
    remark_for_logistic = models.TextField(null=True, blank=True)
    po_number = models.TextField(null=True, blank=True)
    order_type = models.TextField(null=True, blank=True)
    scgp_sales_employee = models.ForeignKey(
        SalesEmployee,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    so_no = models.CharField(max_length=10, null=True, blank=True)
    status_sap = models.CharField(
        default=ScgpExportOrderStatusSAP.BEING_PROCESS.value, max_length=255
    )
    ref_pi_no = models.CharField(max_length=255, blank=True, null=True)
    net_price = models.FloatField(max_length=50, blank=True, null=True)
    doc_currency = models.CharField(max_length=3, blank=True, null=True)
    incoterm = models.CharField(max_length=10, blank=True, null=True)
    usage = models.CharField(max_length=255, blank=True, null=True)
    place_of_delivery = models.CharField(max_length=255, blank=True, null=True)
    port_of_discharge = models.CharField(max_length=255, blank=True, null=True)
    port_of_loading = models.CharField(max_length=255, blank=True, null=True)
    no_of_containers = models.CharField(max_length=255, blank=True, null=True)
    shipping_mark = models.TextField(null=True, blank=True)
    uom = models.CharField(max_length=255, blank=True, null=True)
    gw_uom = models.CharField(max_length=255, blank=True, null=True)
    # TODO: make sure this is correct (update etd from date to char)
    # etd = models.DateField(blank=True, null=True)
    etd = models.CharField(max_length=255, blank=True, null=True)
    # eta = models.CharField(max_length=255, blank=True, null=True)
    eta = models.DateField(blank=True, null=True)
    dlc_expiry_date = models.DateField(blank=True, null=True)
    dlc_no = models.CharField(max_length=255, blank=True, null=True)
    dlc_latest_delivery_date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    payer = models.CharField(max_length=255, blank=True, null=True)
    end_customer = models.CharField(max_length=128, blank=True, null=True)
    contact_person = models.CharField(max_length=128, blank=True, null=True)
    sales_employee = models.CharField(max_length=128, blank=True, null=True)
    author = models.CharField(max_length=128, blank=True, null=True)
    eo_no = models.CharField(max_length=10, blank=True, null=True)
    etd_date = models.DateField(blank=True, null=True)
    pi_type = models.CharField(max_length=255, blank=True, null=True)
    change_type = models.CharField(max_length=255, blank=True, null=True)
    lot_no = models.CharField(max_length=255, blank=True, null=True)
    sales_email = models.CharField(max_length=255, blank=True, null=True)
    cc = models.CharField(max_length=255, blank=True, null=True)
    contract_type = models.CharField(max_length=255, blank=True, null=True)
    production_information = models.TextField(null=True, blank=True)
    internal_comment_to_warehouse = models.TextField(null=True, blank=True)
    sold_to = models.ForeignKey(
        SoldToMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    # tmp field for eo-upload
    # TODO: improve this
    sold_to_code = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(
        CompanyMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    credit_status = models.CharField(max_length=500, null=True, blank=True)
    dp_no = models.CharField(max_length=500, null=True, blank=True)
    invoice_no = models.CharField(max_length=500, null=True, blank=True)
    update_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="order_updated_by",
    )
    shipping_point = models.CharField(max_length=255, null=True, blank=True)
    route = models.CharField(max_length=255, null=True, blank=True)
    sap_order_number = models.CharField(max_length=255, null=True, blank=True)
    status_thai = models.CharField(max_length=255, null=True, blank=True)
    web_user_name = models.TextField(null=True, blank=True)
    info = models.CharField(null=True, blank=True, max_length=255)
    created_by_flow = models.CharField(null=True, blank=True, max_length=255)
    item_no_latest = models.CharField(null=True, blank=True, max_length=255)
    eo_upload_log = models.OneToOneField(
        EoUploadLog, on_delete=models.SET_NULL, null=True, blank=True
    )
    saved_sap_at = models.DateTimeField(null=True, blank=True)
    po_upload_file_log = models.ForeignKey(
        PoUploadFileLog, on_delete=models.CASCADE, null=True, blank=True
    )
    product_group = models.CharField(max_length=255, null=True, blank=True)


class OrderLineDefaultManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(draft=False)


class OrderLineAllManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class OrderOtcPartnerAddress(models.Model):
    id = models.BigAutoField(primary_key=True)
    address_code = models.CharField(max_length=10, null=True)
    name1 = models.CharField(max_length=255, null=True)
    name2 = models.CharField(max_length=255, null=True)
    name3 = models.CharField(max_length=255, null=True)
    name4 = models.CharField(max_length=255, null=True)
    city = models.CharField(max_length=50, null=True)
    postal_code = models.CharField(max_length=10, null=True)
    district = models.CharField(max_length=50, null=True)
    street_1 = models.CharField(max_length=255, null=True)
    street_2 = models.CharField(max_length=255, null=True)
    street_3 = models.CharField(max_length=255, null=True)
    street_4 = models.CharField(max_length=255, null=True)
    location = models.CharField(max_length=255, null=True)
    transport_zone_code = models.CharField(max_length=10, null=True)
    transport_zone_name = models.CharField(max_length=50, null=True)
    country_code = models.CharField(max_length=10, null=True)
    country_name = models.CharField(max_length=50, null=True)
    telephone_no = models.CharField(max_length=50, null=True)
    telephone_extension = models.CharField(max_length=50, null=True)
    mobile_no = models.CharField(max_length=50, null=True)
    fax_no = models.CharField(max_length=50, null=True)
    fax_no_ext = models.CharField(max_length=50, null=True)
    email = models.CharField(max_length=50, null=True)
    language = models.CharField(max_length=3)
    tax_number1 = models.CharField(max_length=50, null=True)
    tax_number2 = models.CharField(max_length=50, null=True)
    tax_id = models.CharField(max_length=50, null=True)
    branch_id = models.CharField(max_length=50, null=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="otc_partneraddress_created_by",
    )
    last_updated_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_updated_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="otc_partneraddress_updated_by",
    )

    class Meta:
        db_table = "sap_migration_order_otc_partneraddress"


class OrderOtcPartner(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    sold_to_code = models.CharField(max_length=10, null=True)
    partner_role = models.CharField(max_length=10, null=True)
    address = models.ForeignKey(OrderOtcPartnerAddress, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="otc_partner_created_by",
    )
    last_updated_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_updated_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="otc_partner_updated_by",
    )

    class Meta:
        db_table = "sap_migration_order_otc_partner"


class OrderLines(models.Model):
    # set default manager to compatible with old code
    objects = OrderLineDefaultManager()

    # manager that return all record
    all_objects = OrderLineAllManager()

    item_no = models.CharField(max_length=255, blank=True, null=True)
    original_item_no = models.CharField(max_length=255, blank=True, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    material = models.ForeignKey(
        MaterialMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    material_variant = models.ForeignKey(
        MaterialVariantMaster, on_delete=models.CASCADE, null=True, blank=True
    )
    customer_mat_35 = models.CharField(max_length=255, null=True, blank=True)
    target_quantity = models.FloatField(null=True, blank=True)
    sales_unit = models.CharField(max_length=255, null=True, blank=True)
    plant = models.CharField(max_length=255, null=True, blank=True)
    shipping_point = models.CharField(max_length=255, null=True, blank=True)
    route = models.CharField(max_length=255, null=True, blank=True)
    route_name = models.CharField(max_length=255, null=True, blank=True)
    po_no = models.CharField(max_length=255, null=True, blank=True)
    po_item_no = models.CharField(max_length=255, null=True, blank=True)
    item_category = models.CharField(max_length=255, null=True, blank=True)
    prc_group_1 = models.CharField(max_length=255, null=True, blank=True)
    prc_group_2 = models.CharField(max_length=255, null=True, blank=True)
    purch_nos = models.CharField(max_length=255, null=True, blank=True)
    po_date = models.DateField(blank=True, null=True)
    over_delivery_tol = models.IntegerField(blank=True, null=True)
    under_delivery_tol = models.IntegerField(blank=True, null=True)
    un_limit_tol = models.CharField(max_length=255, null=True, blank=True)
    payment_term_item = models.CharField(max_length=255, null=True, blank=True)
    reject_reason = models.CharField(max_length=255, null=True, blank=True)
    net_weight = models.FloatField(blank=True, null=True)
    gross_weight = models.FloatField(blank=True, null=True)
    product_hierarchy = models.CharField(max_length=255, null=True, blank=True)
    price_group = models.CharField(max_length=255, null=True, blank=True)
    material_pricing_group = models.CharField(max_length=255, null=True, blank=True)
    sales_district = models.CharField(max_length=255, null=True, blank=True)
    storage_location = models.CharField(max_length=255, null=True, blank=True)
    ref_doc = models.CharField(max_length=255, null=True, blank=True)
    ref_doc_it = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)
    quantity_unit = models.CharField(max_length=12, blank=True, null=True)
    weight = models.FloatField(null=True, blank=True)
    weight_unit = models.CharField(max_length=12, blank=True, null=True)
    net_price = models.FloatField(blank=True, null=True)
    vat_percent = models.FloatField(blank=True, null=True)
    item_cat_eo = models.CharField(max_length=12, blank=True, null=True)
    ref_pi_no = models.CharField(max_length=255, blank=True, null=True)
    material_code = models.CharField(max_length=50, blank=True, null=True)
    condition_group1 = models.CharField(max_length=50, blank=True, null=True)
    material_group2 = models.CharField(max_length=50, blank=True, null=True)
    commission_percent = models.FloatField(blank=True, null=True)
    commission_amount = models.FloatField(blank=True, null=True)
    commission_unit = models.CharField(max_length=3, blank=True, null=True)
    request_date = models.DateField(blank=True, null=True)
    roll_quantity = models.CharField(max_length=255, blank=True, null=True)
    roll_diameter = models.CharField(max_length=255, blank=True, null=True)
    roll_core_diameter = models.CharField(max_length=255, blank=True, null=True)
    roll_per_pallet = models.CharField(max_length=255, blank=True, null=True)
    package_quantity = models.CharField(max_length=255, blank=True, null=True)
    pallet_size = models.CharField(max_length=12, blank=True, null=True)
    pallet_no = models.CharField(max_length=12, blank=True, null=True)
    packing_list = models.CharField(max_length=128, blank=True, null=True)
    delivery_tol_under = models.FloatField(blank=True, null=True)
    delivery_tol_over = models.FloatField(blank=True, null=True)
    delivery_tol_unlimited = models.BooleanField(default=False, null=True)
    remark = models.TextField(null=True, blank=True)
    additional_remark = models.TextField(null=True, blank=True)
    cart_item = models.ForeignKey(CartLines, on_delete=models.SET_NULL, null=True)
    confirmed_date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=255, blank=True, null=True, default="export")
    overdue_1 = models.BooleanField(blank=True, null=True, default=False)
    overdue_2 = models.BooleanField(blank=True, null=True, default=False)
    flag = models.CharField(max_length=255, blank=True, default="Customer", null=True)
    attention_type = models.CharField(max_length=255, blank=True, null=True)
    item_cat_pi = models.CharField(max_length=255, blank=True, null=True)
    price_currency = models.CharField(max_length=255, blank=True, null=True)
    no_of_rolls = models.CharField(max_length=255, blank=True, null=True)
    no_of_package = models.CharField(max_length=255, blank=True, null=True)
    eo_item_no = models.CharField(max_length=255, blank=True, null=True)
    internal_comments_to_warehouse = models.TextField(blank=True, null=True)
    ship_to = models.TextField(blank=True, null=True)
    product_information = models.TextField(blank=True, null=True)
    dtr = models.CharField(max_length=10, blank=True, null=True)
    dtp = models.CharField(max_length=10, blank=True, null=True)
    original_request_date = models.DateField(blank=True, null=True)
    delivery = models.CharField(max_length=10, blank=True, null=True)
    actual_gi_date = models.DateField(blank=True, null=True)
    gi_status = models.CharField(max_length=1, blank=True, null=True)
    total_weight = models.FloatField(null=True, blank=True)
    price_per_unit = models.FloatField(null=True, blank=True)
    total_price = models.FloatField(null=True, blank=True)
    contract_material = models.ForeignKey(
        ContractMaterial, null=True, blank=True, on_delete=models.CASCADE
    )
    iplan = models.OneToOneField(OrderLineIPlan, on_delete=models.CASCADE, null=True)
    request_date_change_reason = models.CharField(max_length=255, null=True, blank=True)
    payment_condition = models.CharField(max_length=255, null=True, blank=True)
    po_no_external = models.CharField(max_length=255, null=True, blank=True)
    bill_to = models.CharField(max_length=255, blank=True, null=True)
    external_comments_to_customer = models.TextField(blank=True, null=True)
    internal_comments_to_logistic = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=250, default="Enable")
    original_order_line = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )
    original_quantity = models.FloatField(null=True, blank=True)
    production_status = models.CharField(
        max_length=255, null=True, blank=True
    )  # Production of item in i-plan
    atp_ctp_status = models.CharField(null=True, blank=True, max_length=255)
    i_plan_on_hand_stock = models.BooleanField(null=True, blank=True)
    i_plan_operations = models.JSONField(null=True, blank=True)
    inquiry_method = models.CharField(max_length=255, null=True, blank=True)
    item_status_en_rollback = models.CharField(
        null=True, blank=True, max_length=255
    )  # used to fix SEO-3783 case 3,4
    item_status_en = models.CharField(
        null=True, blank=True, max_length=255
    )  # Item status EN sync from IPlan and SAP
    item_status_th = models.CharField(
        null=True, blank=True, max_length=255
    )  # Item status TH sync from IPlan and SAP
    assigned_quantity = models.FloatField(null=True, blank=True)
    sap_confirm_status = models.CharField(null=True, blank=True, max_length=255)
    delivery_quantity = models.FloatField(null=True, blank=True)
    net_value = models.FloatField(null=True, blank=True)
    confirm_quantity = models.FloatField(null=True, blank=True)
    non_confirm_quantity = models.FloatField(null=True, blank=True)
    shipping_mark = models.TextField(null=True, blank=True)

    # field for add product to order feature. If user add but not save, it will be True
    draft = models.BooleanField(default=False)
    call_atp_ctp = models.BooleanField(blank=True, null=True, default=False)
    return_status = models.TextField(blank=True, null=True, default="")

    dtr_dtp_handled = models.BooleanField(blank=True, null=True, default=False)
    sap_confirm_qty = models.FloatField(null=True, blank=True)
    weight_display = models.CharField(null=True, blank=True, max_length=255)
    po_sub_contract = models.CharField(null=True, blank=True, max_length=255)
    po_status = models.CharField(null=True, blank=True, max_length=255)
    class_mark = models.TextField(null=True, blank=True)
    gross_weight_ton = models.FloatField(null=True, blank=True)
    net_weight_ton = models.FloatField(null=True, blank=True)
    weight_unit_ton = models.CharField(max_length=12, blank=True, null=True)
    pr_no = models.CharField(null=True, blank=True, max_length=255)
    pr_item = models.CharField(null=True, blank=True, max_length=255)
    price_date = models.DateField(null=True, blank=True)
    batch_no = models.CharField(null=True, blank=True, max_length=20)
    bom_flag = models.BooleanField(null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bom_parent",
    )
    batch_choice_flag = models.BooleanField(null=True, blank=True, default=False)
    sale_text1 = models.TextField(null=True, blank=True)
    sale_text2 = models.TextField(null=True, blank=True)
    sale_text3 = models.TextField(null=True, blank=True)
    sale_text4 = models.TextField(null=True, blank=True)
    item_note = models.TextField(null=True, blank=True)
    sales_qty_factor = models.TextField(null=True, blank=True)
    pr_item_text = models.TextField(null=True, blank=True)
    lot_no = models.TextField(null=True, blank=True)
    production_memo = models.TextField(null=True, blank=True)
    production_flag = models.CharField(null=True, blank=True, max_length=20)
    otc_ship_to = models.ForeignKey(
        OrderOtcPartner,
        on_delete=models.CASCADE,
        related_name="orderline_shipto",
        null=True,
    )
    force_flag = models.BooleanField(null=True, blank=True, default=False)


class Route(models.Model):
    route_code = models.CharField(null=True, blank=True, max_length=255)
    route_description = models.CharField(null=True, blank=True, max_length=255)


class OrderLineDeliveries(models.Model):
    order_line = models.ForeignKey(
        OrderLines, on_delete=models.CASCADE, null=True, blank=True
    )
    sales_order = models.CharField(max_length=10, null=True, blank=True)  # so_no
    sales_order_item = models.CharField(
        max_length=255, null=True, blank=True
    )  # item_no
    delivery = models.CharField(max_length=255, null=True, blank=True)
    actual_gi_date = models.DateField(blank=True, null=True)
    gi_status = models.CharField(max_length=255, null=True, blank=True)
    sales_org = models.CharField(max_length=255, null=True, blank=True)
    distribution_channel = models.CharField(max_length=255, null=True, blank=True)
    shipping_point = models.CharField(max_length=255, null=True, blank=True)


class OrderTextLang(models.Model):
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, null=True, blank=True
    )
    text_id = models.CharField(max_length=10, null=True, blank=True)
    item_no = models.CharField(max_length=100, null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = ("contract", "text_id", "item_no")


class SqsLog(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)


class OrderExtension(models.Model):
    order = models.OneToOneField(Order, primary_key=True, on_delete=models.CASCADE)
    bu = models.CharField(max_length=10, default="PP")
    tax_class = models.CharField(max_length=10, null=True)
    order_amt_before_vat = models.FloatField(null=True)
    order_amt_vat = models.FloatField(null=True)
    order_amt_after_vat = models.FloatField(null=True)
    currency = models.CharField(max_length=10, null=True)
    otc_sold_to = models.ForeignKey(
        OrderOtcPartner,
        on_delete=models.CASCADE,
        related_name="orderextension_soldto",
        null=True,
    )
    otc_bill_to = models.ForeignKey(
        OrderOtcPartner,
        on_delete=models.CASCADE,
        related_name="orderextension_billto",
        null=True,
    )
    otc_ship_to = models.ForeignKey(
        OrderOtcPartner,
        on_delete=models.CASCADE,
        related_name="orderextension_shipto",
        null=True,
    )
    additional_txt_from_header = models.TextField(null=True)
    additional_txt_header_note1 = models.TextField(null=True)
    additional_txt_cash = models.TextField(null=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="orderextension_created_by",
    )
    last_updated_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_updated_by = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="orderextension_updated_by",
    )
    temp_order_no = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = "sap_migration_orderextension"


class OrderLineCp(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    order_line = models.ForeignKey(
        OrderLines, on_delete=models.CASCADE, null=True, blank=True
    )
    item_no = models.CharField(max_length=10)
    material_code = models.CharField(max_length=50)
    confirm_date = models.DateField()
    plant = models.CharField(max_length=50)
    material_bom = models.CharField(max_length=500, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by_id = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="Orderlinecp_created_by",
    )
    last_updated_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_updated_by_id = models.ForeignKey(
        User,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="Orderlinecp_updated_by",
    )

    class Meta:
        db_table = "sap_migration_orderline_cp"
        unique_together = ("item_no", "order_id")


class CustomerMaterialMappingFileLog(models.Model):
    file_name = models.CharField(max_length=255, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_path = models.FileField(
        upload_to="customer_material_mapping_files",
        blank=True,
        storage=EOrderingS3Storage(),
    )
    uploaded_by = models.ForeignKey(
        User,
        related_name="customer_material_mapping_file_logs",
        on_delete=models.CASCADE,
        null=True,
    )
