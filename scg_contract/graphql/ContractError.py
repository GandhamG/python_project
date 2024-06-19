from saleor.graphql.core.types.common import Error

from .enums import ContractErrorCode


class ContractError(Error):
    code = ContractErrorCode(description="The error code.", required=True)
