import logging

from common.mulesoft_api import MulesoftApiRequest
from scgp_export.graphql.enums import SapEnpoint

# TODO: create another API's calling here


def get_contract_detail(contract_no):
    if not contract_no:
        return None, None
    response = {}
    log_opts = {
        "contract_no": contract_no,
    }
    try:
        response = MulesoftApiRequest.instance(
            service_type="sap", **log_opts
        ).request_mulesoft_get(
            uri=SapEnpoint.ES_14.value + "/" + contract_no, params={}
        )
    except Exception as e:
        logging.error(
            "sap_master_data.mulesoft_api.get_contract_detail error %s" % str(e)
        )

    error = response.get("reason") or None
    result = response.get("data") or None
    return error, result
