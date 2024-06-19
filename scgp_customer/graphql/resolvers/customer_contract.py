from sap_migration import models as sap_migration_models
from sap_master_data import models as sap_master_models


def resolve_scgp_customer_contracts(info, contract_no, sold_to_id, kwargs):
    contract_code_sap = kwargs.get("sap_code", None)
    contract = sap_migration_models.Contract.objects.filter(sold_to__user__id=info.context.user.id,
                                                            sold_to__id=sold_to_id)
    if contract_code_sap is not None:
        contract = contract.filter(code__in=contract_code_sap)
    if contract_no:
        contract = contract.filter(code__contains=contract_no[0])
    return contract


def resolve_contract(info, contract_id):
    return sap_migration_models.Contract.objects.get(id=contract_id)


def resolve_products(contract_id, sort_by, info):
    queryset = sap_migration_models.ContractMaterial.objects.filter(contract_id=contract_id)

    list_sap_material_id = info.variable_values.get("list_contract_item", None)
    if list_sap_material_id is not None:
        queryset = sap_migration_models.ContractMaterial.objects.filter(id__in=list_sap_material_id)

    if sort_by is not None:
        queryset = queryset.order_by(*["{}{}".format(sort_by["direction"], field) for field in sort_by["field"]])

    return queryset.order_by("item_no")


def resolve_unloading_point(sold_to_code):
    return sap_master_models.SoldToUnloadingPointMaster.objects.filter(sold_to_code=sold_to_code)
