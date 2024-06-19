from sap_master_data import models as sap_master_data_models
from sap_migration import models as sap_migration_models


def resolve_get_customer_block(sold_to_code, contract_no):
    if contract_no and not sold_to_code:
        contract_obj = sap_migration_models.Contract.objects.filter(code=contract_no).first()
        sold_to_code = contract_obj and contract_obj.sold_to.sold_to_code or None
    sold_to_code = sold_to_code.rjust(10, "0") if sold_to_code else None
    sold_to_obj = sap_master_data_models.SoldToMaster.objects.filter(sold_to_code=sold_to_code).first()
    customer_block = sold_to_obj and sold_to_obj.customer_block or None
    block_codes = ["Z1", "Z5"]
    if customer_block and customer_block.upper() in block_codes:
        return {
            "customer_block": True
        }
    return {
        "customer_block": False
    }
