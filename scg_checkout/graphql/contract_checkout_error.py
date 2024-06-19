from saleor.graphql.core.types.common import Error
from .enums import ContractCheckoutErrorCode


class ContractCheckoutError(Error):
    code = ContractCheckoutErrorCode(description="The error code.", required=True)
