import logging

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Count

from common.sap.sap_api import SapApiRequest
from saleor.plugins.manager import get_plugins_manager
from sap_migration import models as sap_migration_models
from scg_checkout.graphql.helper import round_qty_decimal
from scg_checkout.graphql.resolves.orders import call_sap_es26


@transaction.atomic
def contract_create_checkout(params, created_by):
    try:
        contract_id = params["contract_id"]
        user_id = params["user_id"]
        checkout_lines_info = params["lines"]
        cart = sap_migration_models.Cart.objects.filter(
            sold_to_id=user_id,
            created_by=created_by,
            type="domestic",  # TODO Resolve why we need user_id
        ).first()
        if not cart:
            cart = sap_migration_models.Cart.objects.create(
                contract_id=contract_id,
                sold_to_id=user_id,
                created_by=created_by,
                type="domestic",
            )
        create_checkout_lines(checkout_lines_info, cart.id, contract_id)

        return cart
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def create_or_update_checkout_lines(checkout_lines_info, cart_id, contract_id):
    contract_materials = sap_migration_models.ContractMaterial.objects.filter(
        contract_id=contract_id
    )
    contract_materials_objects = {}
    for contract_material in contract_materials:
        contract_materials_objects[
            str(contract_material.material_id)
        ] = contract_material
    checkout_lines_create = []
    checkout_lines_update = []
    checkout_line_objects = get_checkout_line_objects(cart_id)
    for line_info in checkout_lines_info:
        if float(line_info["quantity"]) == 0:
            raise ValueError("Unacceptable quantity value 0")
        variant_id = line_info.get("variant_id")
        if not variant_id:
            variant_id = (
                sap_migration_models.MaterialVariantMaster.objects.filter(
                    material_id=line_info["product_id"]
                )
                .values_list("id", flat=True)
                .first()
            )
        contract_material_id = contract_materials_objects.get(
            line_info["product_id"]
        ).id
        cartline_object = checkout_line_objects.get(
            concat_variant_id_and_contract_product_id(
                [variant_id, contract_material_id]
            ),
            None,
        )
        if cartline_object:
            quantity = float(cartline_object.get("quantity")) + float(
                line_info["quantity"]
            )
            line = sap_migration_models.CartLines(
                id=cartline_object.get("id"),
                quantity=quantity,
            )
            checkout_lines_update.append(line)
        else:
            line = sap_migration_models.CartLines(
                cart_id=cart_id,
                material_id=line_info["product_id"],
                material_variant_id=variant_id,
                quantity=line_info["quantity"],
                contract_material_id=contract_material_id,
            )
            checkout_lines_create.append(line)
    if len(checkout_lines_create):
        sap_migration_models.CartLines.objects.bulk_create(checkout_lines_create)
    if len(checkout_lines_update):
        sap_migration_models.CartLines.objects.bulk_update(
            checkout_lines_update, ["quantity"]
        )


def get_checkout_line_objects(cart_id):
    cart_lines = sap_migration_models.CartLines.objects.filter(cart_id=cart_id).values(
        "id", "quantity", "material_variant_id", "contract_material_id"
    )
    cart_line_objects = {}
    for cart_line in list(cart_lines):
        cart_line_objects[
            concat_variant_id_and_contract_product_id(
                [
                    cart_line.get("material_variant_id"),
                    cart_line.get("contract_material_id"),
                ]
            )
        ] = cart_line
    return cart_line_objects


def concat_variant_id_and_contract_product_id(keys):
    return "_".join(str(x) for x in keys)


@transaction.atomic
def contract_update_checkout(params):
    checkout_lines_info = params["input"].pop("lines")
    checkout_lines = []
    for line_info in checkout_lines_info:
        line = {
            "id": line_info["id"],
            "variant_id": line_info["variant_id"],
            "quantity": line_info["quantity"],
            "selected": line_info["selected"],
        }

        checkout_lines.append(line)
    sap_migration_models.CartLines.objects.bulk_update(
        [
            sap_migration_models.CartLines(
                id=line.get("id"),
                material_variant_id=line.get("variant_id"),
                quantity=line.get("quantity"),
                # selected=line.get("selected"),  # TODO: Confirm on selected field
            )
            for line in checkout_lines
        ],
        [
            "material_variant_id",
            "quantity",
        ],  # TODO: Confirm on selected field
        batch_size=100,
    )
    return sap_migration_models.Cart.objects.filter(id=params["id"]).first()


@transaction.atomic
def contract_checkout_lines_delete(param):
    try:
        cart_lines = sap_migration_models.CartLines.objects.filter(
            pk__in=param.get("checkout_line_ids")
        )
        checkout_id = cart_lines[0].cart_id
        cart_lines.delete()
        sap_migration_models.Cart.objects.filter(id=checkout_id).annotate(
            num_cart_lines=Count("cartlines")
        ).filter(num_cart_lines=0).delete()

        return cart_lines
    except Exception as e:
        transaction.set_rollback(True)
        raise ImproperlyConfigured(e)


def validate_checkout_lines_info(checkout_lines_info, contract_materials_objects):
    if any(float(line_info["quantity"]) == 0 for line_info in checkout_lines_info):
        raise ValueError("Unacceptable quantity value 0")

    if any(
        line_info.get("contract_material_id")
        and not contract_materials_objects.get(line_info["contract_material_id"])
        for line_info in checkout_lines_info
    ):
        raise ValueError("Unacceptable contract_material_id")


def create_checkout_lines(checkout_lines_info, cart_id, contract_id):
    contract_materials = sap_migration_models.ContractMaterial.objects.filter(
        contract_id=contract_id
    )
    contract_materials_objects = {
        str(contract_material.id): contract_material
        for contract_material in contract_materials
    }

    validate_checkout_lines_info(checkout_lines_info, contract_materials_objects)

    checkout_lines_create = []
    checkout_lines_update = []
    for line_info in checkout_lines_info:
        variant_id = line_info.get("variant_id")

        if not variant_id:
            variant_id = (
                sap_migration_models.MaterialVariantMaster.objects.filter(
                    material_id=line_info["product_id"]
                )
                .values_list("id", flat=True)
                .first()
            )

        contract_material_id = line_info.get("contract_material_id")

        if not contract_material_id:
            contract_material_id = (
                sap_migration_models.ContractMaterial.objects.filter(
                    contract_id=contract_id, material_id=line_info["product_id"]
                )
                .first()
                .id
            )

        line = sap_migration_models.CartLines.objects.filter(
            cart_id=cart_id,
            material_id=line_info["product_id"],
            material_variant_id=variant_id,
            contract_material_id=contract_material_id,
        ).first()
        if not line:
            line = sap_migration_models.CartLines(
                cart_id=cart_id,
                material_id=line_info["product_id"],
                material_variant_id=variant_id,
                quantity=line_info["quantity"],
                contract_material_id=contract_material_id,
            )
            checkout_lines_create.append(line)
            continue
        line.quantity = round_qty_decimal(
            line_info["quantity"] + line.quantity
            if line.quantity
            else line_info["quantity"]
        )
        checkout_lines_update.append(line)

    if checkout_lines_create:
        sap_migration_models.CartLines.objects.bulk_create(checkout_lines_create)
    if checkout_lines_update:
        sap_migration_models.CartLines.objects.bulk_update(
            checkout_lines_update, ["quantity"]
        )


def delete_order_line_newly_added_in_database(so_no, list_item_no):
    sap_migration_models.OrderLines.all_objects.filter(
        order__so_no=so_no, item_no__in=list_item_no
    ).delete()
    order_lines = list(
        sap_migration_models.OrderLines.all_objects.filter(
            order__so_no=so_no, draft=True
        )
    )
    lines = sap_migration_models.OrderLines.all_objects.filter(order__so_no=so_no)
    if not lines:
        sap_migration_models.Order.objects.filter(so_no=so_no).update(
            product_group=None
        )
    order_lines.sort(key=lambda line: int(line.item_no))
    if not order_lines:
        return
    min_item_no = int(order_lines[0].item_no) - 10
    for order_line in order_lines:
        min_item_no += 10
        order_line.item_no = str(min_item_no)
    sap_migration_models.OrderLines.all_objects.bulk_update(order_lines, ["item_no"])
    return True


def delete_and_sync_order_line_with_es_26(so_no):
    manager = get_plugins_manager()
    sap_fn = manager.call_api_sap_client
    es26_response = call_sap_es26(so_no=so_no, sap_fn=sap_fn)
    _order_lines_from_es26 = es26_response["data"][0].get("orderItems", None)
    draft_item_no_from_db = list(
        sap_migration_models.OrderLines.all_objects.values_list(
            "item_no", flat=True
        ).filter(order__so_no=so_no, draft=True)
    )
    draft_item_no_from_db_with_zeros = [item.zfill(6) for item in draft_item_no_from_db]
    item_no_from_es = [item["itemNo"] for item in _order_lines_from_es26]
    item_no_to_delete = [
        element
        for element in draft_item_no_from_db_with_zeros
        if element not in item_no_from_es
    ]
    logging.info(
        f"item number from es26 a = {item_no_from_es},\
                 item number from db = {draft_item_no_from_db}"
    )
    if item_no_to_delete:
        item_no_to_delete_int = [int(i) for i in item_no_to_delete]
        logging.info(f"item number to delete = {item_no_to_delete_int}")
        sap_migration_models.OrderLines.all_objects.filter(
            order__so_no=so_no, item_no__in=item_no_to_delete_int
        ).delete()
    else:
        logging.info("there is no such item to delete ")
    return True


def resolve_check_contract_expired_complete_invalid(contract_no):
    response = SapApiRequest.call_es_14_contract_detail(contract_no=contract_no)
    error_code = response.get("errorCode", None)
    if error_code and error_code == "SAP0001":
        return True
    return False
