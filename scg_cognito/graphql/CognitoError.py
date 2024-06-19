from saleor.graphql.core.types.common import Error

from .enums import CognitoErrorCode


class CognitoError(Error):
    code = CognitoErrorCode(description="The error code.", required=True)
