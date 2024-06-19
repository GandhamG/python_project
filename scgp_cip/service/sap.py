import logging

from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scgp_cip.service.helper.price_calculation_helper import prepare_payload_for_es_41
from scgp_export.graphql.enums import SapEnpoint


def call_sap_es_41(
    lines_in,
    order_db,
    order_information_in,
    order_partners,
    item_no_order_line_db,
):
    body = prepare_payload_for_es_41(
        lines_in,
        order_db,
        order_information_in,
        order_partners,
        item_no_order_line_db,
    )
    logging.info(f"[No Ref Contract - Price Calculator] ES41 Request payload : {body}")
    return MulesoftApiRequest.instance(
        service_type=MulesoftServiceType.SAP.value
    ).request_mulesoft_post(SapEnpoint.ES_41.value, body)
