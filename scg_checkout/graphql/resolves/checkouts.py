from saleor.account.models import User
from saleor.graphql.core.enums import OrderDirection
from sap_master_data.models import MaterialMaster
from sap_migration.models import (
    MaterialVariantMaster,
    CartLines,
    Cart,
    AlternateMaterialOs
)
from scg_checkout.models import (
    AlternatedMaterial,
)
from sap_migration import models as migration_models
from sap_master_data import models as master_models
from django.db.models import Count

from scgp_customer.graphql.resolvers.carts import get_cart_items_material_variant
from scgp_require_attention_items.graphql.enums import Direction


def resolve_contract_checkout(id, info):
    cart = migration_models.Cart.objects.filter(id=id, created_by=info.context.user, type="domestic").first()

    if not cart:
        return None

    material_variants = get_cart_items_material_variant(cart, info)
    info.variable_values.update({"material_variants_sap": material_variants})
    return cart


def resolve_contract_product_variant(id):
    cart_line = migration_models.CartLines.objects.filter(cart_id=id)
    return resolve_products(list(map(lambda x: x.material.material_code, cart_line)))


def resolve_contract_product(id):
    cart_line = migration_models.CartLines.objects.filter(cart_id=id).order_by("contract_material_id").distinct(
        "contract_material_id")
    contract_material_ids = list(map(lambda x: x.contract_material.contract_id, cart_line))
    return migration_models.ContractMaterial.objects.filter(contract_id__in=contract_material_ids)


def resolve_contract_checkouts(user):
    return migration_models.Cart.objects.annotate(quantity_cart_lines=Count('cartlines')) \
        .filter(created_by=user, quantity_cart_lines__gt=0, type="domestic")


def resolve_product_variant(id):
    return MaterialVariantMaster.objects.filter(id=id).first()


def resolve_checkout_lines(id, sort_by):
    if sort_by is None:
        return CartLines.objects.filter(cart_id=id)

    return CartLines.objects.filter(cart_id=id).order_by(
        *["{}{}".format(sort_by["direction"], field) for field in sort_by["field"]]
    )


def resolve_total_customers(user):
    return Cart.objects.filter(created_by=user, type="domestic").distinct("sold_to_id").count()


def resolve_total_products(user):
    return CartLines.objects.filter(cart__created_by=user, cart__type="domestic").count()


def resolve_product(id):
    return MaterialMaster.objects.filter(id=id).first()


def resolve_checkout_lines_selected(checkout_id):
    result = migration_models.CartLines.objects.filter(cart_id=checkout_id, selected=True)
    return result


def resolve_quantity(checkout_id):
    result = CartLines.objects.filter(cart_id=checkout_id).count()

    return result


def resolve_products(qs):
    return master_models.MaterialMaster.objects.filter(material_code__in=qs)


def resolve_alternative_materials_os(kwargs):
    result = migration_models.AlternateMaterialOs.objects.all()
    prepare_alt_mat_sort_by_fields(kwargs)
    return result


def prepare_alt_mat_sort_by_fields(kwargs):
    ordering = [
        "alternate_material__sales_organization__code",
        "alternate_material__sold_to__sold_to_code",
        "alternate_material__material_own__material_code",
        "priority",
    ]
    alt_mat_os_meta = AlternateMaterialOs._meta
    alt_mat_os_meta.ordering = ordering
    if kwargs and kwargs.get('sort_by'):
        sort_fields = kwargs.get('sort_by').field
        direction = kwargs.get('sort_by').direction
        if sort_fields:
            sort_fields.extend(alt_mat_os_meta.ordering)
            if OrderDirection.DESC.value == direction:
                sort_fields = [direction + item for item in sort_fields]
            alt_mat_os_meta.ordering = sort_fields
            kwargs.pop('sort_by')


def resolve_alternated_material():
    return AlternatedMaterial.objects.all()


def resolve_suggestion_search_user_by_name():
    return User.objects.all()


def resolve_order_unit(root, info):
    material_code = root.material_code
    material_purchase = master_models.MaterialPurchaseMaster.objects.filter(material_code=material_code).first()
    if material_purchase:
        purchase_unit = material_purchase.order_unit

        return purchase_unit
    return None


def resolve_purchase_unit(root, info):
    material_code = root.material_code
    material_sale = master_models.MaterialSaleMaster.objects.filter(material_code=material_code).first()
    if material_sale:
        sales_unit = material_sale.sales_unit

        return sales_unit
    return None


def resolve_product_cart_items(user, sold_to_code, contract_code):
    cart_lines = migration_models.CartLines.objects.filter(
        cart__sold_to__sold_to_code=sold_to_code,
        contract_material__contract__code=contract_code,
        cart__created_by=user
    )
    return cart_lines


def resolve_sold_to_partner_address_masters_have_partner_code():
    return master_models.SoldToPartnerAddressMaster.objects.exclude(partner_code__isnull=True).exclude(
        partner_code__exact='')
