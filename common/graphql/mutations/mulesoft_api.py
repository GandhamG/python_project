import graphene
from django.db import transaction

from common.models import MulesoftLog
from saleor.graphql.core.mutations import ModelMutation
from saleor.graphql.core.types import ModelObjectType
from scg_checkout.graphql.contract_checkout_error import ContractCheckoutError


class MulesoftAPILogCreateInput(graphene.InputObjectType):
    url = graphene.String(required=True, description="URL of the mulesoft log.")
    request = graphene.String(required=True, description="Request of the mulesoft log.")
    response = graphene.String(description="Response of the mulesoft log.")
    exception = graphene.String(description="Exception of the mulesoft log.")
    response_time_ms = graphene.Int(description="Response time of the mulesoft log.")
    retry_count = graphene.Int(description="Retry count of the mulesoft log.")
    retry = graphene.Boolean(description="Retry of the mulesoft log.")
    feature = graphene.String(description="Feature of the mulesoft log.")
    order_number = graphene.String(description="Order number of the mulesoft log.")
    orderid = graphene.Int(description="Order id of the mulesoft log.")
    
class MulesoftLogType(ModelObjectType):
    id = graphene.ID(description="ID of the mulesoft log")
    class Meta:
        model = MulesoftLog

class MulesoftAPILogCreate(ModelMutation):
    success = graphene.Boolean(description="Whether the mulesoft log was created.")
    class Arguments:
        input = MulesoftAPILogCreateInput(
            required=True, description="Fields required to create mulesoft log."
        )
    class Meta:
        description = "Mulesoft Api Log"
        model = MulesoftLog
        return_field_name = "mulesoft_log"
        error_type_class = ContractCheckoutError
        error_type_field = "graphql_error"
        object_type = MulesoftLogType

    @classmethod
    def perform_mutation(cls, root, info, **kw):
        with transaction.atomic():
            data = kw.get("input")
            MulesoftLog.objects.create(**data)
        return MulesoftAPILogCreate(success=True)
