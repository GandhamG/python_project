from saleor.graphql.core.types.common import Error
from .enums import Scgp_PoUpload_ErrorCode

class ScgpPoUploadError(Error):
    code = Scgp_PoUpload_ErrorCode(description="The error code.", required=True)
