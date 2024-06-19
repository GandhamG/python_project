from sap_migration.models import Contract, OrderLines


def resolve_export_pi(id):
    return Contract.objects.filter(pk=id).first()


def resolve_export_pis(info, **kwargs):
    queryset = Contract.objects.filter(distribution_channel__code='30').all()
    contract_code_sap = kwargs.get("filter", {}).get("sap_code", None)
    if contract_code_sap is not None:
        queryset = Contract.objects.filter(code__in=contract_code_sap).all()
    return queryset


def resolve_remaining_quantity(contract_material_id, order_id, remaining_quantity):
    if not order_id:
        return remaining_quantity

    line = OrderLines.objects.filter(order_id=order_id, contract_material_id=contract_material_id).first()
    reserved_quantity = 0
    if line:
        reserved_quantity = line.quantity

    return float(remaining_quantity) - float(reserved_quantity)


def resolve_remaining_quantity_ex(contract_material_id, order_id, remaining_quantity_ex):
    if not order_id:
        return remaining_quantity_ex

    line = OrderLines.objects.filter(order_id=order_id, contract_material_id=contract_material_id).first()
    reserved_quantity_ex = 0
    if line:
        reserved_quantity_ex = line.quantity

    return float(remaining_quantity_ex) - float(reserved_quantity_ex)
