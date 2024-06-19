from django.db import models

from saleor.account.models import User
from saleor.order import OrderStatus


class SoldTo(models.Model):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255, blank=True, null=True)
    representatives = models.ManyToManyField(User, blank=True, related_name="sold_tos")


class CustomerContract(models.Model):
    sold_to = models.ForeignKey(SoldTo, on_delete=models.CASCADE)
    company = models.ForeignKey("scg_checkout.Company", on_delete=models.CASCADE)
    code = models.CharField(max_length=50)
    project_name = models.CharField(max_length=128, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    payment_term = models.CharField(max_length=255, blank=False, null=False)


class CustomerProduct(models.Model):
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)


class CustomerProductVariant(models.Model):
    product = models.ForeignKey(CustomerProduct, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)


class CustomerContractProduct(models.Model):
    contract = models.ForeignKey(CustomerContract, on_delete=models.CASCADE)
    product = models.ForeignKey(CustomerProduct, on_delete=models.CASCADE)
    total_quantity = models.FloatField()
    remaining_quantity = models.FloatField()
    price_per_unit = models.FloatField()
    quantity_unit = models.CharField(max_length=12, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, null=True)
    weight = models.FloatField()
    weight_unit = models.CharField(max_length=12, null=True, blank=True)


class CustomerOrder(models.Model):
    contract = models.ForeignKey(
        CustomerContract, blank=True, null=True, on_delete=models.SET_NULL
    )
    total_price = models.FloatField(null=True, blank=True)
    total_price_inc_tax = models.FloatField(null=True, blank=True)
    tax_amount = models.FloatField(null=True, blank=True)
    status = models.CharField(default=OrderStatus.DRAFT, max_length=255)
    # Header
    order_date = models.DateField(blank=True, null=True)
    order_no = models.CharField(max_length=50, blank=True, null=True)
    request_delivery_date = models.DateField(blank=True, null=True)
    ship_to = models.CharField(max_length=255, blank=True, null=True)
    bill_to = models.CharField(max_length=255, blank=True, null=True)
    unloading_point = models.CharField(max_length=255, blank=True, null=True)
    remark_for_invoice = models.TextField(null=True, blank=True)
    remark_for_logistic = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, default=None, null=True, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    internal_comments_to_warehouse = models.TextField(null=True, blank=True)


class CustomerCart(models.Model):
    contract = models.ForeignKey(CustomerContract, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("contract", "created_by")


class CustomerCartItem(models.Model):
    cart = models.ForeignKey(CustomerCart, on_delete=models.CASCADE)
    contract_product = models.ForeignKey(
        CustomerContractProduct, on_delete=models.CASCADE, default=None
    )
    variant = models.ForeignKey(
        CustomerProductVariant, on_delete=models.CASCADE, default=None
    )
    quantity = models.IntegerField(default=0)


class CustomerOrderLine(models.Model):
    order = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE)
    contract_product = models.ForeignKey(
        CustomerContractProduct, on_delete=models.CASCADE, default=None
    )
    variant = models.ForeignKey(
        CustomerProductVariant, on_delete=models.CASCADE, default=None
    )
    quantity = models.FloatField(null=True, blank=True)
    quantity_unit = models.CharField(max_length=12, blank=True, null=True)
    weight_per_unit = models.FloatField(null=True, blank=True)
    total_weight = models.FloatField(null=True, blank=True)
    price_per_unit = models.FloatField(null=True, blank=True)
    total_price = models.FloatField(null=True, blank=True)
    request_delivery_date = models.DateField(blank=True, null=True)
    cart_item = models.ForeignKey(
        CustomerCartItem, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        ordering = ("id",)
