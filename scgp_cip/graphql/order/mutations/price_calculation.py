
import graphene
from saleor.graphql.core.mutations import BaseMutation
from scg_checkout.graphql.types import SapOrderMessage, SapItemMessage
from scg_checkout.graphql.validators import validate_object, validate_objects
from scgp_cip.common.enum import PriceCalculationThirdPartySystem, CipOrderInput, OrderInformationSubmit, OrderLines
from scgp_cip.graphql.order.cip_order_error import CipOrderError
from scgp_cip.graphql.order.types import PriceSummaryResponse, PriceCalculationInput
from scgp_cip.service.integration.integration_service import price_calculation
from scgp_cip.service.helper.price_calculation_helper import get_response_message


class OrderLinePriceCalculator(BaseMutation):
    response = graphene.Field(PriceSummaryResponse)
    success = graphene.Boolean()
    sap_order_messages = graphene.List(SapOrderMessage)
    sap_item_messages = graphene.List(SapItemMessage)

    class Arguments:
        id = graphene.ID(description="ID of the order.", required=True)
        input = PriceCalculationInput(required=True, description="item details")

    class Meta:
        description = "Api for loading price details"
        error_type_class = CipOrderError
        object_type = PriceSummaryResponse
        return_field_name = "response"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        cls.validate_input(data)
        (sap_response, sap_order_messages, sap_item_messages, sap_success)\
            = price_calculation(info, data, PriceCalculationThirdPartySystem.SAP_ES41.value)
        response_class = cls(
            response=sap_response
        )
        return get_response_message(response_class, sap_success, sap_order_messages, sap_item_messages)

    @classmethod
    def validate_input(cls, data):
        validate_object(
            data.get("input").get("order_information", False),
            CipOrderInput.ORDER_INFORMATION.value,
            [OrderInformationSubmit.REQUEST_DATE.value , OrderInformationSubmit.ORDER_TYPE.value]
        )
        validate_objects(
            data.get("input").get("lines", []),
            CipOrderInput.LINES.value,
            [OrderLines.QUANTITY.value, OrderLines.ITEM_NO.value]
        )
