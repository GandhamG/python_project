from saleor.graphql.core.enums import CipOrderErrorCodes
from saleor.graphql.core.types import Error


class CipOrderError(Error):
    code = CipOrderErrorCodes(description="The error code.", required=True)
