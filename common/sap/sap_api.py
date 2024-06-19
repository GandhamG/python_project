from scgp_export.graphql.enums import SapEnpoint

from ..mulesoft_api import MulesoftApiRequest


class SapApiRequest(MulesoftApiRequest):
    # Throw SAP function here under format

    @classmethod
    def call_es_14_contract_detail(cls, contract_no: str):
        log_val = {
            "contract_no": contract_no,
        }
        return MulesoftApiRequest.instance(**log_val).request_mulesoft_get(
            uri=SapEnpoint.ES_14.value + "/" + contract_no, params={}
        )

    @classmethod
    def call_es_21_update_order(cls, data: dict):
        return MulesoftApiRequest.instance().request_mulesoft_post(
            url=SapEnpoint.ES_21.value, data=data
        )

    @classmethod
    def call_es_16_create(cls, request):
        response = cls.instance().request_mulesoft_post(
            url=SapEnpoint.ES_16.value, data=request
        )
        return response

    @classmethod
    def call_es_18_update(cls, request):
        response = cls.instance().request_mulesoft_patch(
            url=SapEnpoint.ES_18.value, data=request
        )
        return response

    @classmethod
    def call_sap_es08(cls, request):
        response = cls.instance().request_mulesoft_post(SapEnpoint.ES_08.value, request)
        return response

    @classmethod
    def call_sap_es26(cls, request):
        return cls.instance().request_mulesoft_get(SapEnpoint.ES_26.value, request)
