from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from sap_migration import models as sap_migration_models
from scg_checkout.graphql.resolves.product_variant import resolve_limit_quantity


@transaction.atomic
def customer_create_cart(params, created_by):
    try:
        customer_contract_id = params["customer_contract_id"]
        cart_items_info = params["lines"]
        sold_to_id = params["sold_to_id"]
        customer_cart = sap_migration_models.Cart.objects.filter(
            created_by=created_by,
            contract_id=customer_contract_id,
            sold_to_id=sold_to_id,
        ).first()
        if not customer_cart:
            customer_cart = sap_migration_models.Cart.objects.create(
                contract_id=customer_contract_id,
                created_by=created_by,
                sold_to_id=sold_to_id,
                type="customer",
            )
        create_or_update_customer_cart_items(
            cart_items_info, customer_cart.id, customer_contract_id
        )
        return customer_cart
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def create_or_update_customer_cart_items(
    cart_items_info, customer_cart_id, customer_contract_id
):
    customer_contract_products = sap_migration_models.ContractMaterial.objects.filter(
        contract_id=customer_contract_id
    )
    contract_products_objects = {}
    for customer_contract_product in customer_contract_products:
        contract_products_objects[
            str(customer_contract_product.material_id)
        ] = customer_contract_product
    cart_items_create = []
    cart_items_update = []
    cart_item_objects = get_cart_item_objects(customer_cart_id)
    for item_info in cart_items_info:
        mat_id = item_info["product_id"]
        variant_id = item_info.get("variant_id")
        contract_material_id = item_info.get("contract_material_id")
        if not variant_id:
            variant_id = (
                sap_migration_models.MaterialVariantMaster.objects.filter(
                    material_id=mat_id
                )
                .values_list("id", flat=True)
                .first()
            )
        variant = sap_migration_models.MaterialVariantMaster.objects.get(pk=variant_id)
        limit_qty = resolve_limit_quantity(
            customer_contract_id,
            mat_id,
            variant.code,
            contract_mat_id=contract_material_id,
        )
        if float(item_info["quantity"]) > limit_qty:
            raise ValueError("Quantity can not over remaining")
        customer_contract_product_id = (
            contract_material_id
            if contract_material_id
            else contract_products_objects[mat_id].id
        )
        cart_item_object = cart_item_objects.get(
            concat_variant_id_and_contract_product_id(
                [variant_id, customer_contract_product_id]
            ),
            None,
        )
        if cart_item_object:
            quantity = float(cart_item_object.get("quantity")) + float(
                item_info["quantity"]
            )
            item = sap_migration_models.CartLines(
                id=cart_item_object.get("id"),
                quantity=quantity,
            )
            cart_items_update.append(item)
        else:
            item = sap_migration_models.CartLines(
                cart_id=customer_cart_id,
                material_variant_id=variant_id,
                quantity=item_info["quantity"],
                contract_material_id=customer_contract_product_id,
            )
            cart_items_create.append(item)
    if len(cart_items_create):
        sap_migration_models.CartLines.objects.bulk_create(cart_items_create)
    if len(cart_items_update):
        sap_migration_models.CartLines.objects.bulk_update(
            cart_items_update, ["quantity"]
        )


@transaction.atomic
def update_customer_cart_line_quantity(customer_cart_id, cart_items_info):
    try:
        cart_items_update = []
        for item_info in cart_items_info:
            cart_line_id = item_info.id
            quantity = item_info.quantity
            material_variant_id = item_info.material_variant_id
            item = sap_migration_models.CartLines(
                id=cart_line_id,
                cart_id=customer_cart_id,
                quantity=quantity,
                material_variant_id=material_variant_id,
            )
            cart_items_update.append(item)

        if len(cart_items_update):
            sap_migration_models.CartLines.objects.bulk_update(
                cart_items_update, ["quantity", "material_variant_id"]
            )
        customer_cart = sap_migration_models.CartLines.objects.filter(
            cart_id=customer_cart_id
        )
        result = {"cart_items": customer_cart.all()}
        return result
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def get_cart_item_objects(customer_cart_id):
    cart_items = sap_migration_models.CartLines.objects.filter(
        cart_id=customer_cart_id
    ).values("id", "quantity", "material_variant_id", "contract_material_id")
    cart_item_objects = {}
    for cart_item in list(cart_items):
        cart_item_objects[
            concat_variant_id_and_contract_product_id(
                [
                    cart_item.get("material_variant_id"),
                    cart_item.get("contract_material_id"),
                ]
            )
        ] = cart_item
    return cart_item_objects


def concat_variant_id_and_contract_product_id(keys):
    return "_".join(str(x) for x in keys)


@transaction.atomic
def update_cart(cart_id, params, user):
    try:
        customer_cart = sap_migration_models.Cart.objects.get(id=cart_id)
        cart_items_info = params["lines"]
        create_or_update_customer_cart_items(
            cart_items_info, cart_id, customer_cart.contract_id
        )
        return customer_cart
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def create_customer_cart_items(cart_items_info, customer_cart_id, customer_contract_id):
    customer_contract_products = sap_migration_models.ContractMaterial.objects.filter(
        contract_id=customer_contract_id
    )
    contract_products_objects = {}
    for customer_contract_product in customer_contract_products:
        contract_products_objects[
            str(customer_contract_product.material_id)
        ] = customer_contract_product
    cart_items_create = []
    for item_info in cart_items_info:
        if (
            float(item_info["quantity"])
            > contract_products_objects[item_info["product_id"]].remaining_quantity
        ):
            raise ValueError("Quantity can not over remaining")
        variant_id = item_info.get("variant_id")
        if not variant_id:
            variant_id = (
                sap_migration_models.MaterialVariantMaster.objects.filter(
                    material_id=item_info["product_id"]
                )
                .values_list("id", flat=True)
                .first()
            )
        customer_contract_product_id = contract_products_objects[
            item_info["product_id"]
        ].id
        item = sap_migration_models.CartLines(
            cart_id=customer_cart_id,
            material_variant_id=variant_id,
            quantity=item_info["quantity"],
            contract_material_id=customer_contract_product_id,
        )
        cart_items_create.append(item)
    if len(cart_items_create):
        sap_migration_models.CartLines.objects.bulk_create(cart_items_create)
