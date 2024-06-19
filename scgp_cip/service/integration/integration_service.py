import time
import uuid

from common.cp.cp_service import get_cp_solution
from common.pmt.pmt_service import mat_search_by_pmt
from common.sap.sap_api import SapApiRequest
from scgp_cip.common.enum import (
    MatSearchThirdPartySystem,
    OrderSolutionThirdPartySystem,
    PriceCalculationThirdPartySystem,
    ThirdPartySystemApi,
)
from scgp_cip.service.price_calculation_service import derive_price_summary_using_es_41


def create_order(request):
    return SapApiRequest.call_es_16_create(request)


def change_order(api_name, request):
    if ThirdPartySystemApi.SAP_ES_18 == api_name:
        return SapApiRequest.call_es_18_update(request)


def mat_search(system_name, input_data):
    if MatSearchThirdPartySystem.PMT.value == system_name:
        return mat_search_by_pmt(input_data)


def price_calculation(info, input_data, system_name):
    if PriceCalculationThirdPartySystem.SAP_ES41.value == system_name:
        return derive_price_summary_using_es_41(info, input_data)


def get_solution(system_name, request):
    if OrderSolutionThirdPartySystem.CP.value == system_name and request:
        return get_cp_solution(request)


def get_partner_info(data):
    sales_organization_code = data.sales_organization_code
    sold_to_code = data.sold_to_code
    pi_message_id = str(time.time())
    request = {
        "piMessageId": pi_message_id,
        "customerId": sold_to_code,
        "saleOrg": sales_organization_code,
        "distriChannel": data.distribution_channel_code,
        "division": data.division_code,
    }
    response = SapApiRequest.call_sap_es08(request)
    data = response["data"][0]
    return data


def get_order_details(so_no):
    request = {"piMessageId": str(uuid.uuid1().int), "saleOrderNo": so_no}

    return SapApiRequest.call_sap_es26(request)
