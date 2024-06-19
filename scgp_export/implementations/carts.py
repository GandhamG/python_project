from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from sap_master_data.models import Conversion2Master, MaterialMaster
from sap_migration.models import Cart, CartLines, ContractMaterial


@transaction.atomic
def create_export_cart(params, created_by):
    try:
        pi_id = params["pi_id"]
        sold_to_id = params["sold_to_id"]
        export_cart = Cart.objects.get_or_create(
            created_by=created_by,
            contract_id=pi_id,
            sold_to_id=sold_to_id,
            type="export",
        )
        # create_export_cart_items(params, export_cart[0].id)
        create_or_update_export_cart_items(params, export_cart[0].id)
        return export_cart[0]
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def create_or_update_export_cart_items(params, cart_id):
    cart_items_info = params["lines"]
    export_cart_items = []
    items_update = []

    conversion_objects = (
        Conversion2Master.objects.filter(
            to_unit="ROL",
        )
        .order_by("material_code", "-id")
        .distinct("material_code")
        .in_bulk(field_name="material_code")
    )

    for cart_item in cart_items_info:
        contract_material_id = cart_item["pi_product_id"]
        contract_material = ContractMaterial.objects.filter(
            id=contract_material_id
        ).first()
        conversion_object = conversion_objects.get(
            str(contract_material.material_code), None
        )
        calculation = conversion_object and conversion_object.calculation or 0
        cart_item_quantity_in_ton = (
            float(cart_item["quantity"]) * round(calculation / 1000, 3)
            if calculation
            else cart_item["quantity"]
        )
        # if calculation:
        #     cart_item["quantity"] = float(cart_item["quantity"]) * round(calculation / 1000, 3)
        # else:
        #     raise ValueError("The material code is not found in conversion table")
        items = CartLines.objects.filter(
            cart_id=cart_id, contract_material_id=contract_material_id
        ).first()
        if items:
            item_quantity_in_ton = (
                float(items.quantity) * round(calculation / 1000, 3)
                if calculation
                else items.quantity
            )
            if (
                cart_item_quantity_in_ton + item_quantity_in_ton
                > contract_material.remaining_quantity_ex
            ):
                raise ValueError("The input quantity is over the remaining")
            quantity = float(cart_item["quantity"]) + float(items.quantity)
            item_update = CartLines(
                id=items.pk,
                quantity=quantity,
            )
            items_update.append(item_update)
        else:
            if cart_item_quantity_in_ton > contract_material.remaining_quantity_ex:
                raise ValueError("The input quantity is over the remaining")
            item = CartLines(
                cart_id=cart_id,
                contract_material_id=contract_material_id,
                quantity=cart_item["quantity"],
            )
            export_cart_items.append(item)
    if items_update:
        CartLines.objects.bulk_update(
            items_update,
            ["quantity"],
        )
    if export_cart_items:
        CartLines.objects.bulk_create(export_cart_items)

    export_cart = Cart.objects.get(id=cart_id)
    export_cart.is_active = True
    export_cart.save()


@transaction.atomic
def update_export_cart(cart_id, params, user):
    try:
        export_cart = Cart.objects.get(id=cart_id)
        create_or_update_export_cart_items(params, cart_id)
        return export_cart
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


@transaction.atomic
def create_export_cart_items(params, cart_id):
    try:
        cart_items_info = params["lines"]
        export_cart_items = []
        pi_product_ids = []

        for cart_item in cart_items_info:
            pi_product_id = cart_item["pi_product_id"]
            pi_product_ids.append(pi_product_id)

        material_ids = list(
            ContractMaterial.objects.filter(id__in=pi_product_ids).values_list(
                "material_id", flat=True
            )
        )
        material_codes = list(
            MaterialMaster.objects.filter(id__in=material_ids).values_list(
                "material_code", flat=True
            )
        )

        conversion_objects = (
            Conversion2Master.objects.filter(
                material_code__in=material_codes,
                to_unit="ROL",
            )
            .distinct("material_code")
            .in_bulk(field_name="material_code")
        )
        contract_material_objects = ContractMaterial.objects.filter(
            pk__in=pi_product_ids,
        ).in_bulk(field_name="id")

        for cart_item in cart_items_info:
            contract_material_id = cart_item["pi_product_id"]
            contract_material_object = contract_material_objects.get(
                int(contract_material_id), None
            )
            material_code = (
                contract_material_object.material.material_code
                if contract_material_object.material
                else ""
            )
            conversion_object = conversion_objects.get(str(material_code), None)
            if conversion_object:
                calculation = conversion_object.calculation
                weight = float(calculation) / 1000
                if (
                    float(cart_item["quantity"]) * weight
                ) > contract_material_object.remaining_quantity:
                    raise ValueError("The input quantity is over the remaining")

            item = CartLines(
                cart_id=cart_id,
                contract_material_id=contract_material_id,
                quantity=cart_item["quantity"],
            )
            export_cart_items.append(item)
        if export_cart_items:
            CartLines.objects.bulk_create(export_cart_items)

        export_cart = Cart.objects.get(id=cart_id)
        export_cart.is_active = True
        export_cart.save()

    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def update_draft_cart_items(params):
    cart_lines = params["lines"]
    cart_ids = [cart.get("id") for cart in cart_lines]
    qs_cart_lines = CartLines.objects.filter(id__in=cart_ids).in_bulk(field_name="id")

    cart_lines_update = []
    for cart_line in cart_lines:
        cart_line_id = int(cart_line.get("id"))
        cart_line_object = qs_cart_lines.get(cart_line_id)
        cart_line_object.quantity = cart_line.get("quantity")
        cart_lines_update.append(cart_line_object)
    CartLines.objects.bulk_update(cart_lines_update, ["quantity"])


@transaction.atomic
def update_draft_export_cart_items(params, cart_id, user):
    export_cart = Cart.objects.get(id=cart_id)
    update_draft_cart_items(params)
    return export_cart
