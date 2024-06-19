from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scgp_cip.common.enum import PmtEndpoint


class PmtApiRequest(MulesoftApiRequest):
    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def call_pmt_mat_search(cls, data: dict):
        return MulesoftApiRequest.instance(
            service_type=MulesoftServiceType.PMT.value
        ).request_mulesoft_post(url=PmtEndpoint.PMT_MAT_SEARCH.value, data=data)
