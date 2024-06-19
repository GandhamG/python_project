from django.core.validators import MinValueValidator
from django.db import models

from saleor.account.models import User
from scgp_export.graphql.enums import ScgpExportOrderStatus


class ScgpMaterialGroup(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)


class ScgpSalesEmployee(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)


class BusinessUnit(models.Model):
    name = models.CharField(max_length=255, null=False, blank=False)


class Company(models.Model):
    name = models.CharField(max_length=255, blank=False, null=False)
    users = models.ManyToManyField(User, related_name="companies")
    business_unit = models.ForeignKey(
        BusinessUnit, blank=False, null=True, on_delete=models.CASCADE
    )


class SalesOrganization(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    business_unit = models.ForeignKey(
        BusinessUnit, null=True, on_delete=models.CASCADE, related_name="business_units"
    )


class ScgSoldTo(models.Model):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255, blank=True, null=True)
    address_text = models.TextField(null=True, blank=True)
    representatives = models.ManyToManyField(User, blank=True, related_name="sold_to")
    sale_organization = models.ForeignKey(
        SalesOrganization, blank=True, null=True, on_delete=models.CASCADE
    )


class DistributionChannel(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)


class Division(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)


class SalesOffice(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)


class SalesGroup(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    sales_organization = models.ForeignKey(
        SalesOrganization,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="sales_organization",
    )


class Product(models.Model):
    name = models.CharField(max_length=255, blank=False, null=False)
    sales_unit = models.CharField(max_length=255, blank=False, null=False)
    code = models.CharField(max_length=255, blank=True, null=True)
    material_group = models.ForeignKey(
        ScgpMaterialGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    grade = models.CharField(max_length=3, null=True, blank=True)
    gram = models.CharField(max_length=3, null=True, blank=True)
    type = models.CharField(max_length=255, blank=True, null=True, default="domestic")
    dia = models.TextField(null=True, blank=True)
    grade_gram = models.CharField(max_length=15, null=True, blank=True)


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, blank=False, null=False, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, null=False, blank=False)
    weight = models.FloatField(null=True, blank=True)


class Contract(models.Model):
    company = models.ForeignKey(
        Company, blank=False, null=False, on_delete=models.CASCADE
    )
    customer = models.ForeignKey(
        User,
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name="tmp_contract",
    )
    project_name = models.CharField(max_length=255, blank=False, null=False)
    start_date = models.DateField(blank=False, null=False)
    end_date = models.DateField(blank=False, null=False)
    payment_term = models.CharField(max_length=255, blank=False, null=False)


class ContractProduct(models.Model):
    contract = models.ForeignKey(
        Contract, blank=False, null=False, on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, blank=False, null=False, on_delete=models.CASCADE
    )
    total = models.FloatField()
    remain = models.FloatField()
    price = models.FloatField()
    plant = models.CharField(max_length=255, blank=True, null=True)
    delivery_under = models.FloatField(blank=True, null=True)
    delivery_over = models.FloatField(blank=True, null=True)


class TempCheckout(models.Model):
    user = models.ForeignKey(User, blank=False, null=False, on_delete=models.CASCADE)
    contract = models.ForeignKey(
        Contract, blank=False, null=False, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.SET_NULL, related_name="carts"
    )
    last_change = models.DateTimeField(auto_now=True)


class TempOrder(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    po_date = models.DateField(null=True, blank=True)
    po_number = models.TextField(null=True, blank=True)
    ship_to = models.TextField(null=True, blank=True)
    bill_to = models.TextField(null=True, blank=True)
    order_type = models.TextField(null=True, blank=True)
    request_date = models.DateField(null=True, blank=True)
    internal_comments_to_warehouse = models.CharField(
        max_length=250, blank=True, null=True
    )
    internal_comments_to_logistic = models.CharField(
        max_length=250, blank=True, null=True
    )
    external_comments_to_customer = models.CharField(
        max_length=250, blank=True, null=True
    )
    product_information = models.CharField(max_length=250, blank=True, null=True)
    sale_organization = models.ForeignKey(
        SalesOrganization, blank=True, null=True, on_delete=models.CASCADE
    )
    distribution_channel = models.ForeignKey(
        DistributionChannel, blank=True, null=True, on_delete=models.CASCADE
    )
    division = models.ForeignKey(
        Division, blank=True, null=True, on_delete=models.CASCADE
    )
    sale_office = models.ForeignKey(
        SalesOffice, blank=True, null=True, on_delete=models.CASCADE
    )
    sale_group = models.ForeignKey(
        SalesGroup, blank=True, null=True, on_delete=models.CASCADE
    )
    total_price = models.FloatField(null=True, blank=True)
    status = models.CharField(default=ScgpExportOrderStatus.DRAFT.value, max_length=255)
    order_no = models.CharField(max_length=255, null=True, blank=True)
    sold_to = models.ForeignKey(
        ScgSoldTo,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="scg_sold_to",
    )
    scgp_sales_employee = models.ForeignKey(
        ScgpSalesEmployee,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="created_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    update_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="update_by"
    )
    so_no = models.CharField(max_length=10, null=True, blank=True)


class TempCheckoutLine(models.Model):
    checkout = models.ForeignKey(
        TempCheckout, blank=False, null=False, on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, blank=False, null=False, on_delete=models.CASCADE
    )
    contract_product = models.ForeignKey(
        ContractProduct, blank=True, null=True, on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        ProductVariant, blank=False, null=False, on_delete=models.CASCADE
    )
    quantity = models.FloatField(null=False, default=0)
    price = models.FloatField(blank=True, null=True)
    selected = models.BooleanField(default=False)


class TempOrderLine(models.Model):
    order = models.ForeignKey(
        TempOrder, blank=True, null=True, on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, blank=True, null=True, on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        ProductVariant, blank=True, null=True, on_delete=models.CASCADE
    )
    contract_product = models.ForeignKey(
        ContractProduct, blank=True, null=True, on_delete=models.CASCADE
    )
    plant = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.FloatField(null=False, default=0)
    net_price = models.FloatField(blank=True, null=True)
    request_date = models.DateField(blank=True, null=True)
    internal_comments_to_warehouse = models.CharField(
        max_length=250, blank=True, null=True
    )
    ship_to = models.TextField(blank=True, null=True)
    product_information = models.CharField(max_length=250, blank=True, null=True)
    checkout_line = models.ForeignKey(
        TempCheckoutLine, blank=True, null=True, on_delete=models.SET_NULL
    )
    confirmed_date = models.DateField(blank=True, null=True)
    item_no = models.FloatField(null=True, blank=True)
    type = models.CharField(max_length=255, blank=True, null=True, default="domestic")
    overdue_1 = models.BooleanField(blank=True, null=True, default=False)
    overdue_2 = models.BooleanField(blank=True, null=True, default=False)
    flag = models.CharField(max_length=255, blank=True, default="Customer", null=True)
    remark = models.TextField(null=True, blank=True)
    attention_type = models.CharField(max_length=255, blank=True, null=True)
    models.TextField(null=True, blank=True)
    dtr = models.CharField(max_length=10, blank=True, null=True)
    dtp = models.CharField(max_length=10, blank=True, null=True)
    original_request_date = models.DateField(blank=True, null=True)
    delivery = models.CharField(max_length=10, blank=True, null=True)
    actual_gi_date = models.DateField(blank=True, null=True)
    gi_status = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        ordering = ("id",)


class AlternativeMaterial(models.Model):
    sales_organization = models.ForeignKey(
        SalesOrganization, blank=False, null=True, on_delete=models.CASCADE
    )
    sold_to = models.ForeignKey(
        "sap_master_data.SoldToMaster", blank=False, null=True, on_delete=models.CASCADE
    )
    material_own = models.ForeignKey(
        "sap_master_data.MaterialMaster",
        blank=False,
        null=True,
        on_delete=models.CASCADE,
        related_name="alternative_material_own",
    )
    type = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="alternative_material_created_by",
    )
    updated_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="alternative_material_updated_by",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ("id",)
        unique_together = (
            "sales_organization",
            "sold_to",
            "material_own",
        )


class AlternativeMaterialOs(models.Model):
    alternative_material = models.ForeignKey(
        AlternativeMaterial,
        blank=False,
        null=False,
        on_delete=models.CASCADE,
    )
    material_os = models.ForeignKey(
        "sap_master_data.MaterialMaster",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    priority = models.IntegerField(validators=[MinValueValidator(1)], null=True)

    class Meta:
        ordering = [
            "alternative_material__sales_organization__code",
            "alternative_material__sold_to__sold_to_code",
            "alternative_material__sold_to__sold_to_name",
        ]


class AlternatedMaterial(models.Model):
    order = models.ForeignKey(
        "sap_migration.Order",
        null=True,
        blank=True,
        related_name="alternated_material_order",
        on_delete=models.SET_NULL,
    )
    order_line = models.ForeignKey(
        "sap_migration.OrderLines",
        null=True,
        blank=True,
        related_name="alternated_material",
        on_delete=models.SET_NULL,
    )
    old_product = models.ForeignKey(
        "sap_migration.MaterialVariantMaster",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="material_own",
    )
    new_product = models.ForeignKey(
        "sap_migration.MaterialVariantMaster",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="material_os",
    )
    error_type = models.CharField(max_length=255, null=True, blank=True)
    quantity_change_of_roll = models.FloatField(null=True, blank=True)
    quantity_change_of_ton = models.FloatField(null=True, blank=True)


class ScgOrderView(models.Model):
    unique_id = models.CharField(primary_key=True, max_length=255)
    id = models.IntegerField()
    contract_pi_no = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255)
    sold_to = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    type = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "scg_union_orders"


class AlternativeMaterialLastUpdateBy(models.Model):
    updated_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="alternative_material_last_updated_by",
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
