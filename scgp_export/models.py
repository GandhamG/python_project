from django.db import models

from saleor.account.models import User
from scg_checkout.models import ScgpMaterialGroup, ScgpSalesEmployee
from scgp_export.graphql.enums import ScgpExportOrderStatus, ScgpExportOrderStatusSAP


class ExportSoldTo(models.Model):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255, blank=True, null=True)
    address_text = models.TextField(null=True, blank=True)


class ExportPI(models.Model):
    sold_to = models.ForeignKey(
        ExportSoldTo, blank=True, null=True, on_delete=models.SET_NULL
    )
    code = models.CharField(max_length=50)
    po_no = models.CharField(max_length=50, blank=True, null=True)
    sold_to_name = models.CharField(max_length=128, blank=True, null=True)
    ship_to_name = models.CharField(max_length=128, blank=True, null=True)
    ship_to_country = models.CharField(max_length=128, blank=True, null=True)
    incoterm = models.CharField(max_length=10, blank=True, null=True)
    payment_term = models.CharField(max_length=10, blank=True, null=True)


class ExportProduct(models.Model):
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    material_group = models.ForeignKey(
        ScgpMaterialGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    grade = models.CharField(max_length=3, null=True, blank=True)
    gram = models.CharField(max_length=3, null=True, blank=True)
    type = models.CharField(max_length=255, blank=True, null=True, default="export")
    material_code = models.CharField(max_length=255, blank=True, null=True)
    grade_gram = models.CharField(max_length=255, blank=True, null=True)


class ExportPIProduct(models.Model):
    pi = models.ForeignKey(ExportPI, on_delete=models.CASCADE)
    product = models.ForeignKey(ExportProduct, on_delete=models.CASCADE)
    total_quantity = models.FloatField()
    remaining_quantity = models.FloatField()
    price_per_unit = models.FloatField()
    quantity_unit = models.CharField(max_length=12, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, null=True)
    weight = models.FloatField()
    weight_unit = models.CharField(max_length=12, null=True, blank=True)


class ExportOrder(models.Model):
    pi = models.ForeignKey(ExportPI, blank=True, null=True, on_delete=models.SET_NULL)
    total_price = models.FloatField(null=True, blank=True)
    tax_amount = models.FloatField(null=True, blank=True)
    status = models.CharField(default=ScgpExportOrderStatus.DRAFT.value, max_length=255)
    status_sap = models.CharField(
        default=ScgpExportOrderStatusSAP.BEING_PROCESS.value, max_length=255
    )
    # Agency
    request_delivery_date = models.DateField(blank=True, null=True)
    order_type = models.CharField(max_length=50, blank=True, null=True)
    sales_organization = models.ForeignKey(
        "scg_checkout.SalesOrganization",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="sales_organizations",
    )
    distribution_channel = models.ForeignKey(
        "scg_checkout.DistributionChannel",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    division = models.ForeignKey(
        "scg_checkout.Division", blank=True, null=True, on_delete=models.CASCADE
    )
    sales_office = models.ForeignKey(
        "scg_checkout.SalesOffice", blank=True, null=True, on_delete=models.CASCADE
    )
    sales_group = models.ForeignKey(
        "scg_checkout.SalesGroup", blank=True, null=True, on_delete=models.CASCADE
    )
    # Header
    ship_to = models.CharField(max_length=255, blank=True, null=True)
    bill_to = models.CharField(max_length=255, blank=True, null=True)
    po_date = models.DateField(blank=True, null=True)
    po_no = models.CharField(max_length=255, blank=True, null=True)
    request_date = models.DateField(blank=True, null=True)
    ref_pi_no = models.CharField(max_length=255, blank=True, null=True)
    net_price = models.CharField(max_length=50, blank=True, null=True)
    doc_currency = models.CharField(max_length=3, blank=True, null=True)
    payment_term = models.CharField(max_length=255, blank=True, null=True)
    incoterm = models.CharField(max_length=10, blank=True, null=True)
    usage = models.CharField(max_length=255, blank=True, null=True)
    unloading_point = models.CharField(max_length=255, blank=True, null=True)
    place_of_delivery = models.CharField(max_length=255, blank=True, null=True)
    port_of_discharge = models.CharField(max_length=255, blank=True, null=True)
    port_of_loading = models.CharField(max_length=255, blank=True, null=True)
    no_of_containers = models.CharField(max_length=255, blank=True, null=True)
    shipping_mark = models.TextField(null=True, blank=True)
    uom = models.CharField(max_length=255, blank=True, null=True)
    gw_uom = models.CharField(max_length=255, blank=True, null=True)
    etd = models.CharField(max_length=255, blank=True, null=True)
    eta = models.CharField(max_length=255, blank=True, null=True)
    dlc_expiry_date = models.DateField(blank=True, null=True)
    dlc_no = models.CharField(max_length=255, blank=True, null=True)
    dlc_latest_delivery_date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    payer = models.CharField(max_length=10, blank=True, null=True)
    end_customer = models.CharField(max_length=128, blank=True, null=True)
    contact_person = models.CharField(max_length=128, blank=True, null=True)
    sales_employee = models.CharField(max_length=128, blank=True, null=True)
    author = models.CharField(max_length=128, blank=True, null=True)
    payment_instruction = models.TextField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    production_information = models.TextField(null=True, blank=True)
    internal_comment_to_warehouse = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    eo_no = models.CharField(max_length=10, blank=True, null=True)
    order_no = models.CharField(max_length=255, blank=True, null=True)
    scgp_sales_employee = models.ForeignKey(
        ScgpSalesEmployee,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    etd_date = models.DateField(blank=True, null=True)
    pi_type = models.CharField(max_length=255, blank=True, null=True)
    change_type = models.CharField(max_length=255, blank=True, null=True)
    lot_no = models.CharField(max_length=255, blank=True, null=True)
    sales_email = models.CharField(max_length=255, blank=True, null=True)
    cc = models.CharField(max_length=255, blank=True, null=True)
    contract_type = models.CharField(max_length=255, blank=True, null=True)


class ExportCart(models.Model):
    pi = models.ForeignKey(ExportPI, on_delete=models.CASCADE)
    sold_to = models.ForeignKey(ExportSoldTo, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("pi", "created_by", "sold_to")


class ExportCartItem(models.Model):
    cart = models.ForeignKey(ExportCart, on_delete=models.CASCADE)
    pi_product = models.ForeignKey(ExportPIProduct, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)


class ExportOrderLine(models.Model):
    order = models.ForeignKey(ExportOrder, on_delete=models.CASCADE)
    pi_product = models.ForeignKey(ExportPIProduct, on_delete=models.CASCADE)
    quantity = models.FloatField()
    quantity_unit = models.CharField(max_length=12, blank=True, null=True)
    weight = models.FloatField()
    weight_unit = models.CharField(max_length=12, blank=True, null=True)
    net_price = models.FloatField(blank=True, null=True)
    vat_percent = models.FloatField()
    item_cat_eo = models.CharField(max_length=12, blank=True, null=True)
    reject_reason = models.CharField(max_length=12, blank=True, null=True)
    ref_pi_no = models.CharField(max_length=255, blank=True, null=True)
    material_code = models.CharField(max_length=50, blank=True, null=True)
    condition_group1 = models.CharField(max_length=50, blank=True, null=True)
    material_group2 = models.CharField(max_length=50, blank=True, null=True)
    commission_percent = models.FloatField()
    commission_amount = models.FloatField()
    commission_unit = models.CharField(max_length=3, blank=True, null=True)
    request_date = models.DateField(blank=True, null=True)
    plant = models.CharField(max_length=10, blank=True, null=True)
    route = models.CharField(max_length=50, blank=True, null=True)
    roll_quantity = models.CharField(max_length=255, blank=True, null=True)
    roll_diameter = models.CharField(max_length=255, blank=True, null=True)
    roll_core_diameter = models.CharField(max_length=255, blank=True, null=True)
    roll_per_pallet = models.CharField(max_length=255, blank=True, null=True)
    package_quantity = models.CharField(max_length=255, blank=True, null=True)
    pallet_size = models.CharField(max_length=12, blank=True, null=True)
    pallet_no = models.CharField(max_length=12, blank=True, null=True)
    packing_list = models.CharField(max_length=128, blank=True, null=True)
    shipping_point = models.CharField(max_length=128, blank=True, null=True)
    delivery_tol_under = models.FloatField(blank=True, null=True)
    delivery_tol_over = models.FloatField(blank=True, null=True)
    delivery_tol_unlimited = models.BooleanField(default=False)
    remark = models.TextField(null=True, blank=True)
    cart_item = models.ForeignKey(ExportCartItem, on_delete=models.SET_NULL, null=True)
    item_no = models.FloatField(null=True, blank=True)
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

    class Meta:
        ordering = ("id",)
        unique_together = (("order", "pi_product"),)


class EOUploadSendMailSummaryLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=500, blank=True, null=True)
