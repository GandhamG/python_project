import graphene

from saleor.graphql.core.mutations import ModelMutation, BaseMutation

from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError
from scg_checkout.graphql.implementations.dtp_dtr import handle_order_line, response_from_sap
from scg_checkout.graphql.types import TempOrderLine
from sap_migration import models as migration_models


class CalculateDtpDtr(ModelMutation):
    status = graphene.String()

    class Meta:
        description = "Update dosmetic order line"
        model = migration_models.OrderLines
        object_type = graphene.List(TempOrderLine)
        return_field_name = "OrderLines"
        error_type_class = ContractCheckoutError
        error_type_field = "temp_order_line"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        order_lines = handle_order_line()
        response = cls.success_response(order_lines)
        return response


class PostToSap(BaseMutation):
    response = graphene.String()

    class Meta:
        description = "Post to SAP"
        error_type_class = ContractCheckoutError
        error_type_field = "temp_order_line"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        path = 'scg_checkout/graphql/implementations/response_api_es21.json'
        result = response_from_sap(path)
        return cls(
            response=result
        )
