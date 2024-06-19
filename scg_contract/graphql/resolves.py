from django.db.models import Sum

from saleor.order.models import Order, OrderLine
from saleor.product.models import Product, ProductVariant
from saleor.warehouse import models as warehouse_models
from scg_contract import models as contract_models
from scg_contract.models import Material, ProductVariantMaterial


def resolve_customer_contracts(info, id):
    return contract_models.Contract.objects.filter(customer_id=id)


def resolve_customer_contract(info, id):
    return contract_models.Contract.objects.filter(id=id).first()


def resolve_business_units(id):
    return contract_models.Division.objects.filter(id=id)


def resolve_material(id):
    return contract_models.Material.objects.filter(id=id).first()


def resolve_materials():
    return contract_models.Material.objects.all()


def resolve_materials_by_product(product_id):
    product_variants = ProductVariant.objects.filter(product_id=product_id)
    variant_ids = []
    for item in product_variants:
        variant_ids.append(item.id)
    return contract_models.ProductVariantMaterial.objects.filter(
        product_variant_id__in=variant_ids
    )


def resolve_material_by_id(id):
    return contract_models.Material.objects.filter(pk=id).first()


def resolve_product_name(id):
    name = ""
    productVariant = ProductVariant.objects.filter(pk=id).first()
    if productVariant is not None:
        product = Product.objects.filter(pk=productVariant.product_id).first()
        if Product is not None:
            name = product.name
    return name


def resolve_product_variant(id):
    return ProductVariant.objects.filter(pk=id).first()


def resolve_orders_by_customer_id(id):
    return Order.objects.filter(user_id=id)


def resolve_order_line_by_order_id(id):
    return OrderLine.objects.filter(order_id=id)


def resolve_materials_by_product_variant(id):
    materia_ids = ProductVariantMaterial.objects.filter(
        product_variant_id=id
    ).values_list("material_id", flat=True)
    return Material.objects.filter(pk__in=list(materia_ids))


def resolve_total_stock(product_variant_id):
    total_stock = warehouse_models.Stock.objects.filter(
        product_variant_id=product_variant_id
    ).aggregate(Sum("quantity"))
    return total_stock["quantity__sum"]
