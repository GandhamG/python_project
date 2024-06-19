import logging

from sap_master_data import models as sap_master_data_models


def resolve_weight_other_products(root, info):
    try:
        converted_weight = resolve_weight_common(
            root, root.material_variant.code, root.sales_unit
        )
    except Exception as e:
        converted_weight = ""
        logging.info(f" weight conversion  : {root.material_variant} exception: {e}")

    return converted_weight


def resolve_weight_for_rol(root, info):
    try:
        converted_weight = resolve_weight_common(
            root, root.material_variant.code, "ROL"
        )
    except Exception as e:
        converted_weight = ""
        logging.info(f" weight conversion  : {root.material_variant} exception: {e}")

    return converted_weight


def resolve_weight_common(root, material_variant_code, sales_unit):
    calculation = getattr(root, "calculation", 0)
    if not calculation:
        conversion_master = (
            sap_master_data_models.Conversion2Master.objects.filter(
                material_code__in=[material_variant_code], to_unit=sales_unit
            )
            .distinct("material_code")
            .order_by("material_code", "-id")
            .values("calculation")
            .first()
        )

        calculation = conversion_master and conversion_master["calculation"] or 0

    return round(calculation / 1000, 3)
