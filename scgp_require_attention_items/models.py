from django.db import models

from scg_checkout.models import (
    SalesGroup,
    SalesOrganization,
    ScgpMaterialGroup,
    ScgpSalesEmployee,
)
from scgp_require_attention_items.graphql.enums import (
    ScgpRequireAttentionConsignment,
    ScgpRequireAttentionSplitOrderItemPartialDelivery,
    ScgpRequireAttentionTypeOfDelivery,
)
from utils.enums import IPlanInquiryMethodCode


class RequireAttentionItems(models.Model):
    unique_id = models.CharField(max_length=255, primary_key=True)
    order_line_id = models.IntegerField()
    type = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "scgp_require_attention_items"


class RequireAttention(models.Model):
    items = models.OneToOneField(
        RequireAttentionItems, primary_key=True, on_delete=models.CASCADE
    )
    iplant_confirm_quantity = models.FloatField(null=True, blank=True)
    item_status = models.CharField(
        default=None,
        max_length=255,
        null=True,
        blank=True,
    )
    original_date = models.DateField(blank=True, null=True)
    inquiry_method_code = models.CharField(
        default=IPlanInquiryMethodCode.JITCP.value,
        max_length=255,
        null=True,
        blank=True,
    )
    transportation_method = models.IntegerField(null=True, blank=True)
    type_of_delivery = models.CharField(
        default=ScgpRequireAttentionTypeOfDelivery.ARRIVAL.value,
        max_length=255,
        null=True,
        blank=True,
    )
    fix_source_assignment = models.CharField(max_length=255, null=True, blank=True)
    split_order_item = models.CharField(
        default=ScgpRequireAttentionSplitOrderItemPartialDelivery.YES.value,
        max_length=255,
        null=True,
        blank=True,
    )
    partial_delivery = models.CharField(
        default=ScgpRequireAttentionSplitOrderItemPartialDelivery.YES.value,
        max_length=255,
        null=True,
        blank=True,
    )
    consignment = models.CharField(
        default=ScgpRequireAttentionConsignment.FREE_STOCK_1000.value,
        max_length=255,
        null=True,
        blank=True,
    )


class RequireAttentionItemView(models.Model):
    unique_id = models.CharField(max_length=255, primary_key=True)
    order_line_id = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    items_id = models.CharField(max_length=255, null=True, blank=True)
    order_no = models.CharField(max_length=255, null=True, blank=True)
    item_no = models.FloatField()
    ship_to = models.CharField(max_length=255, null=True, blank=True)
    sold_to = models.CharField(max_length=255, null=True, blank=True)
    request_date = models.DateField(null=True, blank=True)
    confirmed_date = models.DateField(null=True, blank=True)
    po_no = models.CharField(max_length=255, null=True, blank=True)
    plant = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    material = models.CharField(max_length=500, null=True, blank=True)
    mat_code = models.CharField(max_length=255, null=True, blank=True)
    mat_description = models.CharField(max_length=255, null=True, blank=True)
    request_quantity = models.FloatField(max_length=255, null=True, blank=True)
    material_group = models.ForeignKey(
        ScgpMaterialGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    grade = models.CharField(max_length=255, null=True, blank=True)
    gram = models.CharField(max_length=255, null=True, blank=True)
    sales_organization = models.ForeignKey(
        SalesOrganization, null=True, blank=True, on_delete=models.CASCADE
    )
    sales_group = models.ForeignKey(
        SalesGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    scgp_sales_employee = models.ForeignKey(
        ScgpSalesEmployee, null=True, blank=True, on_delete=models.CASCADE
    )
    attention_type = models.CharField(max_length=255, blank=True, null=True)
    iplant_confirm_quantity = models.FloatField(null=True, blank=True)
    item_status = models.CharField(
        default=None,
        max_length=255,
        null=True,
        blank=True,
    )
    original_date = models.DateField(blank=True, null=True)
    overdue_1 = models.BooleanField(null=True, blank=True)
    overdue_2 = models.BooleanField(null=True, blank=True)
    inquiry_method_code = models.CharField(
        default=IPlanInquiryMethodCode.JITCP.value,
        max_length=255,
        null=True,
        blank=True,
    )
    transportation_method = models.IntegerField(null=True, blank=True)
    type_of_delivery = models.CharField(
        default=ScgpRequireAttentionTypeOfDelivery.ARRIVAL.value,
        max_length=255,
        null=True,
        blank=True,
    )
    fix_source_assignment = models.CharField(max_length=255, null=True, blank=True)
    split_order_item = models.CharField(
        default=ScgpRequireAttentionSplitOrderItemPartialDelivery.YES.value,
        max_length=255,
        null=True,
        blank=True,
    )
    partial_delivery = models.CharField(
        default=ScgpRequireAttentionSplitOrderItemPartialDelivery.YES.value,
        max_length=255,
        null=True,
        blank=True,
    )
    consignment = models.CharField(
        default=ScgpRequireAttentionConsignment.FREE_STOCK_1000.value,
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "scgp_require_attention_items_extend_view"


class RequireAttentionMaterial(models.Model):
    unique_id = models.CharField(primary_key=True, max_length=255)
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    grade = models.CharField(max_length=255, null=True, blank=True)
    gram = models.CharField(max_length=255, null=True, blank=True)
    material_group = models.ForeignKey(
        ScgpMaterialGroup, null=True, blank=True, on_delete=models.CASCADE
    )

    class Meta:
        managed = False
        db_table = "scgp_require_attention_material"


class RequireAttentionSoldTo(models.Model):
    unique_id = models.CharField(max_length=255, primary_key=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "scgp_require_attention_sold_to"


class RequireAttentionIPlan(models.Model):
    items = models.OneToOneField(
        RequireAttentionItems, primary_key=True, on_delete=models.CASCADE
    )
    atp_ctp = models.CharField(max_length=255, null=True, blank=True)
    atp_ctp_detail = models.CharField(max_length=255, null=True, blank=True)
    block = models.CharField(max_length=255, null=True, blank=True)
    run = models.CharField(max_length=255, null=True, blank=True)


class JobInformation(models.Model):
    unique_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    job_type = models.CharField(max_length=255, null=True, blank=True)
    time = models.DateField(blank=True, null=True)
    is_locked = models.BooleanField(default=False)
