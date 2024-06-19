from sap_migration import models


def resolve_contract_materials(contract_id):
    return models.ContractMaterial.objects.filter(contract_id=contract_id)
