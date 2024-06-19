from saleor.graphql.core.types.common import Error
from .enums import ScgpCustomerErrorCode


class ScgpCustomerError(Error):
    code = ScgpCustomerErrorCode(description="The error code.", required=True)
