from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scgp_export.graphql.enums import OtsEndpoint


class OTSApiRequest(MulesoftApiRequest):
    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def call_ots_get_data(cls, data: dict):
        return cls.instance(
            service_type=MulesoftServiceType.OTS.value
        ).request_mulesoft_post(url=OtsEndpoint.OTS.value, data=data)
