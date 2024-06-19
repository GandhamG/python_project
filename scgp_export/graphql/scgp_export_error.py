from saleor.graphql.core.types.common import Error
from .enums import ScgpExportErrorCode


class ScgpExportError(Error):
    code = ScgpExportErrorCode(description="The error code.", required=True)
