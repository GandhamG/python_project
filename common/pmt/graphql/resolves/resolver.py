from scgp_cip.common.enum import MatSearchThirdPartySystem
from scgp_cip.service.integration.integration_service import mat_search


def resolve_pmt_mat_search(input_data):
    return mat_search(MatSearchThirdPartySystem.PMT.value, input_data)
