from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scgp_cip.common.enum import OrderSolutionEndpoint


class CPApiRequest(MulesoftApiRequest):
    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def call_cp(cls, data: dict):
        return cls.instance(
            service_type=MulesoftServiceType.CP.value
        ).request_mulesoft_post(url=OrderSolutionEndpoint.CP.value, data=data)
