import uuid
import graphene
import json
from saleor.graphql.core.mutations import BaseMutation
from common.enum import MulesoftServiceType
from common.mulesoft_api import MulesoftApiRequest
from scg_checkout.graphql.enums import RealtimePartnerType
from scg_checkout.graphql.types import RealtimePartner
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scgp_export.graphql.enums import SapEnpoint
from sap_migration.graphql.enums import OrderType


class CallAPISapRealtimePartner(BaseMutation):
    response = graphene.List(RealtimePartner)
    raw_response = graphene.String()

    class Arguments:
        pi_message_id = graphene.String(required=True, description="contract no of order")
        sold_to_code = graphene.String(required=True, description="sold to code")
        sale_org_code = graphene.String(required=True, description="sale organization code")
        order_type = graphene.Argument(OrderType, description="order type", required=False)
        type = graphene.List(RealtimePartnerType, description="type of realtime partner", required=True)
        distribution_channel = graphene.String(required=False)
        division = graphene.String(required=False)

    class Meta:
        description = "Call to api realtime partner"
        object_type = RealtimePartner
        error_type_class = ContractCheckoutError
        error_type_field = "contractCheckoutError"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        body = {
            "piMessageId": str(uuid.uuid1().int),
            "customerId": data.get("sold_to_code", "").split("-")[0].strip(),
            "saleOrg": data.get("sale_org_code", "").split("-")[0].strip(),
            "distriChannel": data.get("distribution_channel", "").split("-")[0].strip(),
            "division": data.get("division", "").split("-")[0].strip()
        }
        response = MulesoftApiRequest.instance(service_type=MulesoftServiceType.SAP.value).request_mulesoft_post(
            SapEnpoint.ES_08.value,
            body
        )
        try:
            order_type = data.get("order_type", None)
            if order_type == OrderType.CUSTOMER or order_type == OrderType.DOMESTIC:
                distribution_channel = ["10", "20"]
            else:
                distribution_channel = ["30"]
            result = list(filter(
                lambda item:
                item["partnerFunction"] in data["type"],
                response["data"][0]["partnerList"]
            ))

            if order_type:
                result = list(filter(
                    lambda item: item["distributionChannel"] in distribution_channel,
                    result
                ))
        except Exception:
            result = list()
        return cls(
            response=result,
            raw_response=json.dumps(response)
        )
