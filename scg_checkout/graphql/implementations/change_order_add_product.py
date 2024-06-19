from copy import deepcopy

from sap_migration import models as sap_migration_models
from sap_master_data import models as sap_master_data_modes

from django.db.models import F

from scg_checkout.graphql.implementations.validations import (
    validate_order_exists,
    validate_cannot_change_order,
)


def add_product_to_order(so_no, _input_items):
    order = sap_migration_models.Order.objects.annotate(
        sold_to__sold_to_code=F("sold_to__sold_to_code"),
        sales_organization_code=F("sales_organization__code"),
        distribution_channel_code=F("distribution_channel__code")
    ).filter(so_no=so_no).first()
    validate_order_exists(order)
    validate_cannot_change_order(order)

    input_items = deepcopy(_input_items)
    # IMPORTANT: add contract_material, material_variant to input_item
    add_data_to_input_item(input_items)

    material_code_to_weight = get_dict_material_code_to_weight(
        [item["material_variant"].code for item in input_items]
    )

    rt_order_lines = []
    for input_item in input_items:
        contract_material = input_item.get("contract_material")
        material_variant = input_item.get("material_variant")

        quantity = float(input_item.get("quantity"))

        line = sap_migration_models.OrderLines(
            order=order,
            contract_material=contract_material,
            material_id=material_variant.material_id,
            material_variant=material_variant,
            quantity=quantity,
            quantity_unit=contract_material.quantity_unit,
            weight=material_code_to_weight.get(material_variant.code),
            weight_unit=contract_material.weight_unit,
            payment_term_item=contract_material.payment_term,
            sales_unit="ROL",
            price_currency=contract_material.currency,
        )
        # IMPORTANT: we will NOT save order line to db
        rt_order_lines.append(line)
    return rt_order_lines


def add_data_to_input_item(input_items):
    contract_material_ids = [item.get("contract_material_id") for item in input_items]
    id_to_contract_material = sap_migration_models.ContractMaterial.objects.filter(id__in=contract_material_ids).in_bulk()
    id_to_material_variant = sap_migration_models.MaterialVariantMaster.objects.filter(
        material_id__in=[contract_material.material_id for contract_material in id_to_contract_material.values()]
    ).in_bulk()
    material_id_to_material_variant = {material_variant.material_id: material_variant for material_id, material_variant in id_to_material_variant.items()}
    for item in input_items:
        contract_material_id = int(item.get("contract_material_id"))
        material_variant_id = int(item.get("material_variant_id", "0"))
        contract_material = id_to_contract_material.get(contract_material_id)
        material_variant = id_to_material_variant.get(material_variant_id) or material_id_to_material_variant.get(contract_material.material_id)
        item["contract_material"] = contract_material
        item["material_variant"] = material_variant


def get_dict_material_code_to_weight(material_variant_codes):
    material_code_to_conversion_rol = (
        sap_master_data_modes.Conversion2Master.objects.filter(
            material_code__in=material_variant_codes,
            to_unit="ROL",
        )
        .distinct("material_code")
        .in_bulk(field_name="material_code")
    )
    material_code_to_conversion_ton = (
        sap_master_data_modes.Conversion2Master.objects.filter(
            material_code__in=material_variant_codes,
            to_unit="TON",
        )
        .distinct("material_code")
        .in_bulk(field_name="material_code")
    )
    rs = {}
    for material_code, conversion_instance in material_code_to_conversion_rol.items():
        rol_calculation = conversion_instance.calculation
        ton_calculation = material_code_to_conversion_ton[material_code].calculation
        rs[material_code] = rol_calculation / ton_calculation

    return rs
