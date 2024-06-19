from saleor.graphql.core.types.common import Error

from .enums import ScgpRequireAttentionItemsErrorCode


class ScgpRequireAttentionItemsError(Error):
    code = ScgpRequireAttentionItemsErrorCode(description="The error code.", required=True)
