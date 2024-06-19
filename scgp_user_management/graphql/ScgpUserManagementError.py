from saleor.graphql.core.types.common import Error

from .enums import ScgpUserManagementErrorCode


class ScgpUserManagementError(Error):
    code = ScgpUserManagementErrorCode(description="The error code.", required=True)
