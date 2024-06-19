from django.db import models

from saleor.account.models import Company, Division, User
from saleor.product.models import ProductVariant


class Contract(models.Model):
    bu = models.ForeignKey(Division, blank=False, null=False, on_delete=models.CASCADE)
    company = models.ForeignKey(
        Company, blank=False, null=False, on_delete=models.CASCADE
    )
    customer = models.ForeignKey(
        User, blank=False, null=False, on_delete=models.CASCADE
    )
    project_name = models.CharField(max_length=255, blank=False, null=False)
    start_date = models.DateField(blank=False, null=False)
    end_date = models.DateField(blank=False, null=False)
    payment_term = models.CharField(max_length=255, blank=False, null=False)
    product_variants = models.ManyToManyField(ProductVariant, related_name="contracts")


class Material(models.Model):
    name = models.CharField(max_length=250)
    unit = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)


class ProductVariantMaterial(models.Model):
    product_variant = models.ForeignKey(
        ProductVariant, blank=False, null=False, on_delete=models.CASCADE
    )
    material = models.ForeignKey(
        Material, blank=False, null=False, on_delete=models.CASCADE
    )
    value = models.FloatField(blank=True, null=True)
