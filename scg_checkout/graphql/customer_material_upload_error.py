import graphene

from saleor.graphql.core.types import Error
from scg_checkout.graphql.enums import ContractCheckoutErrorCode
from scg_checkout.graphql.types import CustomerMaterialErrorData


class CustomerMaterialUploadError(Error):
    code = ContractCheckoutErrorCode(description="The error code.", required=True)
    data = graphene.Field(CustomerMaterialErrorData)


