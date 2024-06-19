from django.db.models import Sum

from sap_migration import models as sap_migration_model


def resolve_remaining_quantity(contract_product_id, order_id, remaining_quantity):
    if not order_id:
        return remaining_quantity

    sum_quantity = sap_migration_model.OrderLines.objects.filter(order_id=order_id,contract_material_id=contract_product_id).values(
        "contract_material").order_by("contract_material").annotate(sum_quantity=Sum("quantity")).first()
    reserved_quantity = 0
    if sum_quantity:
        reserved_quantity = sum_quantity.get("sum_quantity", 0)

    return float(remaining_quantity) - float(reserved_quantity)
