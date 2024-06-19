from saleor.graphql.core.types.common import Error

from .enums import CustomerErrorCode


class CustomerError(Error):
    code = CustomerErrorCode(description="The error code.", required=True)
