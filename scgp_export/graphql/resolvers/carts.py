from django.db.models import Count, Subquery, OuterRef

from sap_migration.models import (
    CartLines,
    ContractMaterial,
    Cart,
)
from scgp_export import models
from sap_master_data import models as master_models


def resolve_cart_items(cart_id):
    return CartLines.objects.filter(cart_id=cart_id)


def resolve_products(contract_id, info):
    list_sap_material_id = info.variable_values.get("list_contract_item")
    filter_dict = {"contract_id": contract_id}
    if list_sap_material_id is not None:
        filter_dict = {"id__in": list_sap_material_id}

    return ContractMaterial.objects.filter(**filter_dict).annotate(
        calculation=Subquery(
            master_models.Conversion2Master.objects.filter(
                material_code=OuterRef('material_code'), to_unit='ROL'
            ).order_by("material_code", "-id").distinct("material_code").values('calculation'),
        )
    ).order_by("item_no")


def resolve_export_pi(pi_id):
    return models.ExportPI.objects.filter(id=pi_id).first()


def resolve_items(user_id):
    return Cart.objects.annotate(quantity_cart_lines=Count('cartlines')) \
        .filter(created_by__id=user_id, is_active=True, type="export", quantity_cart_lines__gt=0)


def resolve_export_cart(cart_id, user_id):
    return Cart.objects.get(id=cart_id, created_by__id=user_id, type="export")


def resolve_pi(contract_material_id):
    return ContractMaterial.objects.get(id=contract_material_id)
